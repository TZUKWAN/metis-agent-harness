# Metis Agent Harness 详细任务清单

生成时间：2026-05-25  
目标目录：`D:\LATEXTEST\metis-agent-harness`  
依据文档：

- `Metis-Agent-Harness-架构抽取与设计报告.md`
- `Metis-Agent-Harness-构建方案.md`

---

## 1. 使用说明

本文档是 Metis Agent Harness 的开发任务清单，不是架构说明文档。它的用途是把构建方案拆成可以逐项执行、逐项验收、逐项测试的任务。

每个任务包含：

- 任务编号
- 任务名称
- 目标
- 输入依赖
- 具体工作
- 输出产物
- 验收标准
- 测试要求
- 阻塞关系

任务状态建议使用：

- `TODO`
- `IN_PROGRESS`
- `BLOCKED`
- `DONE`
- `DEFERRED`

默认优先级：

- P0：没有它系统不能跑。
- P1：核心 harness 能力。
- P2：生产级稳定性。
- P3：扩展能力。

---

## 2. 总体阶段拆分

| 阶段 | 名称 | 目标 | 优先级 |
|---|---|---|---|
| Phase 0 | 项目初始化 | 建立 Python 包、文档、基础测试框架 | P0 |
| Phase 1 | Runtime Kernel | 跑通最小模型工具循环 | P0 |
| Phase 2 | State + Task Harness | 让复杂任务状态化、步骤化 | P0 |
| Phase 3 | Context + Tool Result Budget | 控制上下文和大工具输出 | P1 |
| Phase 4 | Artifact + Evidence + Quality | 保证真实产物和验收 | P1 |
| Phase 5 | Small Model Mode | 让 9B 模型稳定执行 | P1 |
| Phase 6 | Recovery + Security | 恢复、安全、路径边界 | P1 |
| Phase 7 | Loop + Scheduler | 支持自动循环和定时任务 | P2 |
| Phase 8 | Swarm + Auditor | 支持多智能体和审核团队 | P2 |
| Phase 9 | Skills + Plugins | 支持可复用流程和扩展 | P3 |
| Phase 10 | Adapters | 接入 Aurora / Sophia | P3 |
| Phase 11 | Evaluation + Hardening | 评测、压力测试、文档完善 | P2 |

---

## 3. Phase 0：项目初始化

### M0.1 创建项目基础结构

状态：DONE  
优先级：P0  
目标：建立 Metis Python 包的基础目录。

输入依赖：

- 当前目录：`D:\LATEXTEST\metis-agent-harness`

具体工作：

1. 创建 `metis/` 包目录。
2. 创建 `tests/` 测试目录。
3. 创建 `docs/` 文档目录。
4. 创建基础子目录：
   - `metis/runtime`
   - `metis/events`
   - `metis/providers`
   - `metis/tools`
   - `metis/state`
   - `metis/planning`
   - `metis/context`
   - `metis/memory`
   - `metis/artifacts`
   - `metis/evidence`
   - `metis/quality`
   - `metis/recovery`
   - `metis/security`
   - `metis/loops`
   - `metis/swarm`
   - `metis/skills`
   - `metis/plugins`
   - `metis/telemetry`
   - `metis/adapters`
5. 每个包目录增加 `__init__.py`。

输出产物：

- Python 包骨架。

验收标准：

- `python -c "import metis"` 成功。
- `rg --files metis` 能列出基础包文件。

测试要求：

- 暂无业务测试。
- 做一次 import smoke test。

阻塞关系：

- 阻塞所有后续开发任务。

---

### M0.2 创建 `pyproject.toml`

状态：DONE  
优先级：P0  
目标：定义项目元数据、依赖、测试命令。

输入依赖：

- M0.1

具体工作：

1. 设置项目名：`metis-agent-harness`。
2. 设置 Python 版本：建议 `>=3.11`。
3. 添加基础依赖：
   - `pydantic` 或 dataclasses 方案二选一；初始可不用 pydantic。
   - `pytest`
   - `pytest-asyncio`
   - `httpx`
4. 添加可选依赖：
   - `openai`
   - `anthropic`
   - `tiktoken`
5. 配置 pytest。
6. 配置 ruff/black 可选。

输出产物：

- `pyproject.toml`

验收标准：

- `python -m pytest --version` 可用。
- `pip install -e .` 成功。

测试要求：

- 安装后 import metis 成功。

阻塞关系：

- 阻塞自动化测试。

---

### M0.3 创建基础 README

状态：DONE  
优先级：P1  
目标：写清楚项目定位和当前阶段。

输入依赖：

- 架构报告
- 构建方案

具体工作：

1. 写项目定位。
2. 写非目标：
   - 不是业务智能体。
   - 不是聊天 UI。
   - 不是某个特定领域工具。
3. 写目录说明。
4. 写开发阶段。
5. 写最小运行命令占位。

输出产物：

- `README.md`

验收标准：

- README 能让开发者理解 Metis 是 harness。

测试要求：

- 文档检查。

阻塞关系：

- 不阻塞核心代码。

---

### M0.4 初始化测试结构

状态：DONE  
优先级：P0  
目标：建立单元、集成、端到端测试目录。

具体工作：

1. 创建：
   - `tests/unit`
   - `tests/integration`
   - `tests/e2e`
   - `tests/fixtures`
2. 添加 `tests/unit/test_import.py`。
3. 添加 pytest marker：
   - unit
   - integration
   - e2e
   - local_model
   - network

输出产物：

- 测试目录。
- 基础 import 测试。

验收标准：

- `python -m pytest -q` 至少有 1 个测试通过。

测试要求：

- 必须跑通。

阻塞关系：

- 阻塞后续测试驱动开发。

---

## 4. Phase 1：Runtime Kernel

### M1.1 实现 HookBus

状态：DONE  
优先级：P0  
目标：实现事件注册、触发、优先级、阻断。

输入依赖：

- M0.1
- M0.4

具体工作：

1. 创建 `metis/events/event_types.py`。
2. 创建 `metis/events/hooks.py`。
3. 定义基础事件常量：
   - `agent.pre_run`
   - `agent.post_run`
   - `agent.error`
   - `model.pre_call`
   - `model.post_call`
   - `tool.pre_dispatch`
   - `tool.post_dispatch`
   - `tool.error`
   - `quality.passed`
   - `quality.failed`
4. 实现 `HookBus.register(event, handler, priority, name)`。
5. 实现 `HookBus.emit(event, context)`。
6. 支持 handler 返回新 context。
7. 支持 `context["blocked"] = True` 后停止后续 handler。
8. handler 抛异常不能导致主流程崩溃，必须记录到 context 或日志。

输出产物：

- `metis/events/event_types.py`
- `metis/events/hooks.py`

验收标准：

- handler 按 priority 顺序执行。
- blocked 生效。
- handler 异常被隔离。

测试要求：

- `tests/unit/test_hooks.py`
  - test_priority_order
  - test_blocked_stops_chain
  - test_exception_isolated
  - test_remove_hook
  - test_list_hooks

阻塞关系：

- 阻塞 ToolRegistry、Trajectory、QualityGate、Recovery。

---

### M1.2 定义 Runtime 数据结构

状态：DONE  
优先级：P0  
目标：定义 AgentLoop 所需基础 dataclass。

输入依赖：

- M0.1

具体工作：

1. 创建 `metis/runtime/response.py`。
2. 定义：
   - `ToolCall`
   - `ToolResult`
   - `NormalizedResponse`
   - `AgentRunRequest`
   - `AgentRunResult`
3. 创建 `metis/runtime/errors.py`。
4. 定义：
   - `MetisError`
   - `ProviderError`
   - `ToolDispatchError`
   - `ParserError`
   - `QualityGateError`

输出产物：

- runtime dataclasses。

验收标准：

- 类型可 import。
- 字段满足构建方案。

测试要求：

- `tests/unit/test_runtime_models.py`

阻塞关系：

- 阻塞 provider、parser、agent loop。

---

### M1.3 实现 ToolSpec

状态：DONE  
优先级：P0  
目标：定义工具元数据结构。

输入依赖：

- M1.2

具体工作：

1. 创建 `metis/tools/spec.py`。
2. 定义 `ToolSpec`。
3. 定义 `ToolContext`。
4. 定义 side effect 枚举或字符串约束：
   - read
   - write
   - network
   - destructive
5. 定义默认工具结果限制字段。

输出产物：

- `metis/tools/spec.py`

验收标准：

- ToolSpec 能表达 name、description、parameters、handler、category、side_effect、max_result_chars。

测试要求：

- `tests/unit/test_tool_spec.py`

阻塞关系：

- 阻塞 ToolRegistry。

---

### M1.4 实现 ToolRegistry

状态：DONE  
优先级：P0  
目标：实现工具注册、schema 生成、工具列表。

输入依赖：

- M1.1
- M1.3

具体工作：

1. 创建 `metis/tools/registry.py`。
2. 实现 `register(spec)`。
3. 实现重复工具名处理：
   - 默认报错或显式 overwrite。
4. 实现 `get(name)`。
5. 实现 `list_tools()`。
6. 实现 `schemas(filter=None, max_tools=None)`。
7. schema 输出 OpenAI function tool 格式。
8. 支持按 category / allowed names / side_effect 过滤。

输出产物：

- `metis/tools/registry.py`

验收标准：

- 注册工具后可生成 OpenAI-compatible schema。
- 可过滤工具。

测试要求：

- `tests/unit/test_tool_registry.py`
  - test_register_tool
  - test_duplicate_tool
  - test_schema_format
  - test_filter_by_names
  - test_filter_by_category

阻塞关系：

- 阻塞 ToolDispatcher、AgentLoop。

---

### M1.5 实现 ToolDispatcher

状态：DONE  
优先级：P0  
目标：执行工具并触发 hook。

输入依赖：

- M1.1
- M1.4

具体工作：

1. 创建 `metis/tools/dispatcher.py`。
2. 实现 `dispatch(tool_call, tool_context)`。
3. dispatch 前 emit `tool.pre_dispatch`。
4. 若 blocked，返回 JSON error。
5. 调用 handler。
6. handler 返回 dict 时转 JSON。
7. handler 返回 str 时保留。
8. 异常时 emit `tool.error`。
9. 成功时 emit `tool.post_dispatch`。
10. 统一返回 `ToolResult`。

输出产物：

- `metis/tools/dispatcher.py`

验收标准：

- 工具成功、失败、blocked 都有结构化结果。

测试要求：

- `tests/unit/test_tool_dispatcher.py`
  - test_dispatch_success
  - test_dispatch_dict_result
  - test_unknown_tool
  - test_blocked_by_hook
  - test_handler_exception
  - test_post_dispatch_hook

阻塞关系：

- 阻塞 AgentLoop。

---

### M1.6 实现 FakeProvider

状态：DONE  
优先级：P0  
目标：为测试提供不依赖真实模型的 provider。

输入依赖：

- M1.2

具体工作：

1. 创建 `metis/providers/base.py`。
2. 定义 `BaseProvider` 接口。
3. 创建 `metis/providers/fake.py`。
4. FakeProvider 支持预置响应队列。
5. 响应可包含：
   - content
   - tool_calls
   - usage
6. 用于单元和集成测试。

输出产物：

- `metis/providers/base.py`
- `metis/providers/fake.py`

验收标准：

- 测试中可设置 provider 依次返回 tool_call 和 final。

测试要求：

- `tests/unit/test_fake_provider.py`

阻塞关系：

- 阻塞 AgentLoop 测试。

---

### M1.7 实现 OpenAI-compatible Provider

状态：DONE  
优先级：P0  
目标：连接 OpenAI-compatible API。

输入依赖：

- M1.2
- M1.6

具体工作：

1. 创建 `metis/providers/openai_compat.py`。
2. 支持 `base_url`、`api_key`、`model`。
3. 支持传入 messages 和 tools。
4. 解析 native tool_calls。
5. 提取 usage。
6. 归一化为 `NormalizedResponse`。
7. 网络异常转 `ProviderError`。

输出产物：

- `metis/providers/openai_compat.py`

验收标准：

- 在有 API 配置时能完成一次 chat completion。
- 无配置时测试可跳过。

测试要求：

- unit：mock client。
- integration：可选真实 endpoint。

阻塞关系：

- 阻塞真实模型测试。

---

### M1.8 实现 Tool Call Parser 链

状态：DONE  
优先级：P0  
目标：支持 native 与文本工具调用格式。

输入依赖：

- M1.2

具体工作：

1. 创建 `metis/providers/parsers/base.py`。
2. 创建 `openai_native.py`。
3. 创建 `hermes_xml.py`。
4. 创建 `json_block.py`。
5. 创建 `repair.py` 初版。
6. 支持解析：
   - native tool_calls
   - `<tool_call>{...}</tool_call>`
   - fenced json
   - raw json
7. 解析失败返回 ParserError，不直接崩溃。

输出产物：

- parser 模块。

验收标准：

- 能解析 4 种工具调用格式。
- 错误 JSON 有明确错误。

测试要求：

- `tests/unit/test_tool_call_parsers.py`
  - test_openai_native
  - test_hermes_xml
  - test_json_block
  - test_raw_json
  - test_invalid_json

阻塞关系：

- 阻塞 Small Model Mode。

---

### M1.9 实现 AgentLoop 最小版

状态：DONE  
优先级：P0  
目标：跑通多轮模型工具调用循环。

输入依赖：

- M1.1
- M1.2
- M1.4
- M1.5
- M1.6
- M1.8

具体工作：

1. 创建 `metis/runtime/loop.py`。
2. 实现 `AgentLoop.run(request)`。
3. 每轮调用 provider。
4. 若有 tool_calls，dispatch 工具。
5. 将工具结果加入 messages。
6. 若无 tool_calls，返回 final。
7. 支持 max_turns。
8. 记录 turns_used。
9. emit model pre/post/error hook。

输出产物：

- `metis/runtime/loop.py`

验收标准：

- FakeProvider 第 1 轮返回工具调用，第 2 轮返回 final，AgentLoop 成功结束。
- max_turns 生效。

测试要求：

- `tests/integration/test_agent_loop_fake.py`
  - test_single_tool_then_final
  - test_multiple_tools_then_final
  - test_max_turns
  - test_tool_error_continues

阻塞关系：

- 阻塞所有上层 harness。

---

### M1.10 创建最小 CLI

状态：DONE  
优先级：P1  
目标：提供手动运行入口。

输入依赖：

- M1.9

具体工作：

1. 创建 `metis/adapters/cli.py`。
2. 支持命令：
   - `metis run "task"`
   - `metis doctor`
3. run 命令加载配置。
4. 注册基础工具。
5. 调用 AgentLoop。

输出产物：

- CLI 入口。

验收标准：

- `python -m metis.adapters.cli doctor` 可运行。
- `metis run` 可用 FakeProvider 或真实 provider。

测试要求：

- CLI smoke test。

阻塞关系：

- 不阻塞核心，但阻塞手工验证。

---

## 5. Phase 2：State + Task Harness

### M2.1 实现 SQLiteStateStore 初版

状态：DONE  
优先级：P0  
目标：保存 session、message、tool_call。

输入依赖：

- M1.2

具体工作：

1. 创建 `metis/state/models.py`。
2. 创建 `metis/state/store.py` 接口。
3. 创建 `metis/state/sqlite_store.py`。
4. 初始化表：
   - sessions
   - messages
   - tool_calls
5. 实现：
   - create_session
   - append_message
   - list_messages
   - record_tool_call
   - list_tool_calls

输出产物：

- SQLite 状态存储。

验收标准：

- 能创建 session。
- 能写入/读取 messages。
- 能记录 tool_calls。

测试要求：

- `tests/unit/test_state_store.py`

阻塞关系：

- 阻塞 Goal/Plan/Step。

---

### M2.2 接入 AgentLoop 状态记录

状态：DONE  
优先级：P0  
目标：AgentLoop 执行过程写入 StateStore。

输入依赖：

- M1.9
- M2.1

具体工作：

1. AgentRunRequest 增加 session_id。
2. AgentLoop 每轮保存 assistant response。
3. 每次工具调用保存 tool_call。
4. 保存 tool result ref 或 inline result。
5. 记录 status。

输出产物：

- AgentLoop 状态化。

验收标准：

- 一次 run 后 DB 中有 messages 和 tool_calls。

测试要求：

- `tests/integration/test_agent_loop_state.py`

阻塞关系：

- 阻塞 trajectory、evidence。

---

### M2.3 实现 Goal 数据模型

状态：DONE  
优先级：P0  
目标：保存用户目标。

输入依赖：

- M2.1

具体工作：

1. 创建 `metis/planning/goal.py`。
2. 定义 Goal dataclass。
3. StateStore 增加 goals 表。
4. 实现：
   - create_goal
   - update_goal_status
   - get_goal
   - list_goals

输出产物：

- GoalManager 初版。

验收标准：

- 能创建 active goal。
- 能标记 complete/blocked/failed。

测试要求：

- `tests/unit/test_goal.py`

阻塞关系：

- 阻塞 Plan/Step。

---

### M2.4 实现 Plan / Step 数据模型

状态：DONE  
优先级：P0  
目标：把复杂任务拆成可追踪步骤。

输入依赖：

- M2.3

具体工作：

1. 创建 `metis/planning/plan.py`。
2. 创建 `metis/planning/step.py`。
3. StateStore 增加：
   - plans
   - steps
4. Step 字段包括：
   - action
   - required_inputs
   - expected_output
   - allowed_tools
   - verification_method
   - done_condition
   - status
5. 实现 step 状态转换。

输出产物：

- Plan/Step 管理。

验收标准：

- 一个 goal 可创建 plan。
- plan 下可创建多个 steps。
- step 可 pending/running/verifying/done/failed/blocked。

测试要求：

- `tests/unit/test_plan_step.py`

阻塞关系：

- 阻塞 TaskContract、StepExecutor。

---

### M2.5 实现 TaskContract

状态：DONE  
优先级：P0  
目标：为当前步骤生成小模型可执行合约。

输入依赖：

- M2.4

具体工作：

1. 创建 `metis/planning/task_contract.py`。
2. 实现 `build_task_contract(goal, step, allowed_tools, model_profile)`。
3. 支持 small/balanced/deep 三种 profile。
4. small profile 必须简短。
5. 合约中包含：
   - goal
   - current step
   - allowed tools
   - done condition
   - output rules
   - no fabrication rules

输出产物：

- TaskContract builder。

验收标准：

- 给定 goal/step 能生成合约文本。
- small profile 不超过配置长度。

测试要求：

- `tests/unit/test_task_contract.py`

阻塞关系：

- 阻塞 PromptAssembler。

---

### M2.6 实现 PromptAssembler 初版

状态：DONE  
优先级：P0  
目标：组装模型输入 messages。

输入依赖：

- M2.5

具体工作：

1. 创建 `metis/prompts/assembler.py`。
2. 创建 `metis/prompts/base.py`。
3. 支持输入：
   - base identity
   - task contract
   - memory context
   - recent messages
   - tool policy
4. 输出 OpenAI-style messages。
5. 小模型模式下当前步骤靠近末尾。

输出产物：

- PromptAssembler。

验收标准：

- 能生成 messages。
- system message 包含 contract。
- 不混入业务场景。

测试要求：

- `tests/unit/test_prompt_assembler.py`

阻塞关系：

- 阻塞 StepExecutor。

---

### M2.7 实现 StepExecutor

状态：DONE  
优先级：P0  
目标：按步骤执行任务，而不是整任务自由跑。

输入依赖：

- M1.9
- M2.4
- M2.6

具体工作：

1. 创建 `metis/runtime/execution_controller.py`。
2. 实现：
   - start_step
   - run_step
   - verify_step
   - complete_step
   - fail_step
3. run_step 调用 AgentLoop。
4. Step 完成前必须满足 verification。
5. 更新 StateStore。

输出产物：

- StepExecutor / ExecutionController。

验收标准：

- 一个 plan 能逐步执行。
- step 不会未经验证直接 done。

测试要求：

- `tests/integration/test_step_executor.py`

阻塞关系：

- 阻塞 QualityGate 深度集成。

---

## 6. Phase 3：Context + Tool Result Budget

### M3.1 实现 BudgetConfig

状态：DONE  
优先级：P1  
目标：统一工具输出和上下文预算。

输入依赖：

- M0.2

具体工作：

1. 创建 `metis/runtime/budgets.py`。
2. 定义：
   - per_tool_chars
   - per_turn_chars
   - preview_chars
   - model_context_tokens
   - context_threshold
3. 支持 small/balanced/deep preset。

输出产物：

- BudgetConfig。

验收标准：

- small preset 正确加载。

测试要求：

- `tests/unit/test_budgets.py`

阻塞关系：

- 阻塞 ToolResultStore、ContextEngine。

---

### M3.2 实现 ToolResultStore

状态：DONE  
优先级：P1  
目标：大工具输出外置。

输入依赖：

- M3.1
- M2.1

具体工作：

1. 创建 `metis/tools/result_store.py`。
2. 创建 `.metis/tool-results`。
3. 实现：
   - maybe_persist_result
   - generate_preview
   - read_result_slice
4. 超过阈值写入文件。
5. 返回 persisted-output block。
6. StateStore 记录 result path。

输出产物：

- ToolResultStore。

验收标准：

- 大结果写文件。
- 小结果 inline。
- preview 长度正确。

测试要求：

- `tests/unit/test_tool_result_store.py`

阻塞关系：

- 阻塞 AgentLoop 大输出控制。

---

### M3.3 ToolDispatcher 接入 ToolResultStore

状态：DONE  
优先级：P1  
目标：工具结果自动预算化。

输入依赖：

- M1.5
- M3.2

具体工作：

1. Dispatcher 获得 ToolResultStore。
2. 工具结果返回后检查大小。
3. 超预算则持久化。
4. emit `tool.result_persisted`。
5. ToolResult 中保存 persisted path。

输出产物：

- 预算化 ToolDispatcher。

验收标准：

- 大工具结果不直接进入 messages。

测试要求：

- `tests/integration/test_dispatcher_result_budget.py`

阻塞关系：

- 阻塞 small model mode。

---

### M3.4 实现 ContextEngine base

状态：DONE  
优先级：P1  
目标：上下文管理插件接口。

输入依赖：

- M3.1

具体工作：

1. 创建 `metis/context/engine.py`。
2. 定义接口：
   - update_from_response
   - should_compress
   - compress
   - build_context_packet
   - get_status
3. 定义 ContextPacket。

输出产物：

- ContextEngine base。

验收标准：

- SimpleContextCompressor 可继承。

测试要求：

- `tests/unit/test_context_engine_base.py`

阻塞关系：

- 阻塞 SimpleContextCompressor。

---

### M3.5 实现 SimpleContextCompressor

状态：DONE  
优先级：P1  
目标：压缩旧消息，保护当前任务。

输入依赖：

- M3.4

具体工作：

1. 创建 `metis/context/compressor.py`。
2. 实现 token/char 估算。
3. 保留：
   - system
   - current task contract
   - recent messages
4. 旧消息生成 extractive summary。
5. summary 标注 reference only。
6. emit context.compressed。

输出产物：

- SimpleContextCompressor。

验收标准：

- 超阈值时消息减少。
- 当前 step 不被压缩掉。

测试要求：

- `tests/unit/test_context_compressor.py`

阻塞关系：

- 阻塞 AgentLoop context 集成。

---

### M3.6 AgentLoop 接入 ContextEngine

状态：DONE  
优先级：P1  
目标：每轮模型调用前自动控制上下文。

输入依赖：

- M1.9
- M3.5

具体工作：

1. AgentLoop 调用 context.should_compress。
2. 需要时 context.compress。
3. 每次 response 后 update usage。
4. StateStore 记录 compression event。

输出产物：

- 上下文可控 AgentLoop。

验收标准：

- 长消息测试触发压缩。

测试要求：

- `tests/integration/test_agent_loop_context.py`

阻塞关系：

- 阻塞 small model mode。

---

## 7. Phase 4：Artifact + Evidence + Quality

### M4.1 实现 ArtifactStore

状态：DONE  
优先级：P1  
目标：记录真实交付物。

输入依赖：

- M2.1

具体工作：

1. 创建 `metis/artifacts/store.py`。
2. StateStore 增加 artifacts 表。
3. 实现：
   - register_artifact
   - get_artifact
   - list_artifacts
   - compute_checksum
4. artifact 字段：
   - id
   - type
   - path
   - checksum
   - status
   - metadata

输出产物：

- ArtifactStore。

验收标准：

- 文件存在时可注册 artifact。
- checksum 正确。

测试要求：

- `tests/unit/test_artifact_store.py`

阻塞关系：

- 阻塞 QualityGate artifact checks。

---

### M4.2 实现 Artifact Validators

状态：DONE  
优先级：P1  
目标：验证产物存在、非空、无占位符。

输入依赖：

- M4.1

具体工作：

1. 创建 `metis/artifacts/validators.py`。
2. 实现：
   - exists
   - non_empty
   - extension_matches
   - no_placeholder
   - checksum_matches
3. placeholder 检查词：
   - TODO
   - TBD
   - placeholder
   - mock
   - dummy
   - 示例数据
   - 待补充

输出产物：

- artifact validators。

验收标准：

- 含 placeholder 的文件检查失败。

测试要求：

- `tests/unit/test_artifact_validators.py`

阻塞关系：

- 阻塞 QualityGateRunner。

---

### M4.3 实现 EvidenceLedger

状态：DONE  
优先级：P1  
目标：记录 claim 与来源。

输入依赖：

- M2.1

具体工作：

1. 创建 `metis/evidence/ledger.py`。
2. StateStore 增加 evidence 表。
3. 实现：
   - record_claim
   - list_evidence
   - find_by_source
   - summarize_for_prompt
4. source_type 支持：
   - user_input
   - file
   - tool_output
   - command
   - web
   - artifact
   - model_inference

输出产物：

- EvidenceLedger。

验收标准：

- 能记录和查询证据。

测试要求：

- `tests/unit/test_evidence_ledger.py`

阻塞关系：

- 阻塞 QualityGate truthfulness。

---

### M4.4 实现 QualityGateRunner

状态：DONE  
优先级：P1  
目标：运行质量门。

输入依赖：

- M4.1
- M4.2
- M4.3

具体工作：

1. 创建 `metis/quality/gates.py`。
2. 创建 `metis/quality/runner.py`。
3. 定义 GateSpec。
4. 定义 GateResult。
5. 实现默认 gates：
   - artifact_exists
   - artifact_non_empty
   - no_placeholder
   - requirements_covered
   - no_fake_completion
6. 支持 failure_policy。

输出产物：

- QualityGateRunner。

验收标准：

- gate 可注册、运行、返回结果。
- 失败 gate 有明确 message。

测试要求：

- `tests/unit/test_quality_gates.py`

阻塞关系：

- 阻塞 Step verification。

---

### M4.5 StepExecutor 接入 QualityGate

状态：DONE  
优先级：P1  
目标：步骤完成必须经过质量门。

输入依赖：

- M2.7
- M4.4

具体工作：

1. Step 定义 required gates。
2. StepExecutor 在 complete 前运行 gate。
3. gate 失败则 step failed 或 verifying。
4. gate 通过才 done。

输出产物：

- 质量门控制步骤完成。

验收标准：

- 未生成 artifact 的步骤不能 done。

测试要求：

- `tests/integration/test_step_quality_gate.py`

阻塞关系：

- 阻塞 full e2e。

---

### M4.6 Final Response Truthfulness Gate

状态：DONE  
优先级：P1  
目标：防止最终回答虚假声明。

输入依赖：

- M4.3
- M4.4

具体工作：

1. 检查 final text 中的：
   - 已生成
   - 已运行
   - 已测试
   - 已上传
   - 已修复
2. 对应 trajectory/tool_call/artifact 必须存在。
3. 没证据则 gate fail。

输出产物：

- no_fake_completion gate。

验收标准：

- 模型说“已生成 X”但 X 不存在时失败。

测试要求：

- `tests/unit/test_final_truthfulness_gate.py`

阻塞关系：

- 阻塞 production readiness。

---

## 8. Phase 5：Small Model Mode

### M5.1 定义 ModelProfile

状态：DONE  
优先级：P1  
目标：为 small/balanced/deep 定义执行配置。

输入依赖：

- M3.1

具体工作：

1. 创建 `metis/config.py` 或 `metis/runtime/profiles.py`。
2. 定义：
   - small
   - balanced
   - deep
3. small 配置：
   - max_tools_per_turn = 8
   - max_tool_calls_per_turn = 8
   - prompt budget lower
   - one_tool_call_per_turn = true
   - strict_output = true

输出产物：

- ModelProfile。

验收标准：

- profile 可加载。

测试要求：

- `tests/unit/test_model_profiles.py`

阻塞关系：

- 阻塞 small mode。

---

### M5.2 实现 Stage-based Tool Router

状态：DONE  
优先级：P1  
目标：按当前步骤选择少量工具。

输入依赖：

- M1.4
- M2.4
- M5.1

具体工作：

1. 创建 `metis/tools/permissions.py` 或 `tool_router.py`。
2. 定义阶段：
   - explore
   - plan
   - execute
   - verify
   - finalize
3. 根据 step.allowed_tools 和 profile.max_tools 过滤。
4. 默认 small 不超过 8 个工具。

输出产物：

- ToolRouter。

验收标准：

- 100 个注册工具时 small mode 只返回相关 8 个以内。

测试要求：

- `tests/unit/test_tool_router.py`

阻塞关系：

- 阻塞 small model e2e。

---

### M5.3 实现 Strict Output Contract

状态：DONE  
优先级：P1  
目标：小模型最终输出结构化状态。

输入依赖：

- M2.5
- M2.6

具体工作：

1. PromptAssembler small mode 注入输出 schema。
2. schema 包含：
   - status
   - summary
   - evidence_refs
   - artifact_refs
   - next_action
3. 实现解析器。
4. 非法输出触发 repair。

输出产物：

- strict output parser。

验收标准：

- 非 JSON final 能被识别并触发 repair。

测试要求：

- `tests/unit/test_strict_output_contract.py`

阻塞关系：

- 阻塞 parser repair e2e。

---

### M5.4 实现 Parser Repair Loop

状态：DONE  
优先级：P1  
目标：修复小模型错误工具调用。

输入依赖：

- M1.8
- M5.3

具体工作：

1. AgentLoop 捕获 ParserError。
2. 构造短 repair prompt。
3. 最多 retry 2 次。
4. 记录 parser error。
5. 失败后 blocked。

输出产物：

- parser repair。

验收标准：

- 错误 JSON 第一次失败，第二次修复成功。

测试要求：

- `tests/integration/test_parser_repair.py`

阻塞关系：

- 阻塞 small model reliability。

---

### M5.5 实现 ToolCallGuardrailController

状态：DONE  
优先级：P1  
目标：防止小模型工具循环卡死。

输入依赖：

- M1.5
- M3.2

具体工作：

1. 创建 `metis/tools/guardrails.py`。
2. 实现：
   - exact failure count
   - same tool failure count
   - idempotent no-progress count
   - mutating tool repeat check
3. 决策：
   - allow
   - warn
   - block
   - halt
4. 接入 ToolDispatcher。

输出产物：

- ToolCallGuardrailController。

验收标准：

- 同一失败工具调用重复超过阈值后 block。

测试要求：

- `tests/unit/test_tool_guardrails.py`
- `tests/integration/test_tool_loop_block.py`

阻塞关系：

- 阻塞 production small mode。

---

### M5.6 小模型 E2E 验收任务

状态：DONE  
优先级：P1  
目标：用 small mode 跑真实任务。

输入依赖：

- M5.1-M5.5
- M4.5

具体工作：

1. 准备 fixture 小项目。
2. 任务：读取项目并生成架构报告。
3. 要求：
   - 至少读取 5 个文件。
   - 写出 Markdown 报告。
   - ArtifactStore 记录报告。
   - QualityGate 通过。
4. 使用 FakeProvider 先测。
5. 使用真实 9B endpoint 可选测。

输出产物：

- small mode e2e 测试。

验收标准：

- FakeProvider 跑通。
- 真实 9B 若配置存在则跑通或记录失败原因。

测试要求：

- `tests/e2e/test_small_model_report_task.py`

阻塞关系：

- v0.5 里程碑。

---

## 9. Phase 6：Recovery + Security

### M6.1 实现 ErrorClassifier

状态：DONE  
优先级：P1  
目标：错误分类。

输入依赖：

- M1.2

具体工作：

1. 创建 `metis/recovery/classifier.py`。
2. 分类：
   - network
   - rate_limit
   - auth
   - provider
   - context
   - parser
   - tool
   - validation
   - security
   - unknown

输出产物：

- ErrorClassifier。

验收标准：

- 常见错误字符串分类正确。

测试要求：

- `tests/unit/test_error_classifier.py`

阻塞关系：

- 阻塞 RecoveryManager。

---

### M6.2 实现 RetryPolicy

状态：DONE  
优先级：P1  
目标：jittered backoff。

输入依赖：

- M6.1

具体工作：

1. 创建 `metis/recovery/retry.py`。
2. 实现 jittered_backoff。
3. 支持 max_retries。
4. 支持不同 error category 策略。

输出产物：

- RetryPolicy。

验收标准：

- backoff 有上限和 jitter。

测试要求：

- `tests/unit/test_retry_policy.py`

阻塞关系：

- 阻塞 RecoveryManager。

---

### M6.3 实现 RecoveryManager

状态：DONE  
优先级：P1  
目标：统一恢复逻辑。

输入依赖：

- M6.1
- M6.2
- M1.1

具体工作：

1. 创建 `metis/recovery/manager.py`。
2. 实现：
   - should_retry
   - execute_with_recovery
   - on_tool_error
   - on_provider_error
3. emit recovery.retry。
4. auth/security 不重试。

输出产物：

- RecoveryManager。

验收标准：

- network error 可重试。
- auth error 不重试。

测试要求：

- `tests/unit/test_recovery_manager.py`

阻塞关系：

- 阻塞 provider 稳定性。

---

### M6.4 实现 Path Security

状态：DONE  
优先级：P1  
目标：保护敏感路径。

输入依赖：

- M1.3

具体工作：

1. 创建 `metis/security/paths.py`。
2. 实现：
   - is_write_denied
   - is_read_denied
   - resolve_workspace_path
3. denylist：
   - `.ssh`
   - `.aws`
   - `.gnupg`
   - `.kube`
   - `.docker`
   - `.env`
   - `.netrc`
   - shell rc
   - system dirs
4. 支持 safe root。

输出产物：

- path security。

验收标准：

- 写敏感路径被拒绝。

测试要求：

- `tests/unit/test_path_security.py`

阻塞关系：

- 阻塞文件写工具。

---

### M6.5 实现 Prompt Injection Scanner

状态：DONE  
优先级：P1  
目标：扫描上下文文件和工具输出中的注入风险。

输入依赖：

- M1.1

具体工作：

1. 创建 `metis/security/prompt_injection.py`。
2. 检测：
   - ignore previous instructions
   - system prompt override
   - hidden HTML
   - invisible unicode
   - secret exfiltration
3. 返回 sanitized content 或 block result。

输出产物：

- prompt injection scanner。

验收标准：

- 恶意 context 文件被替换为 blocked note。

测试要求：

- `tests/unit/test_prompt_injection_scanner.py`

阻塞关系：

- 阻塞 workspace context。

---

### M6.6 实现 Redaction

状态：DONE  
优先级：P1  
目标：凭据脱敏。

输入依赖：

- M1.1

具体工作：

1. 创建 `metis/security/redaction.py`。
2. 检测并替换：
   - API key
   - Bearer token
   - password
   - private key block
3. 工具结果和日志写入前可调用。

输出产物：

- redaction utility。

验收标准：

- 测试 key 被替换为 `[REDACTED]`。

测试要求：

- `tests/unit/test_redaction.py`

阻塞关系：

- 阻塞生产日志。

---

## 10. Phase 7：Loop + Scheduler

### M7.1 实现 LoopSpec

状态：DONE  
优先级：P2  
目标：定义循环任务。

输入依赖：

- M2.1

具体工作：

1. 创建 `metis/loops/loop_manager.py`。
2. 定义 LoopSpec：
   - id
   - prompt
   - interval
   - max_iterations
   - status
   - last_run_at
3. StateStore 增加 loops 表。

输出产物：

- LoopSpec。

验收标准：

- 可创建 loop。

测试要求：

- `tests/unit/test_loop_spec.py`

阻塞关系：

- 阻塞 LoopManager。

---

### M7.2 实现 LoopManager

状态：DONE  
优先级：P2  
目标：后台循环执行。

输入依赖：

- M7.1
- M2.7

具体工作：

1. 支持 start/stop/pause/resume/list。
2. 后台线程或 asyncio task。
3. 每次 tick 调用 ExecutionController。
4. 支持 max_iterations。
5. 连续失败熔断。
6. emit loop.tick/loop.error/loop.complete。

输出产物：

- LoopManager。

验收标准：

- loop 能按 interval 执行。
- stop 生效。

测试要求：

- `tests/integration/test_loop_manager.py`

阻塞关系：

- 阻塞 scheduler。

---

### M7.3 实现 Scheduler

状态：DONE  
优先级：P2  
目标：支持定时任务。

输入依赖：

- M7.2

具体工作：

1. 创建 `metis/loops/scheduler.py`。
2. 支持 cron-like 简化表达：
   - every N minutes
   - daily HH:MM
3. 持久化 schedule。
4. 触发 loop。

输出产物：

- Scheduler。

验收标准：

- 可创建 daily schedule。

测试要求：

- `tests/unit/test_scheduler.py`

阻塞关系：

- 不阻塞 v1.0。

---

## 11. Phase 8：Swarm + Auditor

### M8.1 定义 RoleTemplate

状态：DONE  
优先级：P2  
目标：定义角色模板。

输入依赖：

- M1.4

具体工作：

1. 创建 `metis/swarm/roles.py`。
2. 定义 RoleTemplate。
3. 内置角色：
   - planner
   - explorer
   - implementer
   - verifier
   - auditor
   - synthesizer
4. 每个角色定义 allowed_tools。

输出产物：

- RoleTemplateBank。

验收标准：

- 可按 role_id 获取角色。

测试要求：

- `tests/unit/test_role_templates.py`

阻塞关系：

- 阻塞 SwarmOrchestrator。

---

### M8.2 实现 FilteredToolRegistry

状态：DONE  
优先级：P2  
目标：角色工具权限隔离。

输入依赖：

- M1.4
- M8.1

具体工作：

1. 创建 `metis/swarm/orchestrator.py` 或独立模块。
2. 实现 FilteredToolRegistry。
3. 不允许的工具返回结构化 error。

输出产物：

- FilteredToolRegistry。

验收标准：

- Explorer 无法调用 write_file。

测试要求：

- `tests/unit/test_filtered_tool_registry.py`

阻塞关系：

- 阻塞 swarm 执行。

---

### M8.3 实现 SwarmAnalyzer

状态：DONE  
优先级：P2  
目标：判断是否需要 swarm。

输入依赖：

- M2.5

具体工作：

1. 创建 `metis/swarm/analyzer.py`。
2. 基于规则判断：
   - 多模块任务
   - 明确要求多智能体
   - 需要审核团队
   - 多次失败升级
3. 返回 SwarmDecision。

输出产物：

- SwarmAnalyzer。

验收标准：

- 简单任务不触发。
- 复杂任务触发。

测试要求：

- `tests/unit/test_swarm_analyzer.py`

阻塞关系：

- 阻塞 SwarmOrchestrator。

---

### M8.4 实现 TaskDecomposer

状态：DONE  
优先级：P2  
目标：拆分 swarm stage。

输入依赖：

- M8.1

具体工作：

1. 创建 `metis/swarm/decomposer.py`。
2. 输出 stages。
3. stage 支持 parallel。
4. 每个 agent spec 绑定 role。

输出产物：

- TaskDecomposer。

验收标准：

- 复杂任务可拆为 explorer/implementer/verifier/auditor。

测试要求：

- `tests/unit/test_swarm_decomposer.py`

阻塞关系：

- 阻塞 SwarmOrchestrator。

---

### M8.5 实现 SwarmBus

状态：DONE  
优先级：P2  
目标：子智能体结果通信。

输入依赖：

- M2.1

具体工作：

1. 创建 `metis/swarm/bus.py`。
2. 支持：
   - register_agent
   - publish
   - collect
3. 记录 result。

输出产物：

- SwarmBus。

验收标准：

- 多 agent 结果可收集。

测试要求：

- `tests/unit/test_swarm_bus.py`

阻塞关系：

- 阻塞 SwarmOrchestrator。

---

### M8.6 实现 SwarmOrchestrator

状态：DONE  
优先级：P2  
目标：执行多角色任务。

输入依赖：

- M8.1-M8.5
- M2.7

具体工作：

1. 创建 `metis/swarm/orchestrator.py`。
2. 支持 sequential stage。
3. 支持 parallel stage。
4. 每个 agent 使用 filtered tools。
5. 记录 execution record。
6. emit swarm events。

输出产物：

- SwarmOrchestrator。

验收标准：

- 一个 swarm 任务可执行 explorer + verifier。

测试要求：

- `tests/integration/test_swarm_orchestrator.py`

阻塞关系：

- 阻塞 Auditor/Synthesizer。

---

### M8.7 实现 Auditor

状态：DONE  
优先级：P2  
目标：审核子任务和最终结果。

输入依赖：

- M4.4
- M8.6

具体工作：

1. 创建 `metis/swarm/auditor.py`。
2. 审核：
   - artifact 是否存在。
   - evidence 是否充分。
   - tests 是否运行。
   - 是否有伪完成。
3. 输出 audit report。

输出产物：

- Auditor。

验收标准：

- 无 artifact 的完成声明被拦截。

测试要求：

- `tests/integration/test_swarm_auditor.py`

阻塞关系：

- 阻塞 production swarm。

---

### M8.8 实现 ResultSynthesizer

状态：DONE  
优先级：P2  
目标：综合子任务结果。

输入依赖：

- M8.7

具体工作：

1. 创建 `metis/swarm/synthesizer.py`。
2. 只综合通过 audit 的结果。
3. 保留 evidence refs。
4. 输出 final draft。

输出产物：

- ResultSynthesizer。

验收标准：

- failed/audit failed 结果不会进入 final。

测试要求：

- `tests/unit/test_result_synthesizer.py`

阻塞关系：

- 阻塞 swarm final。

---

## 12. Phase 9：Skills + Plugins

### M9.1 实现 Skill 数据结构

状态：DONE  
优先级：P3  
目标：定义可复用流程。

输入依赖：

- M2.5

具体工作：

1. 创建 `metis/skills/manager.py`。
2. 定义 Skill：
   - id
   - name
   - description
   - triggers
   - content
   - allowed_tools
   - quality_gates

输出产物：

- Skill model。

验收标准：

- 可加载一个 SKILL.md。

测试要求：

- `tests/unit/test_skill_model.py`

阻塞关系：

- 阻塞 SkillLoader。

---

### M9.2 实现 SkillLoader

状态：DONE  
优先级：P3  
目标：加载技能文件。

输入依赖：

- M9.1

具体工作：

1. 创建 `metis/skills/loader.py`。
2. 支持读取：
   - `skills/*/SKILL.md`
3. 支持 frontmatter。
4. 支持 UTF-8。
5. 不执行 inline shell，第一版禁止。

输出产物：

- SkillLoader。

验收标准：

- 中文 SKILL.md 正确加载。

测试要求：

- `tests/unit/test_skill_loader.py`

阻塞关系：

- 阻塞 SkillIndex。

---

### M9.3 实现 SkillIndex

状态：DONE  
优先级：P3  
目标：根据任务匹配技能。

输入依赖：

- M9.2

具体工作：

1. 创建 `metis/skills/index.py`。
2. 简单关键词匹配。
3. 返回 top_k。
4. 小模型只注入 skill 摘要。

输出产物：

- SkillIndex。

验收标准：

- 给定任务能匹配相关 skill。

测试要求：

- `tests/unit/test_skill_index.py`

阻塞关系：

- 阻塞 Skill prompt integration。

---

### M9.4 实现 Plugin API

状态：DONE  
优先级：P3  
目标：定义插件扩展接口。

输入依赖：

- M1.4
- M4.4

具体工作：

1. 创建 `metis/plugins/api.py`。
2. 定义插件可注册：
   - tools
   - prompt fragments
   - quality gates
   - role templates
   - artifact validators
3. 插件必须有 manifest。

输出产物：

- Plugin API。

验收标准：

- 测试插件能注册工具。

测试要求：

- `tests/unit/test_plugin_api.py`

阻塞关系：

- 阻塞 adapters。

---

### M9.5 实现 PluginManager

状态：DONE  
优先级：P3  
目标：加载插件。

输入依赖：

- M9.4

具体工作：

1. 创建 `metis/plugins/manager.py`。
2. 支持本地插件目录。
3. 加载 manifest。
4. 调用 register。
5. 插件异常不影响核心启动。

输出产物：

- PluginManager。

验收标准：

- 一个本地插件加载成功。

测试要求：

- `tests/integration/test_plugin_manager.py`

阻塞关系：

- 阻塞 Aurora/Sophia adapter。

---

## 13. Phase 10：Adapters

### M10.1 设计 Adapter 接口

状态：DONE  
优先级：P3  
目标：业务接入统一接口。

输入依赖：

- M9.4

具体工作：

1. 创建 `metis/adapters/base.py`。
2. 定义 Adapter：
   - name
   - register_tools
   - register_prompt_fragments
   - register_quality_gates
   - register_roles
3. Adapter 不允许修改 Metis core。

输出产物：

- Adapter API。

验收标准：

- fake adapter 可注册工具。

测试要求：

- `tests/unit/test_adapter_api.py`

阻塞关系：

- 阻塞 Aurora/Sophia adapter。

---

### M10.2 Aurora Adapter 初版

状态：DONE  
优先级：P3  
目标：接入 Aurora 部分工具。

输入依赖：

- M10.1
- Aurora 项目路径存在

具体工作：

1. 创建 `adapters/aurora_adapter` 或 `metis/adapters/aurora.py`。
2. 选取少量无强业务依赖工具。
3. 包装为 ToolSpec。
4. 注册 Aurora quality auditor 可选。
5. 不迁移 AuroraAgent 主循环。

输出产物：

- Aurora adapter。

验收标准：

- Metis 能列出 Aurora adapter 工具。
- 能调用一个 Aurora 工具。

测试要求：

- `tests/integration/test_aurora_adapter.py`

阻塞关系：

- 不阻塞 core。

---

### M10.3 Sophia Adapter 初版

状态：DONE  
优先级：P3  
目标：接入 Sophia 部分工具。

输入依赖：

- M10.1
- Sophia 项目路径存在

具体工作：

1. 创建 `metis/adapters/sophia.py`。
2. 选取少量通用工具或 research 工具。
3. 包装为 ToolSpec。
4. 将 Sophia task_harness 思想迁移为 TaskContract 可选。
5. 不暴露全部 Sophia 工具给小模型。

输出产物：

- Sophia adapter。

验收标准：

- Metis 能列出 Sophia adapter 工具。
- 能调用一个 Sophia 工具。

测试要求：

- `tests/integration/test_sophia_adapter.py`

阻塞关系：

- 不阻塞 core。

---

## 14. Phase 11：Evaluation + Hardening

### M11.1 建立 E2E Fixture 项目

状态：DONE  
优先级：P2  
目标：创建用于测试 Metis 的小项目。

输入依赖：

- M0.4

具体工作：

1. 在 `tests/fixtures/sample_project` 创建小型 Python 项目。
2. 包含：
   - README
   - 3-5 个 Python 文件
   - 1 个故意语法错误版本可选
   - tests
3. 用于报告任务和修复任务。

输出产物：

- sample_project fixture。

验收标准：

- fixture 可用于测试。

测试要求：

- fixture smoke。

阻塞关系：

- 阻塞 e2e。

---

### M11.2 E2E：架构报告任务

状态：DONE  
优先级：P2  
目标：验证 Metis 能生成真实报告。

输入依赖：

- M11.1
- M5.6

具体工作：

1. 任务：分析 sample_project 架构。
2. 要求生成 Markdown。
3. 检查读取文件数量。
4. 检查 artifact。
5. 检查 evidence。
6. 检查 quality gates。

输出产物：

- e2e 测试。

验收标准：

- 报告真实存在。
- 报告无 placeholder。
- evidence 引用真实文件。

测试要求：

- `tests/e2e/test_architecture_report_task.py`

阻塞关系：

- v1.0 readiness。

---

### M11.3 E2E：修复并测试任务

状态：DONE  
优先级：P2  
目标：验证 Metis 能修复代码。

输入依赖：

- M11.1
- M4.4

具体工作：

1. 准备 broken fixture。
2. 任务：修复测试失败。
3. Metis 必须运行测试。
4. 记录 test command。
5. final 不得虚报。

输出产物：

- e2e 修复测试。

验收标准：

- 测试从失败到通过。
- 修改文件真实。

测试要求：

- `tests/e2e/test_fix_and_test_task.py`

阻塞关系：

- v1.0 readiness。

---

### M11.4 小模型真实 Endpoint 评测

状态：DONE  
优先级：P2  
目标：验证 9B 模型可用性。

输入依赖：

- M5.6
- 可用本地/远端 9B OpenAI-compatible endpoint

具体工作：

1. 配置环境变量：
   - METIS_BASE_URL
   - METIS_API_KEY
   - METIS_MODEL
2. 跑小模型任务集。
3. 记录：
   - success rate
   - parser failures
   - tool calls
   - quality gate failures
   - false completion
4. 生成评测报告。

输出产物：

- `docs/evals/9b-eval-report.md`

验收标准：

- 没有 endpoint 时测试 skip，不伪造。
- 有 endpoint 时真实运行。

测试要求：

- `tests/e2e/test_local_9b_eval.py`

阻塞关系：

- v1.0 quality claim。

---

### M11.5 文档完善

状态：DONE  
优先级：P2  
目标：形成可维护文档体系。

输入依赖：

- 所有核心模块

具体工作：

1. `docs/architecture.md`
2. `docs/module-spec.md`
3. `docs/small-model-mode.md`
4. `docs/security-model.md`
5. `docs/extension-guide.md`
6. `docs/testing-strategy.md`

输出产物：

- docs。

验收标准：

- 每个核心模块有说明。
- 每个 adapter 扩展点有说明。

测试要求：

- 文档链接检查可选。

阻塞关系：

- v1.0 release。

---

## 15. 跨阶段强制任务

### C1 编码规范

状态：DONE  
优先级：P0  
目标：避免中文和 Windows 编码问题。

具体要求：

1. 所有源码 UTF-8。
2. 所有文件读写显式 `encoding="utf-8"`。
3. 测试中文文件读写。
4. 不以 PowerShell 控制台乱码判断文件是否损坏。

验收标准：

- 中文文档读取内容正确。

---

### C2 不伪造完成机制

状态：DONE  
优先级：P0  
目标：Metis 不能让模型虚假完成。

具体要求：

1. 最终回答必须查询 ArtifactStore 和 QualityGate。
2. 工具运行声明必须查询 tool_calls。
3. 测试声明必须查询 command result。
4. 没证据时最终回答必须披露未完成或 blocked。

验收标准：

- 模拟模型虚报时 gate fail。

---

### C3 轨迹记录

状态：DONE  
优先级：P1  
目标：所有关键动作可复盘。

具体要求：

1. 创建 `metis/telemetry/trajectory.py`。
2. 记录：
   - agent events
   - model calls
   - tool calls
   - state transitions
   - quality results
3. 支持 JSONL export。

验收标准：

- 一次 e2e run 生成 trajectory。

---

### C4 测试纪律

状态：DONE  
优先级：P0  
目标：每个模块必须有测试。

具体要求：

1. P0 模块没有测试不得标记 DONE。
2. P1 模块至少有 unit + integration。
3. 涉及真实模型的测试必须可 skip，不能伪造通过。

验收标准：

- CI 或本地 `pytest` 可跑。

---

## 16. 任务依赖总图

```text
M0.1 -> M0.2 -> M0.4

M1.1 -> M1.4 -> M1.5 -> M1.9
M1.2 -> M1.6 -> M1.9
M1.8 -> M1.9

M2.1 -> M2.3 -> M2.4 -> M2.5 -> M2.6 -> M2.7
M1.9 -> M2.2 -> M2.7

M3.1 -> M3.2 -> M3.3
M3.1 -> M3.4 -> M3.5 -> M3.6

M4.1 -> M4.2 -> M4.4
M4.3 -> M4.4
M4.4 -> M4.5 -> M5.6

M5.1 -> M5.2
M5.3 -> M5.4
M5.5 -> M5.6

M6.1 -> M6.2 -> M6.3
M6.4 -> file tools
M6.5 -> workspace context
M6.6 -> logs/tool results

M8.1 -> M8.2 -> M8.6
M8.3 -> M8.6
M8.4 -> M8.6
M8.5 -> M8.6 -> M8.7 -> M8.8

M9.1 -> M9.2 -> M9.3
M9.4 -> M9.5 -> M10.1 -> M10.2/M10.3
```

---

## 17. 第一轮冲刺建议

第一轮不要做全部任务。建议只做 P0 闭环。

### Sprint 1 范围

1. M0.1 项目基础结构
2. M0.2 `pyproject.toml`
3. M0.4 测试结构
4. M1.1 HookBus
5. M1.2 Runtime 数据结构
6. M1.3 ToolSpec
7. M1.4 ToolRegistry
8. M1.5 ToolDispatcher
9. M1.6 FakeProvider
10. M1.8 Tool Call Parser 初版
11. M1.9 AgentLoop 最小版

### Sprint 1 验收

必须跑通：

```text
FakeProvider -> tool_call(read_file) -> ToolDispatcher -> tool_result -> FakeProvider final -> AgentRunResult
```

必须有：

- 单元测试。
- 集成测试。
- trajectory 可选。

不做：

- 数据库。
- swarm。
- adapter。
- web。
- MCP。

---

## 18. 第二轮冲刺建议

### Sprint 2 范围

1. M2.1 SQLiteStateStore
2. M2.2 AgentLoop 状态记录
3. M2.3 Goal
4. M2.4 Plan / Step
5. M2.5 TaskContract
6. M2.6 PromptAssembler
7. M2.7 StepExecutor

### Sprint 2 验收

必须跑通：

```text
user task -> create goal -> create plan -> run step -> verify step -> mark done
```

不允许：

- step 未验证直接 done。

---

## 19. 第三轮冲刺建议

### Sprint 3 范围

1. M3.1 BudgetConfig
2. M3.2 ToolResultStore
3. M3.3 Dispatcher 接入预算
4. M3.4 ContextEngine base
5. M3.5 SimpleContextCompressor
6. M3.6 AgentLoop 接入 context
7. M4.1 ArtifactStore
8. M4.2 Artifact Validators

### Sprint 3 验收

必须跑通：

```text
large tool result -> persisted file -> preview in context -> artifact registered
```

---

## 20. 第四轮冲刺建议

### Sprint 4 范围

1. M4.3 EvidenceLedger
2. M4.4 QualityGateRunner
3. M4.5 StepExecutor 接入 QualityGate
4. M4.6 Final Response Truthfulness Gate
5. M5.1 ModelProfile
6. M5.2 Stage Tool Router
7. M5.3 Strict Output Contract
8. M5.4 Parser Repair
9. M5.5 ToolCallGuardrailController

### Sprint 4 验收

必须跑通：

```text
small model mode -> limited tools -> strict output -> quality gate -> final truthfulness check
```

---

## 21. v1.0 前不得省略的检查

1. 所有 P0/P1 模块有测试。
2. 小模型模式有 E2E。
3. 工具输出预算有测试。
4. 虚假完成 gate 有测试。
5. ArtifactStore 有测试。
6. EvidenceLedger 有测试。
7. Context compression 有测试。
8. Path security 有测试。
9. 中文 UTF-8 有测试。
10. 真实模型测试不伪造，没配置就 skip。

---

## 22. 最终完成定义

Metis v1.0 不能以“代码写完”为完成标准。必须满足：

1. 能作为 Python 包安装。
2. 能通过 CLI 运行。
3. 能连接 OpenAI-compatible provider。
4. 能用 FakeProvider 完成确定性测试。
5. 能执行多轮工具调用。
6. 能创建 goal/plan/step。
7. 能记录状态。
8. 能外置大工具结果。
9. 能压缩上下文。
10. 能生成 artifact。
11. 能记录 evidence。
12. 能运行 quality gate。
13. 能拦截虚假完成。
14. 能以 small model mode 跑真实任务。
15. 有完整测试报告。
16. 有构建文档、模块文档、扩展文档。

只有这些全部满足，Metis 才算成为一个真正可作为不同场景智能体底座的 harness 项目。
