# Iteration 087: Suite-Local Tool Schema Validation

日期：2026-05-25

## 本轮目标

Iteration 086 已经让 materialized targeted suite 保留 `tool_schemas`。但 `validate_eval_suite()` 默认还只使用调用方显式传入的 `tool_schemas`，不会自动读取 suite wrapper 中的 custom schemas。

本轮目标是让 suite-local custom tool schemas 自动参与 required tool argument 校验。

## 已完成变更

1. `validate_eval_suite()` 现在会构造 merged tool schema view：

```text
suite-local tool_schemas
-> explicit tool_schemas override
```

2. 如果调用方没有显式传入 `available_tools`，但 suite-local 或 explicit tool schemas 可用，validator 会用 schema key 集合作为 tool inventory。

3. 新增 `_suite_local_tool_schemas()`。

它会从 wrapped task entries 中提取：

```json
{
  "tool_schemas": {
    "tool_name": {}
  }
}
```

4. 新增 `_merged_tool_schemas()`。

它合并 suite-local schema 和调用方显式 schema；显式 schema 优先，避免 suite 文件覆盖外部 registry。

5. 新增测试：

- suite-local `crm_update` schema 可以让 `allowed_tools` 和 `required_tool_arguments` 通过校验。
- suite-local schema 会拒绝 argument type mismatch。
- explicit `tool_schemas` 会覆盖 suite-local schema。

## 对 Metis Harness 的意义

这一轮把 custom tool schema 的链路继续闭合：

```text
repair task tool_schemas
-> targeted eval stub
-> materialized suite task wrapper
-> validate_eval_suite()
-> required_tool_arguments schema-aware validation
```

对通用 harness 来说，这一点很重要。业务场景里的工具不可能都在 Metis 内置 registry 里，suite 必须能携带自己的工具 schema，并在 validation 阶段自证参数要求是合法的。

## 当前限制

1. suite-level `tool_schemas` 还没有定义，只读取 task wrapper 级别。
2. suite-local schema 只用于 validation，还没有注册到 runtime tool registry。
3. validation report 还没有列出实际使用的 suite-local tool schemas。
4. suite schema snapshot 还没有 id/hash 写入 validation report。
5. 对 schema 本身的 JSON Schema 合法性检查仍然较弱。

## 下一步任务

1. validation report 增加 suite schema snapshot id/hash。
2. release gate 增加 unversioned suite 策略。
3. suite version/migration 增加专用异常与诊断码。
4. suite-level `tool_schemas` 设计。
5. suite-local tool schema 合法性检查。

## 验证结果

- `python -m pytest tests\unit\test_eval_suite_validation.py -q`
  - 结果：16 passed
- `python -m pytest tests\unit\test_eval_suite_validation.py tests\unit\test_eval_compare.py tests\unit\test_eval_runner.py tests\unit\test_eval_suite_run.py tests\unit\test_cli_eval.py -q`
  - 结果：135 passed
- `python -m pytest -q`
  - 结果：323 passed, 4 skipped
- `python -m compileall -q metis`
  - 结果：通过
