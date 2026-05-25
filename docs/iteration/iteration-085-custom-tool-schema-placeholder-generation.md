# Iteration 085: Custom Tool Schema Placeholder Generation

日期：2026-05-25

## 本轮目标

Iteration 077 让 schema repair placeholder 能读取内置工具 schema。但 Metis 的目标是通用 harness，不是只服务内置工具。真实业务智能体一定会定义自己的工具，例如 CRM、合同、计划书、报表、检索、审批、知识库等工具。

本轮目标是让 targeted eval stub generation 能使用 repair task 或 hint event 携带的 custom tool schema，生成 schema-compatible corrected arguments。

## 外部参考结论

本轮检索了 OpenAI Evals 和 OpenAI Agents SDK 工具资料，关键结论：

1. Evals 的 custom data source 依赖 schema 定义评测数据形状。
2. Agents SDK function tools 以工具名、描述、参数 JSON schema 和执行函数为核心。
3. 自定义工具参数 schema 是 agent harness 的基础协议，而不是内置工具的附属功能。

因此 Metis 的 repair/eval 链路必须允许 suite 或 repair task 携带业务工具 schema。

## 已完成变更

1. repair task 支持顶层 `tool_schemas`。

示例：

```json
{
  "tool_schemas": {
    "crm_update": {
      "type": "object",
      "properties": {
        "customer_id": {"type": "integer", "minimum": 1000},
        "status": {"type": "string", "enum": ["qualified", "nurture"]}
      }
    }
  }
}
```

2. schema repair hint event 支持 event-level schema：

- `tool_schema`
- `parameters`

event-level schema 优先于 task-level `tool_schemas`。

3. placeholder schema resolution 优先级：

```text
event.tool_schema / event.parameters
-> task.tool_schemas[tool_name]
-> builtin tool schema
-> fallback placeholder heuristics
```

4. `build_eval_stubs_from_repair_tasks()` 生成的 stub 会保留 `tool_schemas`。

5. 新增测试：

- custom `crm_update.customer_id` 使用 integer minimum 生成 `1000`；
- custom `crm_update.status` 使用 enum 生成 `qualified`；
- `required_tool_arguments` 从 custom corrected arguments 派生；
- event-level `tool_schema` 会覆盖 task-level schema。

## 对 Metis Harness 的意义

这一步把 schema repair eval 从“Metis 内置工具回归”推进到“业务工具可扩展回归”。

对 9B/flash 模型很关键：

1. 小模型对业务工具参数更容易出错。
2. harness 必须用 schema 帮模型把错误收束到可恢复范围。
3. targeted eval 必须覆盖场景工具，而不是只覆盖 read/write/run command。
4. corrected placeholder 必须按业务 schema 生成，否则 eval gate 会失真。

## 当前限制

1. `tool_schemas` 还只存在于 repair task/stub metadata，没有写入 materialized suite wrapper。
2. suite-level `tool_schemas` 尚未定义。
3. custom schema 还没有进入 suite schema v1 JSON snapshot。
4. schema 引用、`$defs`、嵌套 object 还没有完整展开支持。
5. 没有把 custom tool schemas 传给 real provider eval runner 的 validation context。

## 下一步任务

1. materialized suite 保留 task/stub `tool_schemas`。
2. suite schema v1 文档和 JSON snapshot 增加 `tool_schemas`。
3. validation report 增加 suite schema snapshot id/hash。
4. release gate 增加 unversioned suite 策略。
5. custom tool schema 接入 generic eval validation context。

## 验证结果

- `python -m pytest tests\unit\test_eval_compare.py -q`
  - 结果：37 passed
- `python -m pytest tests\unit\test_eval_compare.py tests\unit\test_cli_eval.py tests\unit\test_eval_runner.py tests\unit\test_eval_suite_run.py tests\unit\test_eval_suite_validation.py -q`
  - 结果：132 passed
- `python -m pytest -q`
  - 结果：320 passed, 4 skipped
- `python -m compileall -q metis`
  - 结果：通过
