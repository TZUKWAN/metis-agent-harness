# Iteration 064: Schema Repair Hints and Loop Coverage

日期：2026-05-25

## 本轮目标

上一轮已经把工具 schema validator 做严格了，但严格拦截只是第一步。面向 9B/flash 小模型，真正重要的是：模型第一次工具调用错了以后，harness 能不能给出足够清晰、结构化、可执行的反馈，让模型第二次把参数修正回来。

本轮专门补这个闭环：严格 schema failure -> 结构化 repair feedback -> 模型修正工具调用 -> 工具调用成功 -> 最终输出。

## 已完成变更

1. `AgentLoop._tool_feedback_content` 在 schema validation failure 时新增 `schema_repair_hints`。

2. `schema_repair_hints` 不替代原始 `schema_errors`，而是从常见 schema error 中提取动作型提示：
   - 额外参数：删除不支持的参数。
   - 缺必填参数：补齐必填参数。
   - 类型错误：按 schema 类型重写该字段。
   - 空数组/数组过短：提供足够的数组元素。
   - 数组过长：减少数组元素。
   - 数值越界：增大或减小数值以满足边界。
   - 正则不匹配：按要求重写字符串。
   - enum 不匹配：使用允许的枚举值。
   - oneOf 不匹配：确保只有一个 schema 分支匹配。

3. 新增 agent loop 集成测试：额外参数修复。
   - 第一次调用 `read_file` 多传 `url`。
   - schema guardrail 阻断。
   - feedback 中包含 `schema_repair_hints: ["Remove the unsupported argument at $.url."]`。
   - 第二次调用删除 `url` 后成功。

4. 新增 agent loop 集成测试：空命令数组修复。
   - 第一次调用 `run_command` 传 `command: []`。
   - schema guardrail 阻断。
   - feedback 中包含空数组修复提示。
   - 第二次调用 `command: ["python", "--version"]` 成功。

5. 扩展既有 schema repair 测试。
   - 缺失必填 `path` 时，feedback 现在包含 `Add the required argument $.path.`。

## 对 Metis Harness 的意义

这一步把“严格工具参数验证”推进为“可恢复的工具参数验证”。对小模型非常关键：

1. 小模型不一定一次写对工具参数。
2. 但只要 feedback 清晰，它往往能第二次修正。
3. harness 的价值就是把模糊失败转成结构化、可操作的下一步。
4. 这比单纯提高 prompt 更可靠，因为它在运行时检查真实工具调用，并用真实错误驱动修复。

## 当前限制

1. `schema_repair_hints` 仍是基于错误字符串的轻量转换，不是完整 schema-aware planner。
2. 对 `oneOf` 的提示还没有选择“最接近分支”。
3. 对嵌套对象的修复提示还比较粗。
4. 还没有把这些 repair hint 指标接入 eval report，例如统计 hint 后的恢复成功率。
5. 真实 9B/flash API eval 还没有专门任务验证“额外参数/空数组 -> repair -> 成功”。

## 下一步任务

1. 在 real small-model eval suite 中加入两类真实任务：
   - 多传参数后删除额外参数。
   - 空命令数组后改成合法命令。
2. 给 EvalRunner 增加 `schema_repair_hints_seen` 和 `schema_repair_hint_recovered` 指标。
3. 把 schema repair hint 写入 trace timeline，便于失败诊断。
4. 将 `oneOf` 分支错误转成更具体的候选修复建议。
5. 给 schema error 建立稳定分类，避免 failure shape key 过长。

## 验证结果

- `python -m pytest tests\integration\test_agent_loop_schema_guard.py tests\unit\test_tools.py tests\unit\test_tool_schema_validator.py -q`
  - 结果：35 passed
- `python -m compileall -q metis`
  - 结果：通过

