# Iteration 071: Schema Repair Hint Trace Events

日期：2026-05-25

## 本轮目标

Iteration 070 已经让 comparison 能发现 schema repair hint recovery 的跨 run 退化。本轮把 schema repair hint 从 tool result metadata 和 eval metrics 继续下沉到 runtime trace。

目标是让每一次“harness 给了小模型什么修复提示”都成为可回放、可定位、可链接的 timeline event。

这对 9B/flash 小模型非常关键。小模型失败时，不能只知道“schema validation failed”，还必须能复盘：

1. 哪个工具调用失败。
2. schema 错误是什么。
3. harness 给了哪些修复提示。
4. hint type 是什么。
5. 这个 hint 和前一个 tool.result event 的关系是什么。
6. 后续模型是否按该 hint 修复成功。

## 已完成变更

1. `AgentLoop` 在带 `schema_repair_hints` 的 tool result 后新增独立 trace event：

   - `event_type`: `schema.repair_hint`
   - `status`: `emitted`
   - `tool_name`
   - `tool_call_id`
   - `attributes.parent_event_id`
   - `attributes.schema_errors`
   - `attributes.schema_repair_hints`
   - `attributes.schema_repair_hint_types`
   - `attributes.schema_repair_hint_details`
   - `attributes.hint_count`

2. `tool.result` 仍保留完整 metadata，保证向后兼容。

3. `schema.repair_hint` event 增加 summary：

   - `schema_repair_hint_types=add_required_property`
   - `schema_repair_hint_types=remove_additional_property`
   - 多类型时用逗号连接。

4. `timeline_to_markdown` 新增 schema repair hint summary 渲染。

   现在 CLI trace table 会直接显示：

   - event type
   - status
   - tool
   - hint types

5. integration 测试覆盖：

   - 缺必填参数后生成 `schema.repair_hint`。
   - 额外参数后生成 `schema.repair_hint`。
   - event 关联 tool name、tool call id、parent event id。
   - event 保留 hint details。

6. timeline unit 测试覆盖：

   - Markdown 能展示 `schema.repair_hint` 的 hint type summary。

## 对 Metis Harness 的意义

这一轮把 schema repair hint 从“结果字段”变成“运行轨迹事件”。

区别很大：

1. 结果字段适合统计。
2. trace event 适合回放。
3. event id 可以作为 repair task 的锚点。
4. dashboard 可以按 event 展示模型收到的具体修复提示。
5. comparison/diagnosis 可以把回归原因链接到具体 hint event，而不是只链接整份 artifact。

这进一步推动 Metis 成为通用智能体 harness，而不是单场景 agent 工具箱。未来不同场景智能体只要接入同一运行循环，就能获得统一的 schema repair trace、eval、gate 和 regression 机制。

## 当前限制

1. `schema.repair_hint` event 还没有被 failure artifact diagnosis 直接引用。
2. repair task 还没有直接绑定到 `schema.repair_hint` event id。
3. timeline Markdown 仍是文本表格，还没有 HTML/dashboard 视图。
4. hint event 还没有按 tool/schema path/schema keyword 汇总成独立 dashboard 指标。
5. real 9B/flash eval suite 还没有专门断言 trace event 存在。

## 下一步任务

1. repair task 生成器优先锚定 `schema.repair_hint` event。
2. comparison reason links 增加 timeline event id 级别链接。
3. failure diagnosis 增加 schema repair hint event 摘要。
4. real small-model eval suite 增加 hint recovery trace 任务。
5. trace dashboard 增加 schema repair hint 分组视图。

## 验证结果

- `python -m pytest tests\integration\test_agent_loop_schema_guard.py tests\unit\test_timeline.py -q`
  - 结果：16 passed
- `python -m pytest tests\integration\test_agent_loop_schema_guard.py tests\unit\test_timeline.py tests\unit\test_eval_runner.py -q`
  - 结果：52 passed
- `python -m pytest -q`
  - 结果：307 passed, 4 skipped
- `python -m compileall -q metis`
  - 结果：通过
