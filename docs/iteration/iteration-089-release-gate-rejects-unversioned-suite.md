# Iteration 089: Release Gate Rejects Unversioned Suite

日期：2026-05-25

## 本轮目标

`validate_eval_suite()` 为兼容旧手写 suite，会把 missing `schema_version` 保留为 warning。但 release/strict gate 不应该允许 unversioned suite 进入发布评测。

本轮目标是在 `metis eval run-suite --gate` 中加入 unversioned suite 拦截策略。

## 已完成变更

1. `_eval_run_suite()` 增加 gate 前置检查：

```text
validation valid
-> if --gate and suite is unversioned: fail before model run
-> env check
-> model run
-> report
-> gate
```

2. 新增 `_validation_has_unversioned_suite()`。

判定方式：

- `validation["schema_version"] == "unversioned"`；或
- warnings 中存在：

```json
{
  "path": "schema_version",
  "code": "missing"
}
```

3. 当 `--gate` 遇到 unversioned suite：

- 打印 validation markdown；
- 打印明确原因；
- 返回 exit code `1`；
- 不检查模型环境变量；
- 不运行 provider；
- 不写 eval run report。

4. 新增 CLI 测试：

- `run-suite --gate` 拒绝 unversioned suite；
- 拒绝发生在 env check 之前。

## 对 Metis Harness 的意义

Metis 的目标是可长期迭代、可审计、可回归。未声明 schema version 的 suite 可以作为 legacy 兼容输入，但不能作为 release gate 的依据。

这一轮把策略分层明确化：

1. validation：兼容旧 suite，给 warning。
2. normal run-suite：仍允许 legacy 测试。
3. run-suite --gate：严格要求 declared supported schema version。

这避免 unversioned suite 混入正式回归，导致未来无法解释评测结果对应的 suite schema。

## 当前限制

1. 只覆盖 `run-suite --gate`，还没有覆盖独立 `metis eval gate --run`。
2. gate report 本身还没有记录 suite validation report。
3. generic eval run manifest 还没有记录 suite schema snapshot metadata。
4. unversioned suite policy 还不能通过 CLI 参数显式放宽。
5. real-small-model 固定 suite 暂未接入同样的 suite schema policy。

## 下一步任务

1. generic eval run manifest 记录 suite schema snapshot metadata。
2. suite version/migration 增加专用异常与诊断码。
3. suite-level `tool_schemas` 设计。
4. suite-local tool schema 合法性检查。
5. 独立 `metis eval gate --run` 增加 suite schema evidence 检查。

## 验证结果

- `python -m pytest tests\unit\test_cli_eval.py -q`
  - 结果：37 passed
- `python -m pytest tests\unit\test_cli_eval.py tests\unit\test_eval_suite_validation.py tests\unit\test_eval_suite_run.py tests\unit\test_eval_runner.py tests\unit\test_eval_compare.py -q`
  - 结果：136 passed
- `python -m pytest -q`
  - 结果：324 passed, 4 skipped
- `python -m compileall -q metis`
  - 结果：通过
