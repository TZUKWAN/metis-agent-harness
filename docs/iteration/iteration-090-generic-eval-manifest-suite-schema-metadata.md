# Iteration 090: Generic Eval Manifest Suite Schema Metadata

日期：2026-05-25

## 本轮目标

Iteration 088 让 validation report 记录 suite schema snapshot metadata。但真正的 eval run artifact 里，`manifest.json` 还不能证明这次运行对应哪个 suite schema snapshot。

本轮目标是让 generic eval suite metadata、manifest 和 latest pointer 都记录 suite schema snapshot id/path/hash。

## 已完成变更

1. `suite_validation.py` 将 `_suite_schema_snapshot_metadata()` 提升为公开 helper：

```python
suite_schema_snapshot_metadata()
```

2. `generic_eval_suite_metadata()` 现在包含：

- `suite_schema_id`
- `suite_schema_path`
- `suite_schema_sha256`

3. `generic_eval_suite_manifest()` 顶层现在包含：

- `suite_schema_id`
- `suite_schema_path`
- `suite_schema_sha256`

4. `write_generic_eval_latest_pointer()` 现在包含：

- `suite_schema_id`
- `suite_schema_sha256`

5. 测试覆盖：

- generic suite metadata 的 schema snapshot hash 等于当前 `suite-schema-v1.json` 的真实 SHA256；
- manifest 写入 schema id/path/hash；
- latest pointer 写入 schema id/hash。

## 对 Metis Harness 的意义

validation report 证明“这份 suite 能不能跑”，run manifest 证明“这次实际跑了什么”。两者都必须记录 schema artifact，才能让历史 eval 可审计。

这一轮让链路变成：

```text
suite-schema-v1.json
-> validation report
-> generic eval suite metadata
-> manifest.json
-> latest.json
```

对长期 9B/flash 回归尤其重要：未来回看某次 run 时，不仅能看到模型、profile、suite path，还能看到当时对应的 suite schema snapshot hash。

## 当前限制

1. real-small-model 固定 suite manifest 还没有同样的 suite schema metadata。
2. independent `metis eval gate --run` 还没有检查 manifest 是否有 schema metadata。
3. migration 仍没有专用异常与诊断码。
4. suite-level `tool_schemas` 尚未设计。
5. suite-local tool schema 合法性检查仍较弱。

## 下一步任务

1. 独立 `metis eval gate --run` 增加 suite schema evidence 检查。
2. real-small-model manifest 增加 schema metadata 或声明非-loadable-suite。
3. suite version/migration 增加专用异常与诊断码。
4. suite-level `tool_schemas` 设计。
5. suite-local tool schema 合法性检查。

## 验证结果

- `python -m pytest tests\unit\test_eval_suite_run.py tests\unit\test_eval_suite_validation.py -q`
  - 结果：25 passed
- `python -m pytest tests\unit\test_eval_suite_run.py tests\unit\test_eval_suite_validation.py tests\unit\test_cli_eval.py tests\unit\test_eval_compare.py tests\unit\test_eval_runner.py -q`
  - 结果：136 passed
- `python -m pytest -q`
  - 结果：324 passed, 4 skipped
- `python -m compileall -q metis`
  - 结果：通过
