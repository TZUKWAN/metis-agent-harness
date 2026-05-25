# Iteration 066: Typed Schema Repair Hints and Clustering

日期：2026-05-25

## 本轮目标

Iteration 065 已经把 `schema_repair_hints` 纳入 eval metrics，但 hints 仍主要是文本和并行类型数组。本轮把 schema repair hint 升级为更稳定的结构化对象，并让 failure clustering 能消费 hint 类型。

目标是避免后续诊断依赖原始 schema error 文本。对 9B/flash 小模型来说，我们需要长期追踪：

1. 哪类 schema repair hint 最常出现。
2. 哪类 hint 最常恢复失败。
3. 哪个 schema path 和 keyword 反复造成问题。
4. 哪类工具 schema 或提示语需要优先改。

## 已完成变更

1. `metis.tools.schema_feedback` 新增 canonical detail 结构。

`schema_repair_feedback(schema_errors)` 现在返回：

- `hints`
- `hint_types`
- `details`

其中 `details` 的单项结构为：

- `hint_type`
- `schema_path`
- `schema_keyword`
- `schema_error`
- `hint_text`

2. 保留兼容 API。

- `schema_repair_hints(schema_errors)`
- `schema_repair_hint_types(schema_errors)`
- `schema_repair_hint_details(schema_errors)`

3. Dispatcher metadata 新增：

- `schema_repair_hint_details`

4. AgentLoop tool feedback 新增：

- `schema_repair_hint_details`

5. EvalRunner tool result excerpt 新增：

- `schema_repair_hint_details`

6. EvalResult 已能保留按 hint type 的统计：

- `schema_repair_hint_types_seen`
- `schema_repair_hint_type_successes`
- `schema_repair_hint_type_failures`

7. Failure clustering 新增 hint 类型维度。

新增 cluster key：

- `schema_repair_hint_type:{hint_type}`
- `schema_repair_hint_failure_type:{hint_type}`
- `schema_repair_hint_path:{hint_type}:{normalized_schema_path}`

新增 signals：

- `schema_repair_hint_type:{hint_type}={count}`
- `schema_repair_hint_failure_type:{hint_type}={count}`
- `schema_repair_hint_detail={hint_type}@{schema_path}:{schema_keyword}`

## 新增测试覆盖

1. `schema_repair_feedback` 返回稳定类型、自然语言 hint 和 canonical details。
2. dispatcher schema failure metadata 包含 hint type 和 detail。
3. AgentLoop 返回给模型的 tool feedback 包含 hint type 和 detail。
4. EvalRunner excerpt 保留 hint detail。
5. Failure clustering 能按 hint type、hint failure type、hint path 聚类。
6. Remediation backlog 对 hint failure type 标记 critical。

## 对 Metis Harness 的意义

这一轮把 schema repair 从“人读文本”推进到“机器可审计 taxonomy”。

这对长期目标很关键：

1. 9B 模型的主要价值不在一次写对，而在收到 harness feedback 后稳定修复。
2. 稳定 hint type 可以跨模型、跨任务、跨版本比较恢复能力。
3. Failure clustering 可以直接告诉我们“哪类修复提示没用”，而不是只看到一堆 schema error 文本。
4. 后续可以按 hint type 自动生成 targeted eval、repair prompt、tool schema examples。

## 当前限制

1. detail 字段还没有解析出 `expected_type`、`actual_type`、`constraint_value`、`allowed_values`。
2. `schema_repair_hint_path` 聚类可能会因为 path 过细导致碎片化，所以目前只作为辅助 cluster。
3. Eval markdown 还没有专门展示按 hint type 的汇总表。
4. suite-level hint recovery rate 仍未实现。
5. trace timeline 还没有独立 `schema.repair_hint` event。

## 下一步任务

1. 增加 suite-level hint recovery summary。
2. 增加 real 9B/flash hint recovery eval tasks。
3. 扩展 detail parser，提取 expected/actual/constraint/allowed values。
4. 给 `schema_repair_hint_failure_type:*` 自动生成 targeted repair stubs。
5. 把 hint type distribution 写入 markdown report 和 comparison report。

## 验证结果

- `python -m pytest tests\unit\test_schema_feedback.py tests\unit\test_tools.py tests\integration\test_agent_loop_schema_guard.py tests\unit\test_eval_runner.py tests\unit\test_failure_clusters.py -q`
  - 结果：63 passed
- `python -m compileall -q metis`
  - 结果：通过

