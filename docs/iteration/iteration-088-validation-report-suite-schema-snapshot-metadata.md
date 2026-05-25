# Iteration 088: Validation Report Suite Schema Snapshot Metadata

日期：2026-05-25

## 本轮目标

Iteration 083 新增了 machine-readable suite schema snapshot：

```text
docs/evals/suite-schema-v1.json
```

但 `validate_eval_suite()` 的报告之前只记录 `schema_version` 和 supported versions，不能证明本次 validation 对应哪个 schema artifact。

本轮目标是让 validation report 记录 suite schema snapshot 的 id、路径和 SHA256。

## 已完成变更

1. `suite_validation.py` 新增：

```python
SUITE_SCHEMA_SNAPSHOT_PATH = Path(__file__).resolve().parents[2] / "docs" / "evals" / "suite-schema-v1.json"
```

2. 新增 `_suite_schema_snapshot_metadata()`。

它会读取 snapshot 文件并返回：

- `suite_schema_id`
- `suite_schema_path`
- `suite_schema_sha256`

3. `_validation_report()` 现在把 snapshot metadata 写入 JSON report。

4. `eval_suite_validation_to_markdown()` 现在展示：

- Suite schema id
- Suite schema path
- Suite schema sha256

5. 测试验证：

- report 中的 `suite_schema_id` 等于 snapshot `$id`；
- report 中的 `suite_schema_sha256` 等于当前文件实际 SHA256；
- Markdown 中展示 schema id 和 hash。

## 对 Metis Harness 的意义

这一步把 eval suite validation 从“字段检查报告”推进到“可审计校验报告”。

在长期 9B/flash eval 循环里，我们需要回答：

1. 这个 suite 用哪个 schema version？
2. validator 当时支持哪些版本？
3. 当时对应的 machine-readable schema artifact 是哪一个？
4. 这个 artifact 的精确内容 hash 是什么？

有了 snapshot hash，未来回看历史 validation report 时，可以判断它对应的 schema 文件是否发生过变化。

## 当前限制

1. validation report 记录了 snapshot hash，但还没有把它和 release gate 绑定。
2. snapshot 只覆盖 suite schema v1，尚无多版本 snapshot registry。
3. snapshot hash 没有写入 generic eval run manifest。
4. snapshot 本身还没有用 JSON Schema validator 执行校验。
5. 没有单独的 schema artifact integrity command。

## 下一步任务

1. release gate 增加 unversioned suite 策略。
2. suite version/migration 增加专用异常与诊断码。
3. suite-level `tool_schemas` 设计。
4. suite-local tool schema 合法性检查。
5. generic eval run manifest 记录 suite schema snapshot metadata。

## 验证结果

- `python -m pytest tests\unit\test_eval_suite_validation.py -q`
  - 结果：16 passed
- `python -m pytest tests\unit\test_eval_suite_validation.py tests\unit\test_cli_eval.py tests\unit\test_eval_suite_run.py tests\unit\test_eval_runner.py tests\unit\test_eval_compare.py -q`
  - 结果：135 passed
- `python -m pytest -q`
  - 结果：323 passed, 4 skipped
- `python -m compileall -q metis`
  - 结果：通过
