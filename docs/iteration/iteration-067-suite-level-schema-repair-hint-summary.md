# Iteration 067: Suite-Level Schema Repair Hint Summary

日期：2026-05-25

## 本轮目标

前几轮已经完成了 schema repair hints 的生成、类型化、任务级指标和 failure clustering。本轮补 suite-level 汇总。

没有 suite-level summary 时，单个任务能看到 hint 是否恢复成功，但无法快速判断整套 eval 的 hint recovery 水平。面向 9B/flash 小模型，这个汇总非常关键，因为 harness 的目标不是让模型永远不犯错，而是让模型在错误后被框架稳定拉回正确轨道。

## 已完成变更

1. `EvalSuiteResult.summary` 新增 run-level 汇总。

当前 summary 包含：

- `task_count`
- `passed`
- `failed`
- `schema_repair_hints_seen`
- `schema_repair_hint_successes`
- `schema_repair_hint_failures`
- `schema_repair_hint_recovery_rate`
- `schema_repair_hint_types_seen`
- `schema_repair_hint_type_successes`
- `schema_repair_hint_type_failures`

2. `eval-report.json` 新增顶层 `summary`。

这让后续 comparison、gate、CI、dashboard 可以直接读取 run-level 指标，不必扫描所有 result。

3. `eval-report.md` 新增 `## Summary`。

Markdown 报告现在能直接看到：

- schema repair hint recovery rate
- hint type seen distribution
- hint type success distribution
- hint type failure distribution

4. 新增 suite summary 聚合测试。

测试覆盖：

- 两个任务的 hint seen/success/failure 汇总。
- hint recovery rate = successes / seen。
- hint type seen/success/failure map 聚合。
- JSON report 包含 summary。
- Markdown report 展示 recovery rate 和失败 hint type。

## 对 Metis Harness 的意义

这一步让 schema repair hint 从“单任务诊断信息”变成“可比较的运行级指标”。

后续可以用它做：

1. 不同模型的 hint recovery rate 对比。
2. 不同 profile 的 repair 能力对比。
3. 发布前 gate：hint recovery rate 低于阈值则失败。
4. 历史 run regression：某类 hint 的失败率上升时报警。
5. 真实 9B/flash 模型能力曲线追踪。

## 当前限制

1. summary 还没有接入 `eval gate` 阈值。
2. comparison report 还没有比较 hint recovery rate delta。
3. suite-level summary 还没有按 tool name 拆分。
4. hint type 统计还没有按 schema path 或 schema keyword 展开。
5. real 9B/flash eval suite 还没有加入专门的 hint recovery tasks。

## 下一步任务

1. 给 eval gate 增加 suite-level hint recovery 阈值。
2. 给 comparison report 增加 hint recovery regression 检查。
3. 在 real small-model eval suite 加入两个 hint recovery 任务。
4. 把 summary 写入 run manifest，便于外部工具读取。
5. 增加 hint recovery by tool 的分布。

## 验证结果

- `python -m pytest tests\unit\test_eval_runner.py -q`
  - 结果：44 passed
- `python -m compileall -q metis`
  - 结果：通过
