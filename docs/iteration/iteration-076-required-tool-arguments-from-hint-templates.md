# Iteration 076: Required Tool Arguments From Hint Templates

日期：2026-05-25

## 本轮目标

Iteration 075 已经生成 `schema_repair_argument_templates`。本轮把模板继续转成 materialized targeted suite 可执行的 `required_tool_arguments`。

目标是让 targeted eval 不只携带诊断元数据，还能声明 corrected call 必须满足哪些参数要求。

## 已完成变更

1. `schema_repair_argument_templates` 新增 `tool_name`。

2. `build_eval_stubs_from_repair_tasks()` 会从 corrected template 生成 `required_tool_arguments`。

示例：

```json
{
  "tool": "write_file",
  "arguments": {
    "path": {
      "contains": "required path"
    }
  }
}
```

3. 生成规则是保守的：

- 只有模板有 `tool_name` 时才生成。
- 只有 `corrected_arguments` 非空时才生成。
- 占位符值会转成 `contains` 谓词，而不是伪装成真实业务值。
- 空 corrected template 不生成 required argument。

4. materialized targeted suite 继承 `required_tool_arguments`。

5. 新增测试：

- stub 中的 corrected template 会转成 `required_tool_arguments`。
- materialized suite 保留相同要求。
- 写盘后的 suite 能通过 `validate_eval_suite()` 的 schema-aware validation。

## 对 Metis Harness 的意义

这一轮让 targeted eval stub 从“建议修复什么”继续推进到“评测时必须看到什么工具参数”。

对 9B/flash 模型来说，这很关键：

1. 只要求 schema repair success 还不够。
2. 必须要求模型最终调用正确工具。
3. 必须要求 corrected call 带上关键参数。
4. 必须让 suite validator 先证明这些参数要求和工具 schema 相容。

## 当前限制

1. `contains` 仍是宽松谓词，后续需要 schema-aware placeholder filling。
2. corrected template 还没有从真实 tool schema 推断 enum、number、array 的更具体值。
3. generated prompt 还没有自动描述 malformed/corrected 参数对。
4. real 9B suite 还没有直接运行这些 materialized tasks。

## 下一步任务

1. 从 tool schema 推断 placeholder 类型和值。
2. 生成 prompt 时包含 malformed/corrected 参数对。
3. materialized suite 增加 schema version。
4. real small-model eval suite 增加一条由 hint template 生成的任务。

## 验证结果

- `python -m pytest tests\unit\test_eval_compare.py -q`
  - 结果：34 passed
- `python -m pytest tests\unit\test_eval_compare.py tests\unit\test_cli_eval.py tests\unit\test_eval_suite_validation.py tests\unit\test_eval_suite_run.py -q`
  - 结果：90 passed
- `python -m pytest -q`
  - 结果：312 passed, 4 skipped
- `python -m compileall -q metis`
  - 结果：通过
