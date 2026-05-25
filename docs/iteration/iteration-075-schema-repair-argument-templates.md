# Iteration 075: Schema Repair Argument Templates

日期：2026-05-25

## 本轮目标

Iteration 074 已经让 targeted eval stub 消费 `schema_repair_hint_events`，并生成 hint-aware gates。本轮继续推进：从 `schema_repair_hint_details` 推断 malformed/corrected argument templates。

目标不是伪造真实业务参数，而是生成可审查、可替换、可自动化加工的模板，让后续 targeted eval 更接近可执行任务。

## 已完成变更

1. targeted eval stub 新增 `schema_repair_argument_templates`。

每个模板包含：

- `hint_type`
- `schema_path`
- `schema_keyword`
- `malformed_arguments`
- `corrected_arguments`
- `notes`

2. 第一批模板覆盖：

- `add_required_property`
- `remove_additional_property`
- `increase_array_items`
- `reduce_array_items`
- `fix_type`
- `increase_numeric_value`
- `reduce_numeric_value`
- `fix_string_pattern`
- `use_enum_value`

3. 对前三类高频 hint 增加测试覆盖：

- `add_required_property`
  - malformed: `{}`
  - corrected: `{"path": "<required path>"}`
- `remove_additional_property`
  - malformed: `{"url": "<unsupported url>"}`
  - corrected: `{}`
- `increase_array_items`
  - malformed: `{"command": []}`
  - corrected: `{"command": ["<command item>"]}`

4. `eval_stubs_to_markdown()` 展示 argument template 摘要。

5. `materialize_eval_suite_from_stubs()` 保留 `schema_repair_argument_templates`。

## 对 Metis Harness 的意义

这一轮把 hint diagnosis 进一步转成 eval construction material。

现在链路变成：

```text
schema.repair_hint event
-> hint details
-> repair task
-> hint-aware eval stub
-> argument templates
-> future executable schema repair eval
```

这对 9B/flash 模型很重要，因为小模型不是靠“更聪明”解决所有问题，而是靠 harness 把错误压缩成稳定、短、可执行的修复任务。

## 当前限制

1. 模板仍是占位符，还没有填入真实工具 schema 的示例值。
2. 模板还没有自动合并到 `EvalTaskSpec.required_tool_arguments`。
3. corrected template 还没有绑定 expected tool name。
4. real small-model suite 还没有直接消费这些模板。

## 下一步任务

1. 给 argument template 增加 `tool_name`。
2. 从 tool schema 推断占位符类型，例如 string、array、number、enum。
3. 把 corrected template 转成 `required_tool_arguments`。
4. materialized suite 输出 hint-aware metadata 到 task spec。

## 验证结果

- `python -m pytest tests\unit\test_eval_compare.py -q`
  - 结果：33 passed
- `python -m pytest tests\unit\test_eval_compare.py tests\unit\test_cli_eval.py tests\unit\test_eval_suite_validation.py -q`
  - 结果：81 passed
- `python -m pytest -q`
  - 结果：311 passed, 4 skipped
- `python -m compileall -q metis`
  - 结果：通过
