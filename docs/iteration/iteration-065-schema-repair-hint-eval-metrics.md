# Iteration 065: Schema Repair Hint Eval Metrics

日期：2026-05-25

## 本轮目标

Iteration 064 已经让 schema validation failure 返回 `schema_repair_hints`。本轮把这个能力纳入评测体系，避免它只是运行时反馈，而无法被量化、对比和 gate。

面向 9B/flash 小模型，核心问题不是“是否曾经失败”，而是：

1. 失败时 harness 是否给出了具体修复提示。
2. 模型收到提示后是否完成了恢复。
3. 未恢复的 hint failure 是否能在 eval report 中被定位。

## 已完成变更

1. 新增 `metis.tools.schema_feedback.schema_repair_hints`。
   - 把 schema error 到修复 hint 的转换从 `AgentLoop` 中抽出为工具层 helper。
   - `ToolDispatcher` 在 schema validation failure 时直接写入 `metadata["schema_repair_hints"]`。
   - 这样 trace、tool result excerpt、EvalRunner 都能看到同一份 hint 数据。

2. `AgentLoop` 继续在 tool feedback 中输出 `schema_repair_hints`。
   - 如果 dispatcher 已经写入 metadata，直接复用。
   - 如果历史结果缺少 metadata，则按 `schema_errors` 现算，保持兼容。

3. `EvalResult` 新增指标：
   - `schema_repair_hints_seen`
   - `schema_repair_hint_successes`
   - `schema_repair_hint_failures`

4. `EvalTaskSpec` 新增 gate 字段：
   - `min_schema_repair_hint_successes`
   - `max_schema_repair_hint_failures`

5. Eval markdown 表格、failure artifact metrics、tool result excerpts 均包含新指标或 hint metadata。

6. Suite validation 已把新增 gate 字段纳入整数/非负校验。

## 新增测试覆盖

1. dispatcher schema failure 会把 `schema_repair_hints` 写进 ToolResult metadata。
2. EvalRunner 可以统计带 hint 的 schema repair：
   - seen = 1
   - successes = 1
   - failures = 0
3. EvalRunner 可以用 `min_schema_repair_hint_successes` 和 `max_schema_repair_hint_failures` gate 任务。
4. unrecovered schema hint 会让任务失败，并输出明确的 gate 错误。
5. tool result excerpt 会保留 `schema_repair_hints`，便于失败诊断。

## 对 Metis Harness 的意义

这一步让“给小模型反馈”变成可度量能力。

没有这个指标时，我们只能知道 schema repair 成功或失败，但不知道成功是否发生在 harness 给出明确修复 hint 之后。现在可以开始回答更关键的问题：

1. 哪类 schema hint 最有用。
2. 哪类 hint 小模型仍然修不好。
3. 提示越具体，是否真的提高恢复率。
4. 新模型、新 profile、新 prompt 是否改善了 hint recovery。

这对逼近高端 Codex/GPT 风格 agent 的关键路径很重要：强模型可能一次写对；小模型必须依赖运行时契约、结构化错误、可操作反馈和 eval 闭环。

## 剩余问题

1. 还没有按 hint 类型拆分指标，例如 `additional_property_removed`、`missing_required_added`、`empty_array_fixed`。
2. 还没有把 hint recovery rate 汇总到 suite-level metadata。
3. 真实 9B/flash eval suite 还没有包含专门的 hint recovery 任务。
4. failure clustering 仍主要看原始 schema error，尚未使用 hint 类型归类。
5. trace timeline 虽然能通过 tool result metadata 看到 hint，但还没有单独的 `schema.repair_hint` event。

## 下一步任务

1. 在 real small-model eval suite 中增加两个 hint recovery 任务：
   - 额外参数删除。
   - 空命令数组修复。
2. 增加 suite-level 汇总：
   - schema repair hint recovery rate
   - hint failure rate
   - hint type distribution
3. 把 schema repair hint 类型稳定化，形成 failure cluster key。
4. 在 trace timeline 中增加专门的 hint event，便于可视化排查。

## 验证结果

- `python -m pytest tests\unit\test_eval_runner.py tests\unit\test_tools.py tests\integration\test_agent_loop_schema_guard.py tests\unit\test_eval_suite_validation.py -q`
  - 结果：71 passed
- `python -m compileall -q metis`
  - 结果：通过

