# Iteration 072: Schema Repair Hint Repair Task Anchors

日期：2026-05-25

## 本轮目标

Iteration 071 已经把 `schema.repair_hint` 写入 runtime trace。仅有 trace event 还不够，自动修复链路必须优先把 repair task 锚定到真正可修复的事件。

本轮目标是让 repair task 的 `critical_event_ids` 在 schema hint 场景中指向 `schema.repair_hint`，而不是只指向泛化的 failed `tool.result`。

## 已完成变更

1. `select_critical_event()` 新增 schema repair hint 优先级。

当前优先级：

1. failed finalization event
2. `schema.repair_hint`
3. failed `tool.result`
4. failed parser/finalization repair event
5. explicit error event
6. 最后一个 event fallback

2. `critical_event_id()` 自动继承新策略。

3. `build_repair_tasks_from_diagnosis()` 无需改变外部 schema，继续通过 `_critical_event_ids_for_paths()` 获取关键事件，但现在 schema repair 类 timeline 会锚定 hint event。

4. 新增 timeline unit 测试：

   - 当 timeline 同时包含 failed `tool.result` 和 `schema.repair_hint` 时，critical event 选择 `schema.repair_hint`。

5. 新增 repair task 测试：

   - repair task 保留完整 `timeline_event_ids`。
   - `critical_event_ids` 指向 `a:002:schema.repair_hint`。

## 对 Metis Harness 的意义

这一步把“可观察事件”接入“可执行修复任务”。

对 9B/flash 小模型来说，很多失败不是工具真的不可用，而是模型第一次传错参数。harness 已经能给出修复提示，但后续自动诊断如果只锚定 `tool.result`，修复任务仍然偏粗。

现在 repair task 可以指向：

1. 失败工具调用。
2. harness 给出的具体 schema hint。
3. hint type 和 hint details。
4. 后续 targeted eval 应该覆盖的修复点。

这会降低人工排查成本，也让后续自动生成 repair eval 时更容易生成“先犯错，再收到 hint，再成功重试”的任务。

## 当前限制

1. diagnosis entry 还没有直接展示 schema repair hint event 摘要。
2. targeted eval stub 还没有从 `schema.repair_hint` payload 中生成更具体的 malformed/corrected 参数模板。
3. comparison reason links 还没有直接携带 timeline event id。
4. dashboard 还没有按 hint event 聚合失败。

## 下一步任务

1. failure diagnosis 增加 schema repair hint event 摘要。
2. targeted eval stub 从 hint event 中提取 hint type、schema path、schema keyword。
3. comparison reason links 增加 event-level references。
4. repair plan 按 `schema.repair_hint` 类型排序 schema 类任务。

## 验证结果

- `python -m pytest tests\unit\test_timeline.py tests\unit\test_eval_compare.py -q`
  - 结果：38 passed
- `python -m pytest -q`
  - 结果：309 passed, 4 skipped
- `python -m compileall -q metis`
  - 结果：通过
