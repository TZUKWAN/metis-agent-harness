# Iteration 082: Version-Aware Suite Loader

日期：2026-05-25

## 本轮目标

Iteration 080 让 validator 能拒绝 unsupported schema version，Iteration 081 补了 schema v1 文档。但实际 runner 加载路径仍然是直接读 JSON，然后提取 `tasks`。

这意味着如果绕过 CLI validation、直接调用 `load_eval_task_specs()` 或 `load_eval_suite_payload()`，runner 仍可能消费未知 suite 版本。

本轮目标是把 runner 加载路径改成 version-aware，并让 `suite_run` 复用同一个入口。

## 已完成变更

1. `metis.evals.runner` 新增：

```python
SUPPORTED_EVAL_SUITE_SCHEMA_VERSIONS = frozenset({"1"})
```

2. 新增 `normalize_eval_suite_payload()`。

行为：

- list payload 会规范化为 legacy `custom-json-list` payload；
- 非 object/list payload 抛出 `TypeError`；
- 缺失 `schema_version` 保持 legacy 兼容；
- 非字符串 `schema_version` 抛出 `ValueError`；
- unsupported schema version 抛出 `ValueError`；
- supported schema version 返回 payload copy。

3. 新增 `load_versioned_eval_suite_payload()`。

这是 runner 层的统一加载入口：

```text
path or directory -> targeted-eval-suite.json -> JSON parse -> normalize_eval_suite_payload()
```

4. `load_eval_task_specs()` 改为调用 `load_versioned_eval_suite_payload()`。

5. `suite_run.load_eval_suite_payload()` 改为复用 runner 的 version-aware loader。

6. `suite_validation.py` 复用 runner 层的 `SUPPORTED_EVAL_SUITE_SCHEMA_VERSIONS`，避免 validator 和 runner 各自维护一份 supported set。

7. 新增测试：

- `load_versioned_eval_suite_payload()` 会拒绝 `schema_version: "2"`。
- `suite_run.load_eval_suite_payload()` 会拒绝 `schema_version: "2"`。
- 原有 materialized suite directory load path 仍能读取 version 1 suite。

## 对 Metis Harness 的意义

这是版本治理从“校验报告”进入“运行入口”的一步。

对长期 harness 来说，runner 是最终可信边界之一。只在 CLI validation 中做版本检查是不够的，因为调用方可能绕过 CLI，直接调用 Python API。现在 runner 本身也会拒绝 unsupported suite version，减少把格式不兼容误判成模型能力退化的风险。

## 当前限制

1. 还没有 migration registry。
2. unversioned suite 仍被兼容加载。
3. direct JSON list payload 被归为 legacy `custom-json-list`，没有版本。
4. supported version set 还没有导出到机器可读 schema artifact。
5. runner 的错误目前是 `ValueError`，还没有专用异常类型。

## 下一步任务

1. 生成 machine-readable suite schema 或 schema snapshot。
2. prompt argument template context 增加数量限制、排序策略和溢出摘要。
3. suite-local/custom tool schema 接入 placeholder 生成。
4. release gate 增加 unversioned suite 策略。
5. 为 suite version/migration 增加专用异常与诊断码。

## 验证结果

- `python -m pytest tests\unit\test_eval_runner.py tests\unit\test_eval_suite_run.py tests\unit\test_eval_suite_validation.py -q`
  - 结果：59 passed
- `python -m pytest tests\unit\test_eval_runner.py tests\unit\test_eval_suite_run.py tests\unit\test_eval_suite_validation.py tests\unit\test_cli_eval.py tests\unit\test_eval_compare.py -q`
  - 结果：129 passed
- `python -m pytest -q`
  - 结果：316 passed, 4 skipped
- `python -m compileall -q metis`
  - 结果：通过
