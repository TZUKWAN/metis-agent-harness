# Iteration 073: Schema Repair Hint Diagnosis Summary

日期：2026-05-25

## 本轮目标

Iteration 071/072 已经完成两步：

1. runtime trace 生成 `schema.repair_hint` event。
2. repair task 的 `critical_event_ids` 可以优先锚定 `schema.repair_hint`。

本轮继续把这条链路向前推进：让 comparison diagnosis 直接提取 `schema.repair_hint` event 的摘要。

目标是让 diagnosis 不只是告诉人“看这个 timeline”，而是直接告诉人和自动化系统：

1. 哪个 task 出现 schema repair hint。
2. hint event id 是什么。
3. parent tool-result event id 是什么。
4. tool name 和 tool call id 是什么。
5. schema errors 是什么。
6. hint types 是什么。
7. hint text 是什么。
8. hint details 里有哪些 schema path 和 schema keyword。

## 外部参考

本轮检索了当前 agent observability/eval 方向：

1. OpenTelemetry GenAI semantic conventions 强调用事件和属性记录模型、工具调用和系统自定义语义。
2. LangChain/LangSmith agent eval 文档强调评估 trajectory，也就是消息和工具调用序列，而不是只看最终输出。
3. OpenAI Evals 强调可复用、自定义 eval，使失败行为能够沉淀成回归套件。

Metis 当前做法与这些方向一致，但更面向小模型 harness：把 schema repair hint 作为可回放、可诊断、可转 eval 的一等事件。

## 已完成变更

1. `eval_run_comparison_diagnosis()` 新增 `schema_repair_hint_events`。

每个 diagnosis entry 会按 task id 汇总 timeline 中的 `schema.repair_hint`：

```json
{
  "a": [
    {
      "event_id": "a:002:schema.repair_hint",
      "parent_event_id": "a:001:tool.result",
      "tool_name": "write_file",
      "tool_call_id": "c1",
      "schema_errors": ["$.path: missing required property"],
      "hint_types": ["add_required_property"],
      "hints": ["Add the required argument $.path."],
      "hint_details": [
        {
          "hint_type": "add_required_property",
          "schema_path": "$.path",
          "schema_keyword": "required"
        }
      ]
    }
  ]
}
```

2. `eval_run_diagnosis_to_markdown()` 展示 schema repair hint event 摘要。

示例：

```text
Schema repair hint events: a=a:002:schema.repair_hint(add_required_property)
```

3. `build_repair_tasks_from_diagnosis()` 保留 `schema_repair_hint_events`。

这样后续 targeted eval stub 生成器不需要重新读取 timeline，就能直接消费 hint payload。

4. 新增单元测试覆盖：

   - diagnosis 从 timeline 读取 `schema.repair_hint`。
   - 摘要保留 `event_id`、`parent_event_id`、`hint_types`、`hints`、`hint_details`。
   - Markdown 展示 hint event。
   - repair task 继承 hint event 摘要。

## 对 Metis Harness 的意义

这一轮把 trace event 接入 diagnosis payload。

这意味着 Metis 的失败修复链路现在更完整：

```text
schema invalid tool call
-> tool.result metadata
-> schema.repair_hint trace event
-> critical_event_ids anchor
-> diagnosis schema_repair_hint_events
-> repair task schema_repair_hint_events
-> future targeted eval stub
```

这对 9B/flash 模型特别重要，因为小模型需要 harness 把错误变成明确、短、可执行、可评测的修复动作。

## 当前限制

1. targeted eval stub 还没有读取 `schema_repair_hint_events` 来生成 schema repair 专项 eval。
2. repair plan 还没有按 hint type 聚合 schema 类任务。
3. comparison reason links 还没有直接暴露 event-level references。
4. real 9B/flash eval suite 还没有断言 diagnosis 中必须出现 hint event 摘要。

## 下一步任务

1. targeted eval stub 从 `schema_repair_hint_events` 中生成更具体的 repair eval skeleton。
2. repair plan 按 hint type 汇总 schema repair 任务。
3. comparison reason links 增加 event-level references。
4. real small-model eval suite 增加 hint diagnosis trace 任务。

## 验证结果

- `python -m pytest tests\unit\test_eval_compare.py -q`
  - 结果：32 passed
- `python -m pytest tests\unit\test_eval_compare.py tests\unit\test_timeline.py tests\integration\test_agent_loop_schema_guard.py -q`
  - 结果：49 passed
- `python -m pytest -q`
  - 结果：310 passed, 4 skipped
- `python -m compileall -q metis`
  - 结果：通过
