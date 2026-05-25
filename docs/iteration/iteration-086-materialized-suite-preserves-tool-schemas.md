# Iteration 086: Materialized Suite Preserves Tool Schemas

日期：2026-05-25

## 本轮目标

Iteration 085 让 targeted eval stub generation 能使用 repair task 或 hint event 携带的 custom tool schema。这个能力已经能生成正确的 schema-compatible placeholder，但 custom schema 信息只停留在 stub 层。

本轮目标是让 materialized targeted suite 保留 `tool_schemas`，并同步更新 suite schema 文档和 machine-readable JSON snapshot。

## 已完成变更

1. `materialize_eval_suite_from_stubs()` 的 task wrapper 现在保留：

```json
{
  "tool_schemas": {}
}
```

2. `docs/evals/suite-schema.md` 的 wrapped task entry 增加：

```text
tool_schemas: object mapping tool names to JSON schemas
```

3. `docs/evals/suite-schema-v1.json` 的 `wrapped_task_entry.properties` 增加：

```json
{
  "tool_schemas": {
    "type": "object",
    "additionalProperties": {
      "type": "object"
    }
  }
}
```

4. `tests/unit/test_docs_exist.py` 增加 snapshot 契约断言，确认 wrapped task entry 声明 `tool_schemas`。

5. `tests/unit/test_eval_compare.py` 增加测试：

- custom tool schema 从 stub materialize 到 suite task wrapper。
- 普通 repair metadata preservation 测试覆盖 `tool_schemas`。

## 对 Metis Harness 的意义

自定义工具 schema 是场景智能体的核心扩展点。stub 阶段能使用 custom schema 还不够，必须把它带到 materialized suite，后续 runner、validator、report 和 migration 才能继续使用。

这一轮让链路变成：

```text
repair task tool_schemas
-> targeted eval stub tool_schemas
-> materialized suite task wrapper tool_schemas
-> suite schema v1 contract
```

这对 9B/flash 模型尤其关键，因为业务工具的 schema 是 harness 降低模型工具调用错误率的主要手段。

## 当前限制

1. `tool_schemas` 已进入 suite wrapper，但 generic eval validation context 尚未自动合并 suite-local schemas。
2. suite-level `tool_schemas` 尚未定义，只支持 task wrapper 级别。
3. `tool_schemas` 的内部 JSON schema 结构在 snapshot 中仍较宽松。
4. runner 还没有把 task wrapper `tool_schemas` 传入执行期工具 registry。
5. validation report 还没有报告 schema snapshot id/hash。

## 下一步任务

1. custom tool schema 接入 generic eval validation context。
2. validation report 增加 suite schema snapshot id/hash。
3. release gate 增加 unversioned suite 策略。
4. suite version/migration 增加专用异常与诊断码。
5. suite-level `tool_schemas` 设计。

## 验证结果

- `python -m pytest tests\unit\test_eval_compare.py tests\unit\test_docs_exist.py -q`
  - 结果：40 passed
- `python -m pytest tests\unit\test_eval_compare.py tests\unit\test_docs_exist.py tests\unit\test_eval_suite_validation.py tests\unit\test_eval_runner.py tests\unit\test_eval_suite_run.py -q`
  - 结果：99 passed
- `python -m pytest -q`
  - 结果：320 passed, 4 skipped
- `python -m compileall -q metis`
  - 结果：通过
