# Iteration 068: Schema Repair Hint Release Gate

日期：2026-05-25

## 本轮目标

Iteration 067 已经把 schema repair hint recovery 做成 suite-level summary。本轮把它接入 release gate。

对面向 9B/flash 小模型的 harness 来说，hint recovery 不能只是报告里的观察项。小模型经常会第一次工具参数写错，harness 的价值在于能否通过 schema guardrail 和 repair hint 把它拉回正确轨道。因此 hint recovery rate 应该能进入 CI/发布阈值，阻断回归。

## 已完成变更

1. `evaluate_eval_run_gate` 新增阈值：

- `min_schema_repair_hint_recovery_rate`
- `max_schema_repair_hint_failures`

2. Gate aggregates 新增：

- `schema_repair_hints_seen`
- `schema_repair_hint_successes`
- `schema_repair_hint_failures`
- `schema_repair_hint_recovery_rate`

3. Gate 支持两种数据源：

- 优先读取 `eval-report.json` 顶层 `summary`。
- 如果旧报告没有 `summary`，回退扫描每个 result 的 task-level hint metrics。

4. CLI `metis eval gate` 新增参数：

- `--min-schema-repair-hint-recovery-rate`
- `--max-schema-repair-hint-failures`

5. Gate markdown/json 会自然输出新增 aggregates 和 thresholds。

## 新增测试覆盖

1. 当 summary 中 hint recovery rate 低于阈值时 gate 失败。
2. 当 summary 中 hint failure 数超过阈值时 gate 失败。
3. 当旧报告没有 summary 时，gate 能从 result-level metrics 聚合 recovery rate。
4. CLI 默认参数会传入新增阈值。
5. CLI 显式参数能解析并传递新增阈值。

## 对 Metis Harness 的意义

这一轮让 hint recovery 从“可观察”变成“可阻断回归”。

后续可以定义更贴近 9B 小模型真实能力的 release profile：

1. 基础任务成功率必须达标。
2. 工具调用错误必须可恢复。
3. schema repair hint recovery rate 必须达标。
4. hint failure 不能无限累积。
5. failure clusters 不能出现 critical 回归。

这比只看 success rate 更稳，因为 success rate 可能掩盖“模型频繁犯错但偶然成功”的问题；hint recovery rate 能更直接衡量 harness 对小模型的纠偏能力。

## 当前限制

1. release gate 还没有按 hint type 设置阈值。
2. comparison report 还没有比较 hint recovery rate delta。
3. real 9B/flash eval suite 还没有专门加入 hint recovery tasks。
4. manifest 还没有写入 summary，外部工具读取仍需打开 eval-report.json。

## 下一步任务

1. 把 summary 写入 run manifest。
2. comparison report 增加 hint recovery regression 检查。
3. real small-model eval suite 增加额外参数修复和空命令数组修复任务。
4. gate 支持按 hint type 的失败阈值。

## 验证结果

- `python -m pytest tests\unit\test_eval_gate.py tests\unit\test_cli_eval.py -q`
  - 结果：43 passed
- `python -m compileall -q metis`
  - 结果：通过

