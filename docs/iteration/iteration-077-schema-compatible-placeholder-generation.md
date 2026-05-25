# Iteration 077: Schema-Compatible Placeholder Generation

日期：2026-05-25

## 本轮目标

Iteration 076 已经能从 schema repair argument template 生成 `required_tool_arguments`，但 corrected template 里的值仍是宽泛占位符，例如 `<required path>`。这种值适合表达“这里需要一个参数”，但不适合作为可验证 targeted eval 的底座。

本轮目标是把这些占位符升级为 schema-compatible placeholder：

1. 从工具 schema 推断字段类型。
2. 为 string、array、number、boolean、enum、oneOf 生成能通过 schema validation 的值。
3. 继续保留 placeholder 的性质，不伪装成真实业务数据。
4. 让 `required_tool_arguments` 从 schema-compatible corrected template 派生。
5. 让 hint event 中出现的工具自动进入 eval stub 的 `allowed_tools`。

## 已完成变更

1. `build_eval_stubs_from_repair_tasks()` 现在会从 `schema_repair_hint_events` 提取 `tool_name`。

这些工具名会合并到 targeted eval stub 的 `allowed_tools`，避免 repair task 指向 `run_command` 但生成的 stub 只允许 `read_file/write_file`。

2. schema repair argument template 会按工具 schema 生成 corrected placeholder。

当前实现通过 `ToolRegistry` 和 `register_builtin_tools()` 读取内置工具 schema，然后按 `tool_name + schema_path leaf` 找到字段 schema。

示例：

```json
{
  "hint_type": "add_required_property",
  "schema_path": "$.path",
  "tool_name": "write_file",
  "corrected_arguments": {
    "path": "outputs/metis-placeholder.txt"
  }
}
```

3. 数组类 hint 会生成非空数组。

示例：

```json
{
  "hint_type": "increase_array_items",
  "schema_path": "$.command",
  "tool_name": "run_command",
  "malformed_arguments": {
    "command": []
  },
  "corrected_arguments": {
    "command": ["metis-placeholder-command_item"]
  }
}
```

4. `required_tool_arguments` 会使用 schema-compatible corrected value。

示例：

```json
[
  {
    "tool": "write_file",
    "arguments": {
      "path": {
        "contains": "outputs/metis-placeholder.txt"
      }
    }
  },
  {
    "tool": "run_command",
    "arguments": {
      "command": {
        "contains": "metis-placeholder-command_item"
      }
    }
  }
]
```

5. suite validation 继续保持 schema-aware。

新增测试验证 materialized suite 写盘后可以通过 `validate_eval_suite()`，并且 `required_tool_arguments` 的字段名与工具 schema 相容。

## 当前生成策略

当前 placeholder 生成规则是保守的：

1. `enum`：选择第一个枚举值。
2. `oneOf`：优先选择 array 分支；没有 array 分支时选择第一个可解析分支。
3. `array`：生成一个元素，元素按 `items` schema 递归生成。
4. `integer/number`：优先使用 `minimum`，否则使用 `1`。
5. `boolean`：使用 `true`。
6. `path`：使用 `outputs/metis-placeholder.txt`。
7. `content`：使用 `metis-placeholder-content`。
8. `encoding`：使用 `utf-8`。
9. `command`：默认字符串分支使用 `python --version`。
10. 其他 string 字段：使用 `metis-placeholder-<field>`。

## 对 Metis Harness 的意义

这一步把 targeted eval 从“描述一个要修的 schema 问题”继续推进到“能生成更接近可执行任务的 schema-compatible 参数约束”。

对 9B/flash 模型尤其重要：

1. 小模型容易在工具参数类型上犯错。
2. harness 需要把错误变成可恢复、可评测、可回归的结构化任务。
3. 评测任务必须先经过 schema-aware validation，不能靠人工假设。
4. 生成的修复参数必须足够具体，才能进入真实 provider eval。
5. 这些 placeholder 仍然明确标记为 placeholder，避免把模板误当成业务数据。

## 当前限制

1. schema 来源当前只覆盖内置工具。

后续需要把运行时 registry、项目自定义工具 schema 或 suite-local tool schema 传入 stub generator。

2. `oneOf` 分支选择仍是启发式。

当前优先选择 array 分支，是为了覆盖 `increase_array_items` 这类 hint。后续应按 hint type 和 schema keyword 选择更准确的分支。

3. prompt 仍未自动包含 malformed/corrected 参数对。

虽然 metadata 已经存在，但模型实际运行时还没有收到这些对照样例。下一轮应把它们写入 eval prompt 或独立 fixture。

4. materialized suite 还没有 schema version。

后续需要为 generated targeted suite 加版本，避免老 suite 和新 runner 之间出现隐式不兼容。

5. real 9B eval suite 尚未直接消费这些生成任务。

当前是生成、校验、写盘链路完成；下一步要把它接到真实小模型回归任务中。

## 下一步任务

1. 把 malformed/corrected argument template 注入 targeted eval prompt。
2. 为 materialized targeted suite 增加 schema version。
3. 支持从 suite-local/custom tool schema 生成 placeholder。
4. 把第一批 hint-derived tasks 纳入真实 9B provider eval。
5. 按 hint type 改进 `oneOf` 分支选择策略。

## 验证结果

- `python -m pytest tests\unit\test_eval_compare.py -q`
  - 结果：34 passed
- `python -m pytest tests\unit\test_eval_compare.py tests\unit\test_cli_eval.py tests\unit\test_eval_suite_validation.py tests\unit\test_eval_suite_run.py -q`
  - 结果：90 passed
- `python -m pytest -q`
  - 结果：312 passed, 4 skipped
- `python -m compileall -q metis`
  - 结果：通过
