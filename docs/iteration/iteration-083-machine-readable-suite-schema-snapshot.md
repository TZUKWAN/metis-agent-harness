# Iteration 083: Machine-Readable Suite Schema Snapshot

日期：2026-05-25

## 本轮目标

Iteration 081 增加了 Markdown 版 suite schema 文档，Iteration 082 让 runner 的加载路径变成 version-aware。但当前 schema 契约仍主要靠文档和 Python validator 表达。

本轮目标是新增机器可读的 suite schema snapshot，让工具、审查流程和未来 migration 能读取一个稳定的 JSON artifact。

## 已完成变更

1. 新增 JSON schema snapshot：

```text
docs/evals/suite-schema-v1.json
```

2. snapshot 内容覆盖：

- top-level suite object；
- `schema_version` const `1`；
- `tasks` array；
- wrapped task entry；
- direct `EvalTaskSpec` entry；
- `required_tool_arguments`；
- list/bool/int/dict task spec fields；
- non-negative nullable counters；
- `x-metis` metadata。

3. `docs/evals/suite-schema.md` 增加 machine-readable snapshot 链接。

4. `tests/unit/test_docs_exist.py` 增加 schema snapshot 契约测试。

测试会从代码中读取：

- `EvalTaskSpec` dataclass fields；
- `SUPPORTED_EVAL_SUITE_SCHEMA_VERSIONS`；
- `LIST_FIELDS`；
- `BOOL_FIELDS`；
- `INT_FIELDS`；
- `DICT_FIELDS`；
- `PREDICATE_KEYS`。

然后反查 `suite-schema-v1.json`，确认 snapshot 没有和代码字段集合漂移。

## 对 Metis Harness 的意义

这一步把 suite schema 从“人能读的说明”推进到“机器可消费的契约”。

它对后续能力很关键：

1. migration 工具可以读取 schema artifact。
2. release gate 可以检查 schema artifact 与 runner 支持版本是否一致。
3. 外部场景项目可以用 schema snapshot 生成或校验自己的 eval suite。
4. 文档、validator、runner 之间的漂移可以更早暴露。
5. 长期 9B/flash eval 数据集可以形成更稳定的数据协议。

## 当前限制

1. JSON schema snapshot 还没有接入 `validate_eval_suite()` 的实际校验流程。
2. snapshot 使用 `additionalProperties: true`，仍以兼容性为先。
3. wrapper metadata 的内部结构仍较宽松。
4. `required_tool_arguments.arguments` 仍只声明为 object，精细校验仍由 Python validator 根据 tool schema 完成。
5. 没有自动从 dataclass 生成 JSON schema，当前是手写 snapshot 加契约测试。

## 下一步任务

1. prompt argument template context 增加数量限制、排序策略和溢出摘要。
2. suite-local/custom tool schema 接入 placeholder 生成。
3. release gate 增加 unversioned suite 策略。
4. 为 suite version/migration 增加专用异常与诊断码。
5. 将 JSON schema snapshot 接入 validation report，报告 snapshot id/hash。

## 验证结果

- `python -m pytest tests\unit\test_docs_exist.py tests\unit\test_eval_suite_validation.py -q`
  - 结果：16 passed
- `python -m pytest tests\unit\test_docs_exist.py tests\unit\test_eval_suite_validation.py tests\unit\test_eval_runner.py tests\unit\test_eval_suite_run.py tests\unit\test_eval_compare.py -q`
  - 结果：96 passed
- `python -m pytest -q`
  - 结果：317 passed, 4 skipped
- `python -m compileall -q metis`
  - 结果：通过
