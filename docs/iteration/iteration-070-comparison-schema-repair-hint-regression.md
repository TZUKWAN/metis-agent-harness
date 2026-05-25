# Iteration 070: Comparison Schema Repair Hint Regression

日期：2026-05-25

## 本轮目标

Iteration 069 已经把 eval summary 写入 manifest 和 latest pointer。本轮把 summary 接入 eval run comparison，让跨 run 对比能发现 schema repair hint recovery 的退化。

对 9B/flash 小模型来说，单次 run 达标还不够。真正需要的是持续防回归：如果新版本 harness、profile、prompt 或工具 schema 让 hint recovery rate 下降，comparison 应该报告并阻断 release profile。

## 已完成变更

1. `compare_eval_runs` 新增 `summary_diff`。

当前包含：

- `schema_repair_hint_recovery_rate`
- `schema_repair_hint_failures`
- `schema_repair_hint_type_failure_deltas`
- `schema_repair_hint_type_failure_increases`

2. `comparison.json` 新增 `summary_diff`。

3. `comparison.md` 新增 `## Summary Drift`。

展示：

- schema repair hint recovery rate 变化
- schema repair hint failures 变化
- schema repair hint type failure increases

4. release/strict profile 新增 regression reason：

- `schema_repair_hint_recovery_rate_decreased`
- `schema_repair_hint_failures_increased`
- `schema_repair_hint_type_failures_increased`

5. regression reason links 新增 summary drift payload，并在 Markdown 中展示具体 change/changes，避免只显示 `recorded`。

6. 推荐修复动作新增 hint recovery 相关说明。

## 新增测试覆盖

1. baseline hint recovery rate 1.0，current 0.5 时 comparison 记录 regression。
2. hint failure 数增加时 comparison 记录 regression。
3. hint type failure 增加时 comparison 记录 regression。
4. Markdown 输出 `## Summary Drift`。
5. regression reason links 包含 summary change payload。
6. Markdown regression reason links 展示具体 summary delta。
7. 既有 compare tests 保持通过。

## 对 Metis Harness 的意义

这一轮把 schema repair hint recovery 从单 run gate 扩展到跨 run regression 检测。

这对长期目标非常关键：

1. 可以比较不同模型版本的恢复能力。
2. 可以比较不同 prompt/profile 的恢复能力。
3. 可以发现工具 schema 改动后，小模型是否更难修复。
4. 可以把“恢复能力退化”当成 release blocker。

这比只看 success rate 更细，因为 success rate 可能没有变化，但模型可能从“稳定按 hint 修复”退化成“靠运气最终成功”。

## 当前限制

1. comparison 还没有按 tool name 拆分 hint recovery。
2. comparison 还没有按 schema path/schema keyword 拆分。
3. exploratory profile 仍只记录不阻断，这是当前设计，后续可增加 profile-specific summary drift 输出强度。
4. real 9B/flash eval suite 还没有 hint recovery 专项任务。

## 下一步任务

1. real small-model eval suite 增加 hint recovery tasks。
2. comparison report 增加 hint type success/failure 完整表。
3. run manifest 增加 schema version。
4. trace timeline 增加 `schema.repair_hint` event。

## 验证结果

- `python -m pytest tests\unit\test_eval_compare.py tests\unit\test_cli_eval.py -q`
  - 结果：66 passed
- `python -m pytest -q`
  - 结果：306 passed, 4 skipped
- `python -m compileall -q metis`
  - 结果：通过
