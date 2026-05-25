# Iteration 081: Suite Schema V1 Documentation

日期：2026-05-25

## 本轮目标

Iteration 079-080 已经完成两件事：

1. generated materialized targeted suite 会写入 `schema_version: "1"`。
2. validator 会拒绝声明了未知 schema version 的 suite。

但这还不够。版本治理必须有正式 schema 文档，否则后续 runner、validator、migration、release gate 和外部用户都只能从代码里反推格式。

本轮目标是新增 `docs/evals/suite-schema.md`，把 schema version 1 的结构、字段语义、兼容规则和迁移规则写清楚，并增加测试确保文档关键内容不会丢失。

## 已完成变更

1. 新增文档：

```text
docs/evals/suite-schema.md
```

2. 文档覆盖内容：

- suite schema 的用途；
- 当前 supported versions；
- 顶层字段；
- wrapped task entry；
- direct EvalTaskSpec entry；
- EvalTaskSpec 字段；
- required tool arguments；
- schema repair metadata；
- compatibility rules；
- migration rules；
- release gate expectations。

3. 更新 docs 契约测试：

```text
tests/unit/test_docs_exist.py
```

新增 `test_eval_suite_schema_doc_covers_version_contract()`，检查文档至少包含：

- `SUPPORTED_EVAL_SUITE_SCHEMA_VERSIONS`
- `schema_version`
- `Task Entry Forms`
- `EvalTaskSpec`
- `required_tool_arguments`
- `Compatibility Rules`
- `Migration Rules`
- `Release Gate Expectations`

## 对 Metis Harness 的意义

Metis 的 eval suite 是 harness 自我改进循环的核心资产。它要长期承载：

1. 真实 9B/flash 模型失败样本。
2. schema repair regression。
3. tool retry obedience regression。
4. evidence finalization regression。
5. provider/profile 对比。
6. release gate。
7. 未来自动 migration 和 backfill。

没有正式 schema 文档，版本号只是一个字段；有了 schema 文档，版本号才变成可治理协议。

## 当前限制

1. 文档是 Markdown，不是机器可执行 JSON Schema。
2. runner 仍没有 version-aware loader。
3. migration 工具还不存在。
4. release gate 还没有强制 unversioned suite 策略。
5. 文档契约测试只检查关键章节与关键词，不验证每个字段都和代码完全同步。

## 下一步任务

1. runner 增加 version-aware load path。
2. 生成 machine-readable suite schema 或 schema snapshot。
3. prompt argument template context 增加数量限制、排序策略和溢出摘要。
4. suite-local/custom tool schema 接入 placeholder 生成。
5. release gate 增加 unversioned suite 策略。

## 验证结果

- `python -m pytest tests\unit\test_docs_exist.py tests\unit\test_eval_suite_validation.py tests\unit\test_eval_compare.py -q`
  - 结果：49 passed
- `python -m pytest tests\unit\test_docs_exist.py tests\unit\test_eval_compare.py tests\unit\test_cli_eval.py tests\unit\test_eval_suite_validation.py tests\unit\test_eval_suite_run.py -q`
  - 结果：93 passed
- `python -m pytest -q`
  - 结果：314 passed, 4 skipped
- `python -m compileall -q metis`
  - 结果：通过
