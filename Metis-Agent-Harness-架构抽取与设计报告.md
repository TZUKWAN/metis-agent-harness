# Metis Agent Harness 架构抽取与设计报告

生成时间：2026-05-25  
分析范围：

- `D:\LATEXTEST\aurora-agent`
- `D:\LATEXTEST\sophia-agent`
- `D:\LATEXTEST\hermes-agent`

目标：把 Aurora、Sophia、Hermes 三个项目里不依赖具体业务场景的智能体运行底座抽取出来，形成一个可以独立演进的 `metis-agent-harness` 架构方向。这个架构不是“商业计划书智能体”、不是“学术研究智能体”、也不是“通用聊天壳”，而是一个专门服务于不同场景智能体开发的 harness 底座：它负责让模型会规划、会调用工具、会保存状态、会压缩上下文、会自我校验、会恢复失败、会产出文件、会记录证据、会多智能体协作，并且在小模型，尤其是免费或低成本 9B 级模型上，尽可能稳定地产出高质量交付成果。

本报告不包含示例数据，不把业务场景能力当成 harness 能力，不假设未验证的实现已经存在。以下所有判断均来自本地代码阅读、项目结构分析和外部开源 agent harness 项目参照。

---

## 1. 结论先行

Metis 应该被设计成一个“低模型能力补偿型”的智能体 harness。它的核心不是让模型更聪明，而是把高质量工作拆成可验证的工程过程，用架构把模型的短板包住。

9B 模型普遍存在以下问题：

1. 长程规划不稳定。
2. 容易忘记前文约束。
3. 工具调用参数容易出错。
4. 复杂任务中间状态保持能力弱。
5. 质量自检不可靠。
6. 多步骤任务容易提前宣布完成。
7. 容易受提示注入或错误上下文影响。
8. 面对大工具输出时容易上下文溢出。
9. 对“真实完成”和“写一份看起来完成的文本”区分能力不足。

所以 Metis 的设计重点应该是：

- 用强制任务合约替代自由发挥。
- 用状态机和步骤表替代模型脑内规划。
- 用工具注册表和参数校验替代自由工具猜测。
- 用事件 hook 让所有关键动作可观察、可拦截、可复盘。
- 用 memory、snapshot、trajectory 保存过程，而不是依赖上下文。
- 用 context engine 控制模型看到的信息，而不是把所有内容塞给模型。
- 用 verification gate 控制阶段完成，而不是让模型自己说完成。
- 用 role/subagent 隔离复杂任务，但必须配套权限限制、结果综合和审计。
- 用 artifact-first 交付，把最终成果写入文件、报告、表格、演示或其他可检查产物。
- 用 recovery、retry、credential failover 和 graceful degradation 提升稳定性。

从三个项目看：

- Aurora 的优点是轻量、结构直观、工具注册清楚、Hook/Guardrail/Recovery/Swarm/Loop 组成清晰，适合作为 Metis 的最小核心骨架参考。
- Sophia 的优点是“任务质量 harness”意识更强，包含 Goal、Loop、SubAgent、Swarm、Autopilot、Memory、Trajectory、Snapshot、Kanban、Skill、Plugin、Experiment、Workspace Context 等大量可复用机制，适合作为 Metis 的生产级机制库参考。
- Hermes 的优点是通用运行时能力最强，尤其是 provider transport、context engine 插件化、大工具输出持久化、工具循环 guardrail、文件安全、技能预处理、多后端环境、多模型 tool-call parser、gateway/ACP 通道等，适合作为 Metis 的底层运行时和模型兼容层参考。

最终建议：Metis 不应简单复制三者任一项目，而应组合成一个四层架构：

1. **Runtime Kernel**：模型、消息、工具调用循环、transport、parser、预算、错误恢复。
2. **Control Plane**：goal、plan、loop、hook、event bus、state machine、scheduler、snapshot、trajectory。
3. **Cognitive Harness**：task contract、context engine、memory、skill、subagent/swarm、quality gates、evidence ledger。
4. **Application Adapter Layer**：面向不同场景注册工具、提示模板、输出格式、领域规则，不污染底座。

---

## 2. 外部开源项目参照

根据 GitHub 和公开项目资料，本次重点参考以下方向：

1. LangGraph / LangChain 体系  
   参考点：状态图、长运行工作流、条件边、checkpoint、人类介入点。  
   相关链接：
   - https://github.com/langchain-ai/langgraph
   - https://www.langchain.com/blog/langgraph

2. CrewAI  
   参考点：role-based agents、Crew 与 Flow 的区分、任务委派、角色职责清晰化。  
   相关链接：
   - https://github.com/crewAIInc/crewAI

3. OpenHands  
   参考点：sandboxed execution、tool/action space、软件开发型 agent 的环境控制、生命周期管理、评测环境。  
   相关链接：
   - https://github.com/All-Hands-AI/OpenHands
   - https://docs.all-hands.dev/usage/agents

4. DeepAgents  
   参考点：planning tool、filesystem backend、subagent delegation、长任务状态外置。  
   相关链接：
   - https://github.com/langchain-ai/deepagents

5. OpenHarness / Its Harness 方向  
   参考点：harness interoperability、runtime-neutral IR、不同 agent framework 的适配层思想。  
   相关链接：
   - https://openharness.ai/
   - https://itsharness.com/

这些项目共同说明一个趋势：真正可用的 agent 不只是“模型 + 工具列表”，而是一个有状态、有控制面、有安全边界、有可观测性、有产物管理、有验证闭环的运行系统。

Metis 与这些外部项目的区别应当是：更明确地面向“小模型可用性”。LangGraph 偏通用工作流，CrewAI 偏角色协作，OpenHands 偏代码环境，DeepAgents 偏深度任务模式。Metis 应把这些思想收敛成一套可嵌入不同业务 agent 的 harness package，并把“降低模型推理负担”作为第一设计原则。

---

## 3. 本地三个项目的 harness 能力总览

### 3.1 Aurora 当前 harness 层

关键文件：

- `aurora/agent.py`
- `aurora/hooks.py`
- `aurora/tools/registry.py`
- `aurora/context.py`
- `aurora/memory/session_db.py`
- `aurora/loop.py`
- `aurora/swarm/orchestrator.py`
- `aurora/swarm/decomposer.py`
- `aurora/swarm/roles.py`
- `aurora/guardrails.py`
- `aurora/security.py`
- `aurora/recovery.py`
- `aurora/skills/manager.py`
- `aurora/mcp/client.py`
- `aurora/mcp_server.py`
- `aurora/sandbox/guard.py`
- `aurora/sandbox/policy.py`
- `aurora/quality/auditor.py`
- `aurora/quality/optimizer.py`

Aurora 的 harness 结构非常清晰。`AuroraAgent` 在初始化时创建：

- `HookManager`
- `ToolRegistry`
- `LoopManager`
- `ConversationHistory`
- `MemoryManager`
- LLM provider client
- `ContextCompressor`
- `ToolGuardrails`
- `SecurityManager`
- `RecoveryManager`
- `SwarmOrchestrator`

这说明 Aurora 的底座已经具备一个标准 agent runtime 的主要环节。它的问题不是有没有 harness，而是 harness 还较轻，很多模块是可用骨架，但生产级深度不如 Sophia 与 Hermes。

Aurora 的优点：

1. 架构易懂，适合作为 Metis 最小内核模型。
2. ToolRegistry 很干净，注册、schema 暴露、dispatch、hook 拦截、异常 JSON 化都清楚。
3. HookManager 是统一扩展点，所有机制可挂到 tool、agent、swarm、loop、goal、memory、context、security 事件上。
4. ContextCompressor 简单直接，能在上下文超过阈值时总结旧消息并保留近期消息。
5. SwarmOrchestrator 有角色推荐、任务分解、角色工具白名单、并发执行、结果综合。
6. LoopManager 支持后台循环、暂停、恢复、停止、持久化配置。
7. Guardrails 有连续调用限制和速率限制。
8. SecurityManager 有提示注入检测、凭据脱敏、路径校验。
9. RecoveryManager 有错误分类和重试建议。

Aurora 的不足：

1. Tool call loop 的实现不如 Hermes 严谨，对 tool result budget、无进展循环、失败重复调用等控制较弱。
2. ContextCompressor 的 token 估算较粗糙，且总结提示存在编码损坏，说明国际化/编码链路需要规范。
3. Swarm 的触发规则和角色匹配偏关键字启发式，适合轻量场景，但对 9B 模型应加入更强的结构化计划和强制验收。
4. RecoveryManager 只提出重试建议，没有深度绑定实际 retry executor。
5. LoopManager 当前 tick 主要更新状态和发 hook，执行动作的桥接需要更明确。
6. 对交付物、证据链、质量门、artifact registry 的抽象不足。

Aurora 对 Metis 的可抽取价值：

- 最小 agent kernel 形态。
- HookManager 事件总线。
- ToolRegistry 的最简洁实现。
- Role filtered tool registry。
- Session + message + memory 的 SQLite 持久化。
- Loop/Swarm/Recovery/Guardrail 的基础接口。

### 3.2 Sophia 当前 harness 层

关键文件：

- `sophia/agent.py`
- `sophia/task_harness.py`
- `sophia/autopilot.py`
- `sophia/hooks.py`
- `sophia/tools/registry.py`
- `sophia/context.py`
- `sophia/memory.py`
- `sophia/goal.py`
- `sophia/loop.py`
- `sophia/subagent.py`
- `sophia/swarm/orchestrator.py`
- `sophia/swarm/analyzer.py`
- `sophia/swarm/decomposer.py`
- `sophia/swarm/synthesizer.py`
- `sophia/guardrails.py`
- `sophia/recovery.py`
- `sophia/credentials.py`
- `sophia/scheduler.py`
- `sophia/kanban.py`
- `sophia/plugins.py`
- `sophia/security.py`
- `sophia/skills/manager.py`
- `sophia/skills/factory.py`
- `sophia/learning.py`
- `sophia/snapshot.py`
- `sophia/trajectory.py`
- `sophia/workspace_context.py`

Sophia 是三个项目里最像“完整智能体 harness”的项目。它在 `SophiaAgent.__init__` 里明确分层：

- P0 Core：goal、swarm、subagents、loops。
- P1 Stability：memory、context_compressor、autopilot、credentials、recovery、guardrails。
- P2 Engineering：scheduler、kanban、plugins、security、skills、skill_factory。
- P3 Advanced：learning、snapshot、trajectory、experiments。

这套分层对 Metis 很有价值。它说明一个生产级 agent harness 不能只靠 chat loop，而要包含目标管理、循环任务、子智能体、恢复、安全、学习、轨迹、快照和插件。

Sophia 的 `task_harness.py` 是最值得抽取的部分之一。它不是业务工具，而是一个“任务质量合约生成器”。其中 `build_task_harness_prompt` 强制模型：

1. 把任务拆成原子步骤。
2. 每步必须有 action、required inputs、expected output、verification method、done condition。
3. 一次只执行一步。
4. 重要 claim 要关联 workspace evidence、tool output 或 explicit limitation。
5. 终稿前必须跑质量检查。
6. 禁止伪造数据、引用、文件、工具输出、完成状态。
7. 用户要求文件时必须给 artifact path。
8. 最终必须包含 completion proof。

这正是小模型需要的外骨骼。9B 模型不要期待它“自觉严谨”，要把严谨变成 runtime contract。

Sophia 的 `autopilot.py` 也非常有价值。它把自动化分为三层：

1. Intent Router：根据用户输入注入系统提示。
2. Execution Monitor：通过 hook 观察工具序列，发现重复流程后生成 skill。
3. System Prompt Appendix：把默认操作手册注入系统提示。

这说明 Metis 可以有一个“轻量 autopilot”模块：它不替代主 agent，而是在每轮前后提供结构化干预。

Sophia 的 Swarm 比 Aurora 更完整。它包含：

- `TaskAnalyzer`
- `TaskDecomposer`
- `RoleTemplateBank`
- `SwarmBus`
- `ResultSynthesizer`
- `SwarmExecutionRecord`
- stage-based plan
- parallel / sequential stage execution
- streaming swarm events
- token aggregation
- execution records

这比 Aurora 的简单并发角色执行更适合作为 Metis swarm v1 的参考。

Sophia 的不足：

1. 当前仍有明显业务耦合。很多机制直接围绕研究/论文/实证分析。
2. 工具数量很多，容易造成 tool schema 膨胀，小模型会被工具列表压垮。
3. 编码问题存在，说明中文文本、文件编码、跨机器提交需要规范。
4. 许多模块是强能力模块，但 Metis 不能把它们全部默认塞进 harness 核心，否则底座会变重。
5. `task_harness.py` 是 prompt contract，但还不是强制 runtime state machine。小模型场景下应把 prompt contract 下沉成结构化执行器。

Sophia 对 Metis 的可抽取价值：

- 分层机制：Core / Stability / Engineering / Advanced。
- Task Harness 合约。
- Autopilot 三层机制。
- GoalManager、LoopManager、SubAgentManager、SwarmOrchestrator。
- Memory + Context + Trajectory + Snapshot。
- SkillManager + SkillFactory。
- Kanban / Scheduler / Plugin / Experiment 的可扩展工程化思路。

### 3.3 Hermes 当前 harness 层

关键文件：

- `environments/agent_loop.py`
- `agent/context_engine.py`
- `agent/context_compressor.py`
- `agent/memory_manager.py`
- `agent/memory_provider.py`
- `agent/prompt_builder.py`
- `agent/tool_guardrails.py`
- `agent/tool_result_classification.py`
- `tools/tool_result_storage.py`
- `tools/budget_config.py`
- `agent/file_safety.py`
- `agent/retry_utils.py`
- `agent/transports/base.py`
- `agent/transports/*.py`
- `environments/tool_call_parsers/*.py`
- `agent/skill_preprocessing.py`
- `agent/skill_utils.py`
- `agent/shell_hooks.py`
- `agent/trajectory.py`
- `gateway/*.py`
- `acp_adapter/*.py`

Hermes 的 harness 层更接近通用 agent runtime。它不像 Aurora/Sophia 那样以业务功能为中心，而是大量处理模型兼容、工具循环、上下文、安全、gateway、transport、环境和协议。

Hermes 的 `HermesAgentLoop` 是标准工具调用循环：

1. 输入 OpenAI-style messages。
2. 构造 chat completion kwargs。
3. 根据 provider/server 发起请求。
4. 提取 reasoning。
5. 检查 tool calls。
6. dispatch 工具。
7. 记录 tool errors。
8. 持续多轮，直到自然停止或达到 max_turns。

它支持任何返回 ChatCompletion + tool_calls 的服务，包括 OpenAI、vLLM、SGLang、OpenRouter，以及带客户端 parser 的 ManagedServer。这对 9B 模型尤其重要，因为很多 9B 模型并不稳定支持标准 tool calling，必须靠 parser 和 prompt 约束适配。

Hermes 的 `ContextEngine` 抽象非常关键。它把上下文管理变成可插拔接口：

- `update_from_response`
- `should_compress`
- `compress`
- `should_compress_preflight`
- `has_content_to_compress`
- `on_session_start`
- `on_session_end`
- `get_tool_schemas`
- `handle_tool_call`
- `get_status`
- `update_model`

这比 Aurora/Sophia 的固定 ContextCompressor 更适合 Metis。Metis 应直接采用类似 ContextEngine 的抽象，让不同场景可以选择 compressor、DAG memory、retrieval memory、workspace index、episodic store 等策略。

Hermes 的 `tools/tool_result_storage.py` 是小模型友好架构的关键。它把大工具输出分为三层防御：

1. 单个工具内部先截断。
2. 单个工具结果超阈值时写入 sandbox 文件，只把 preview + path 放回上下文。
3. 单轮多个工具结果总量超预算时，把最大结果 spill 到文件，直到低于预算。

这个机制非常重要。小模型上下文窗口较小，把大输出直接塞回去会造成灾难。Metis 必须内建“工具结果外置存储 + 可读 preview + file pointer”。

Hermes 的 `tool_guardrails.py` 也很重要。它不是简单限流，而是判断：

- exact failed call 重复。
- same tool failure 重复。
- idempotent no progress。
- mutating tool 与 idempotent tool 区分。
- allow / warn / block / halt 四类动作。
- 工具参数通过 canonical JSON + hash 标识，避免泄露原始参数。

这比 Aurora/Sophia 的连续调用计数更强。Metis 应采用 Hermes 的思想作为 tool loop circuit breaker。

Hermes 的 `prompt_builder.py` 有两个值得抽取的能力：

1. 上下文文件注入前扫描 prompt injection、隐藏字符、可疑 shell/secret 读取片段。
2. 系统提示由 identity、platform hints、skills index、context files、memory、ephemeral prompts 组合而成。

Metis 应有 Prompt Assembly Pipeline，而不是一个巨大的固定 system prompt。

Hermes 的不足：

1. 体系很强但也很复杂，不适合直接整体迁移。
2. 许多模块与 Hermes CLI、gateway、provider、工具生态高度绑定。
3. 对 Metis 初始版本来说，完整复制会拖慢落地。
4. 部分注释/文本编码显示有问题，但核心架构清楚。

Hermes 对 Metis 的可抽取价值：

- ProviderTransport 抽象。
- ContextEngine 插件化。
- 大工具输出持久化和预算。
- Tool-call parser 适配不同模型。
- Tool loop guardrail controller。
- File safety 读写边界。
- Memory context fencing 和 streaming scrubber。
- Prompt assembly pipeline。
- Gateway/ACP 多入口架构思想。
- Jittered retry。

---

## 4. Harness 层能力分类

为了避免把业务能力混入 Metis，这里按 harness 层抽象重新分类。

### 4.1 Agent Kernel

职责：

- 管理一次用户请求的执行生命周期。
- 构建 messages。
- 调用模型。
- 解析响应。
- 执行工具。
- 追加工具结果。
- 判断是否继续。
- 形成最终响应。

来源参考：

- Aurora：`AuroraAgent._call_llm`
- Sophia：`SophiaAgent._run_internal` / `run` / streaming run
- Hermes：`HermesAgentLoop`

Metis 设计建议：

```text
MetisAgent
  - RuntimeConfig
  - ProviderRouter
  - PromptAssembler
  - ToolRegistry
  - HookBus
  - StateStore
  - ContextEngine
  - MemoryManager
  - ArtifactStore
  - QualityGateRunner
  - ExecutionController
```

对 9B 模型的关键约束：

- max_turns 必须较小且可配置。
- 每轮必须有 tool loop guardrail。
- 不要一次暴露全部工具。
- 每个任务阶段只暴露相关工具。
- 模型输出最好要求结构化 JSON 或 tagged blocks。
- 工具调用失败要给模型短、明确、可行动的错误。
- 最终回答前必须有 runtime 检查，不只靠模型自检。

### 4.2 Tool Registry 与 Tool Router

职责：

- 统一注册工具。
- 生成 tool schema。
- 校验参数。
- 执行 handler。
- 统一 JSON 结果。
- 发出 pre/post/error hook。
- 支持工具白名单、角色工具权限、阶段工具权限。

来源参考：

- Aurora：`aurora/tools/registry.py`
- Sophia：`sophia/tools/registry.py`
- Hermes：`model_tools.py`、tool schemas、tool result budget、tool guardrails

Metis 应把工具系统升级为：

```text
ToolRegistry
  - register(tool_spec)
  - get_schema(filter)
  - dispatch(call, context)
  - validate_args(schema, args)
  - normalize_result(result)
  - persist_large_result(result)
  - classify_result(result)
  - emit hook events

ToolSpec
  - name
  - description
  - parameters
  - handler
  - category
  - side_effect_level: read | write | network | destructive
  - max_result_chars
  - allowed_roles
  - required_permissions
  - retry_policy
  - verification_policy
```

Metis 不能只维护 `name -> handler`，因为 9B 模型需要 runtime 帮它做选择和约束。工具 metadata 必须包含副作用等级、输出预算、权限、重试策略和验证策略。

建议工具分层：

1. Core Tools：文件读、目录列举、搜索、写文件、patch、shell、HTTP、browser。
2. State Tools：goal、todo、memory、artifact、snapshot、trajectory。
3. Control Tools：plan、step_complete、quality_check、ask_review、loop_create。
4. Extension Tools：业务 agent 自己注册。

对小模型，默认只暴露 Core Read + State + Plan；写操作、shell、网络、browser 应按阶段开启。

### 4.3 Hook/Event Bus

职责：

- 所有机制通过事件解耦。
- 支持优先级。
- 支持上下文修改。
- 支持 blocked 短路。
- 支持观测、审计、学习、恢复。

来源参考：

- Aurora：`HookManager` 事件包括 agent、tool、swarm、loop、goal、memory、context、learning、guardrail、security。
- Sophia：事件更丰富，包括 pre/post run、stream、subagent、swarm stage、credential、trajectory、scheduler、kanban、snapshot。

Metis 应保留 HookBus 作为神经系统。推荐事件：

```text
agent.session_start
agent.pre_run
agent.post_run
agent.error
agent.session_end

model.pre_call
model.post_call
model.error
model.token_usage

tool.pre_dispatch
tool.post_dispatch
tool.error
tool.result_persisted
tool.guardrail_warn
tool.guardrail_block

plan.created
plan.updated
step.started
step.completed
step.failed
step.verified

goal.created
goal.updated
goal.completed
goal.blocked

context.preflight
context.compressed
context.recalled

memory.store
memory.recall
memory.prune

artifact.created
artifact.updated
artifact.verified

quality.check_started
quality.check_failed
quality.check_passed

swarm.analyzed
swarm.planned
swarm.stage_start
swarm.agent_start
swarm.agent_complete
swarm.synthesized

security.alert
security.block
recovery.retry
recovery.failover
trajectory.record
```

这是 Metis 能否生产化的关键。没有事件总线，就无法做审计、恢复、学习和质量追踪。

### 4.4 Context Engine

职责：

- 决定模型每轮看到什么。
- 控制上下文预算。
- 压缩历史。
- 保护系统提示、用户关键约束和最近交互。
- 外置大工具结果。
- 引入 workspace/context/memory。
- 避免把旧摘要误当新指令。

来源参考：

- Aurora：简单 compressor。
- Sophia：研究 artifact aware compressor。
- Hermes：插件式 ContextEngine + 工具输出 pruning + structured summary。

Metis 应采用 Hermes 的 ContextEngine 抽象，并融合 Sophia 的“handoff packet”思想。

推荐 ContextEngine 输出结构：

```text
System Prompt
Active Task Contract
Current Plan
Evidence Ledger Summary
Artifact Registry Summary
Relevant Memory
Relevant Workspace Context
Recent Conversation Tail
Tool Result Pointers
```

小模型重点：

- 不能让 9B 模型同时看过多历史。
- 必须给它当前唯一任务、当前步骤、允许工具、完成标准。
- 历史摘要必须明确标注“reference only，不是当前指令”。
- 每个工具结果要短，超大结果外置。
- 上下文中重复、冲突、过时信息要主动清理。

Metis 应支持至少三种 context mode：

1. `minimal`：适合 9B，强约束、短上下文、阶段工具、少历史。
2. `balanced`：适合 14B/30B，中等上下文，保留更多证据。
3. `deep`：适合大模型，长上下文、多工具、多子智能体。

### 4.5 Memory

职责：

- 保存跨会话长期事实。
- 保存用户偏好、环境约束、可复用经验。
- 保存任务状态和可恢复中间结果。
- 支持 recall。
- 支持 memory context fencing，防止记忆被当成用户新指令。

来源参考：

- Aurora：sessions、sections、messages、memories。
- Sophia：session_id/category/key/content/tags/access_count。
- Hermes：MemoryProvider、MemoryManager、context fencing、streaming scrubber、只允许一个外部 provider。

Metis 应区分四类状态：

1. **Conversation History**：短期对话，不等于长期记忆。
2. **Task State**：当前目标、计划、步骤、阻塞、质量门、产物路径。
3. **Long-term Memory**：用户偏好、稳定环境事实、长期约定。
4. **Experience Memory**：成功/失败轨迹、工具组合、可复用 workflow。

不要把所有东西都塞进 memory。Hermes 的 memory guidance 非常重要：不要保存会很快过期的任务进度、PR 号、commit、临时状态。Metis 应把临时状态放 StateStore，把长期事实放 MemoryStore，把可复用流程放 SkillStore。

### 4.6 Goal / Plan / Step State Machine

职责：

- 把复杂任务变成可执行计划。
- 保存每步状态。
- 每步有 done condition。
- 只有验证通过才能完成。
- 支持 blocked。
- 支持 resume。

来源参考：

- Sophia：`GoalManager`、`task_harness.py`。
- Hermes：Kanban task protocol、todo store、DeepAgents 方向的 planning/todo。

Metis 必须把 Sophia 的 prompt-level contract 下沉为 runtime-level state machine。推荐结构：

```text
Goal
  id
  objective
  status: active | complete | blocked | failed
  constraints
  acceptance_criteria
  created_at
  updated_at

Plan
  goal_id
  version
  steps[]

Step
  id
  title
  action
  required_inputs
  expected_output
  allowed_tools
  verification_method
  done_condition
  status: pending | running | done | failed | blocked
  evidence_refs[]
  artifact_refs[]
  errors[]
```

小模型不应该自己记住步骤状态。Metis 要在每轮 prompt 里注入当前 step，并在工具侧强制 step transition。

### 4.7 Loop / Scheduler

职责：

- 后台循环任务。
- 定时任务。
- 轮询任务。
- 自动重试。
- 长任务 heartbeat。

来源参考：

- Aurora：`LoopManager` 后台线程、pause/resume/stop。
- Sophia：`LoopManager`、`CronScheduler`。
- Hermes：cron、gateway session、kanban heartbeat。

Metis 建议：

- Loop 不要直接等于“反复问模型”。它应是一个调度器，触发一个受控 run。
- 每次 loop tick 必须有 max_turns、timeout、tool budget、quality gate。
- Loop 状态必须持久化。
- 长任务必须 heartbeat。
- 连续失败必须熔断。

### 4.8 SubAgent / Swarm

职责：

- 复杂任务拆分。
- 专家角色并行处理。
- 工具权限隔离。
- 上下文隔离。
- 结果综合。
- 审核团队。

来源参考：

- Aurora：简单 swarm，角色匹配、白名单工具、并发执行。
- Sophia：stage-based swarm，analyzer/decomposer/synthesizer/execution record。
- CrewAI：role-based collaboration。
- DeepAgents：subagent delegation + filesystem state。

Metis 的 Swarm 应分两层：

1. **Internal SubTask Delegation**：短任务、同一进程、同一 state store、隔离上下文。
2. **Durable Work Board**：长任务、跨进程/跨机器、类似 Kanban，可恢复、可审核。

对 9B 模型，Swarm 不一定意味着多个 9B 模型一起聊天。更合理的是：

- 主模型只做路由和步骤控制。
- 子任务模型拿到很小、很明确的 prompt。
- 每个子 agent 工具更少。
- 每个子 agent 输出结构化结果。
- 综合器不直接信任子结果，要有 evidence refs 和 quality checks。

角色模板应包含：

```text
role_id
name
mission
scope
allowed_tools
forbidden_actions
input_contract
output_schema
quality_checks
handoff_format
```

审核团队不是“再问一个模型说好不好”。审核必须绑定：

- 文件是否存在。
- 测试是否运行。
- 证据是否引用。
- 需求关键词是否覆盖。
- 产物是否可打开。
- 数据是否真实。
- 工具输出是否真实。
- 是否存在模拟/伪实现。

### 4.9 Quality Gate 与 Evidence Ledger

职责：

- 防止模型“写完就算完成”。
- 把验收标准变成可执行检查。
- 每个重要 claim 有证据来源。
- 最终交付前自动检查。

来源参考：

- Sophia：task_harness 的 evidence ledger、quality checks、completion proof。
- Aurora：quality auditor/optimizer。
- Hermes：trajectory、tool result classification、file safety。

Metis 应内置 QualityGateRunner：

```text
QualityGate
  id
  name
  scope
  check_type: static | tool | model_judge | human | test
  command/tool
  pass_condition
  failure_action
```

推荐默认质量门：

1. Requirement Coverage Gate：用户需求关键词是否全部覆盖。
2. No-Fabrication Gate：是否存在无证据数据、虚假工具结果、虚假路径。
3. Artifact Existence Gate：承诺的文件是否真实存在。
4. Test Gate：代码项目是否跑了测试。
5. Syntax/Compile Gate：代码是否能编译。
6. Link/Reference Gate：外部引用是否可追踪。
7. Security Gate：是否暴露凭据、越权路径、危险命令。
8. Context Drift Gate：最终输出是否仍回答最新用户请求。
9. Small Model Completion Gate：模型是否仅写计划而没执行。

EvidenceLedger 应保存：

```text
claim_id
claim
source_type: tool_output | file | command | web | user | model_inference
source_ref
confidence
verified_at
```

对小模型，EvidenceLedger 不只是报告用途，也应该参与 prompt：模型每次总结时只能引用 ledger 中已有证据。

### 4.10 Artifact Store

职责：

- 保存交付物。
- 记录产物类型、路径、生成步骤、验证状态。
- 支持最终报告引用。

来源参考：

- Sophia：document_delivery、snapshot、result_store。
- Hermes：tool_result_storage、filesystem backend。
- Aurora：export/presentation/pdf/docx。

Metis 需要一个通用 ArtifactStore，不绑定 docx/ppt/pdf 业务。

```text
Artifact
  id
  type: markdown | docx | pdf | pptx | png | csv | json | code | report | log
  path
  created_by_step
  source_refs
  checksum
  validation_status
  metadata
```

这能解决“模型说生成了文件但其实没有”的问题。最终回答不应凭模型文字，而应查询 ArtifactStore。

### 4.11 Provider / Transport / Parser

职责：

- 支持 OpenAI-compatible、Anthropic、Gemini、OpenRouter、本地 vLLM/SGLang/Ollama/LM Studio。
- 消息格式转换。
- 工具 schema 转换。
- 响应归一化。
- reasoning 提取。
- tool call 解析。
- credential failover。

来源参考：

- Hermes：`ProviderTransport`、tool_call_parsers、retry_utils、credential_pool。
- Sophia：providers/base、openai_compat、anthropic。
- Aurora：简单 provider setup。

Metis 要重点服务 9B 免费模型，就必须把 parser 做成一等公民。很多 9B 模型可能输出：

```text
<tool_call>{"name":"read_file","arguments":{"path":"..."}}</tool_call>
```

或 Markdown JSON，或错误 JSON，或漏括号。Metis 需要：

- Strict parser。
- Repair parser。
- Fallback no-tool mode。
- Tool-call format prompt。
- Tool-call validation feedback。

Provider 输出应归一化为：

```text
NormalizedResponse
  content
  reasoning
  tool_calls[]
  finish_reason
  usage
  raw
```

### 4.12 Security / Sandbox

职责：

- 路径安全。
- 写入 denylist。
- prompt injection 检测。
- context file 扫描。
- 凭据脱敏。
- tool permission。
- sandbox execution。

来源参考：

- Aurora：SecurityManager、sandbox policy。
- Sophia：SecurityManager、WorkspaceGuard。
- Hermes：file_safety、prompt_builder context scan、tool_guardrails。

Metis 默认应有安全边界：

1. 所有写操作默认限制在 workspace。
2. 禁止写入 `.ssh`、`.aws`、`.kube`、`.docker`、shell rc、`.env`、系统目录。
3. 读内部 skill/cache 文件要通过专用工具，不允许直接读。
4. context 文件注入前扫描隐藏指令、隐藏 unicode、HTML hidden div、secret exfiltration。
5. 工具 schema 标注 side effect。
6. SubAgent 只获得任务需要的工具。

### 4.13 Skill / Plugin

职责：

- 保存可复用工作流。
- 基于任务匹配技能。
- 技能可更新。
- 插件扩展工具、context engine、memory provider、output adapter。

来源参考：

- Sophia：SkillManager、SkillFactory、PluginManager。
- Hermes：SKILL.md preprocessing、skills index、skill template vars、inline shell 可控。

Metis 应区分：

- Skill：面向模型的操作手册和流程。
- Plugin：面向代码的扩展包。
- Template：面向输出的结构模板。
- Adapter：面向业务场景的桥接层。

对小模型，Skill 不应该太长。应支持：

- skill index 先注入短描述。
- 命中后再加载完整 skill。
- skill 内容可裁剪。
- skill 可带 tool policy。
- skill 可带 quality gates。

---

## 5. Metis 推荐总体架构

推荐目录结构：

```text
metis-agent-harness/
  pyproject.toml
  README.md
  docs/
    architecture.md
    small-model-playbook.md
    module-spec.md
    security-model.md
    extension-guide.md
  metis/
    __init__.py
    agent.py
    runtime/
      loop.py
      execution_controller.py
      state.py
      events.py
      hooks.py
      errors.py
      budgets.py
    providers/
      base.py
      openai_compat.py
      anthropic.py
      local.py
      router.py
      parsers/
        base.py
        openai.py
        hermes_xml.py
        qwen.py
        json_repair.py
    prompts/
      assembler.py
      system.py
      contracts.py
      context_files.py
    tools/
      registry.py
      spec.py
      dispatcher.py
      result_store.py
      guardrails.py
      permissions.py
    context/
      engine.py
      compressor.py
      workspace.py
      summarizer.py
    memory/
      provider.py
      sqlite.py
      manager.py
      fences.py
    planning/
      goal.py
      plan.py
      step.py
      task_harness.py
      todo.py
    quality/
      gates.py
      evidence.py
      auditor.py
      verifier.py
    artifacts/
      store.py
      manifest.py
      validators.py
    swarm/
      analyzer.py
      decomposer.py
      roles.py
      orchestrator.py
      bus.py
      synthesizer.py
    loops/
      scheduler.py
      loop_manager.py
      heartbeat.py
    skills/
      manager.py
      index.py
      loader.py
      factory.py
    plugins/
      manager.py
      api.py
    security/
      paths.py
      prompt_injection.py
      redaction.py
      sandbox.py
    telemetry/
      trajectory.py
      traces.py
      metrics.py
      logs.py
    adapters/
      cli.py
      web.py
      mcp_server.py
      acp.py
  tests/
```

核心依赖方向必须保持单向：

```text
Application Adapter
  -> Metis Agent
    -> Runtime Kernel
      -> Provider / Tool / Context / State

Business Tools
  -> ToolRegistry
  -> HookBus
  -> ArtifactStore

No business module should import Metis internal application-specific code.
```

也就是说，未来任何领域 agent，比如商业计划、论文、法律、医疗、财务、代码、设计，都只能通过 adapter 注册：

- tools
- prompt fragments
- skills
- quality gates
- artifact validators
- role templates
- output adapters

不能反向改 Metis 核心。

---

## 6. Metis 运行流程设计

### 6.1 标准单轮流程

```text
1. receive user input
2. create or resume session
3. emit agent.pre_run
4. classify task complexity
5. build or update goal
6. build task contract
7. select context mode
8. recall memory
9. scan workspace context if needed
10. select tools for current stage
11. assemble prompt
12. call model
13. parse response
14. if tool calls:
    14.1 validate tool calls
    14.2 apply tool guardrails
    14.3 dispatch tools
    14.4 persist large results
    14.5 record evidence/artifacts
    14.6 append compact tool results
    14.7 continue next turn
15. if final:
    15.1 run quality gates
    15.2 if fail, repair
    15.3 if pass, finalize
16. save trajectory
17. emit agent.post_run
```

### 6.2 复杂任务流程

```text
1. task classifier marks complex
2. GoalManager creates goal
3. Planner creates Plan with Steps
4. each Step exposes only relevant tools
5. StepExecutor runs model/tool loop
6. Verifier checks done condition
7. EvidenceLedger records proof
8. ArtifactStore records outputs
9. failed step triggers RecoveryManager
10. repeated failure triggers blocked or swarm escalation
11. final Synthesizer builds final deliverable
12. QualityGateRunner verifies final deliverable
```

### 6.3 Swarm 流程

```text
1. SwarmAnalyzer decides if swarm needed
2. Decomposer creates stages
3. RoleResolver picks role templates
4. each AgentSpec receives:
   - task
   - scope
   - allowed tools
   - output schema
   - evidence requirement
5. stage executes sequential or parallel
6. results written to SwarmBus
7. Synthesizer combines only verified results
8. Auditor reviews synthesis
9. final result goes through quality gates
```

---

## 7. 9B 小模型专项设计

这是 Metis 的核心目标。本节单独展开。

### 7.1 小模型的失败模式

从当前三个项目和外部 agent 框架经验看，9B 模型常见失败包括：

1. 计划写得漂亮，但不执行。
2. 执行了第一步后忘记后续步骤。
3. 工具参数 JSON 出错。
4. 工具失败后重复同一个错误调用。
5. 搜索/读取大量内容后无法提炼。
6. 看到太多工具，不知道该用哪个。
7. 看到太长系统提示，忽略关键约束。
8. 自检时只说“已检查”，没有真实检查。
9. 对文件是否真实存在没有概念。
10. 容易受旧摘要、旧用户请求、工具输出里的指令干扰。

### 7.2 Metis 对小模型的补偿策略

#### 策略 1：短上下文 + 强状态

不要让 9B 模型背负完整历史。它每次只需要：

- 当前目标。
- 当前步骤。
- 当前允许工具。
- 当前输入。
- 当前完成标准。
- 最近少量上下文。
- 必要证据摘要。

状态放数据库，不放模型脑内。

#### 策略 2：阶段工具暴露

9B 模型不能面对 100 个工具。Metis 应按阶段暴露：

- 探索阶段：read/list/search/web。
- 计划阶段：goal/plan/todo。
- 执行阶段：少数执行工具。
- 验证阶段：test/compile/check/artifact validators。
- 交付阶段：artifact/finalize。

工具 schema 数量建议：

- 9B：每轮 5-12 个工具。
- 14B：每轮 10-25 个工具。
- 30B+：可更多，但仍应按任务过滤。

#### 策略 3：结构化输出

小模型自由文本容易漂。每个关键阶段都要求固定输出：

```json
{
  "status": "needs_tool|step_done|blocked|final",
  "reason": "...",
  "tool_calls_intent": [],
  "evidence_refs": [],
  "next_step": "..."
}
```

即使底层 provider 不支持 JSON mode，也可以用 parser 做校验和重试。

#### 策略 4：工具调用 parser + repair

必须兼容：

- OpenAI tool_calls。
- Hermes `<tool_call>` 标签。
- Qwen/Hermes 风格。
- Markdown fenced JSON。
- 裸 JSON。

解析失败时不要直接终止，而是给模型极短反馈：

```text
Your tool call JSON was invalid. Return exactly one valid tool call using this schema...
```

最多 repair 1-2 次，之后降级。

#### 策略 5：大输出外置

Hermes 的 tool result storage 必须成为 Metis 核心。对 9B：

- 单工具结果超过 4K-8K 字符即外置。
- 单轮工具结果总预算可设 20K-50K。
- preview 必须包含关键信息和读取路径。
- 模型需要更多时用 read_file(offset, limit)。

#### 策略 6：强制 verification gate

9B 自检不可靠。所以最终完成必须由 runtime 检查：

- 文件存在。
- 命令运行。
- 测试通过。
- 报告字数/结构满足。
- 没有 TODO 占位。
- 没有“示例数据”。
- 证据链存在。

#### 策略 7：模型不可见的审计器

不要让同一个 9B 模型既生成又审核。Metis 可以：

- 用规则审核。
- 用更小的静态工具审核。
- 用第二个模型审核。
- 用同模型但不同 prompt 审核，但必须配合客观检查。

#### 策略 8：失败恢复前置

小模型容易卡住。Metis 必须自动识别：

- 同一工具同一参数失败重复。
- 同一工具不同参数但同类失败。
- 无进展读取。
- 写入失败。
- 测试失败。
- provider rate limit。

并采取：

- 警告。
- 提示换策略。
- block tool call。
- halt turn。
- credential failover。
- fallback provider。
- 降级为非工具回答。

#### 策略 9：技能库短索引

Metis 应把技能作为模型外部程序库：

- system prompt 只放 skill name + 20-80 字描述。
- 命中后加载完整 skill。
- 完整 skill 也应可裁剪。
- 技能中每一步要对应工具和验收。

#### 策略 10：交付物优先

小模型最终回答容易虚。Metis 应把高质量产出变成 artifact-first：

1. 先生成文件。
2. 再验证文件。
3. 再让模型写简短交付说明。

---

## 8. 从三项目抽取到 Metis 的模块映射表

| Metis 模块 | Aurora 来源 | Sophia 来源 | Hermes 来源 | 采用建议 |
|---|---|---|---|---|
| Agent loop | `aurora/agent.py` | `sophia/agent.py` | `environments/agent_loop.py` | 以 Hermes 为 runtime，参考 Aurora 简洁性 |
| Hook bus | `aurora/hooks.py` | `sophia/hooks.py` | shell/gateway hooks 思想 | 以 Sophia 事件全集为基础 |
| Tool registry | `aurora/tools/registry.py` | `sophia/tools/registry.py` | tool result/storage/guardrails | Registry 用 Aurora/Sophia，预算和熔断用 Hermes |
| Context | `aurora/context.py` | `sophia/context.py` | `agent/context_engine.py`、`context_compressor.py` | 采用 Hermes 插件接口，融合 Sophia handoff |
| Memory | `memory/session_db.py` | `memory.py` | `memory_manager.py` | 四类状态分离 |
| Goal/Plan | 较弱 | `goal.py`、`task_harness.py` | todo/kanban 思想 | Sophia 为主，做成 runtime state machine |
| Loop | `loop.py` | `loop.py`、`scheduler.py` | cron/gateway | Sophia + Aurora，补 heartbeat |
| Swarm | `swarm/orchestrator.py` | `swarm/*` | delegate/kanban 思想 | Sophia 为主，Aurora 白名单保留 |
| Recovery | `recovery.py` | `recovery.py`、credentials | `retry_utils.py` | Sophia + Hermes jitter |
| Guardrails | `guardrails.py` | `guardrails.py` | `tool_guardrails.py` | Hermes 为主 |
| Security | `security.py` | `security.py`、workspace guard | `file_safety.py`、prompt scan | Hermes 为主 |
| Skill | `skills/manager.py` | `skills/*` | skill preprocessing/index | Hermes + Sophia |
| Artifact | export modules | result_store/snapshot/document_delivery | tool_result_storage | 新建独立 ArtifactStore |
| Quality | quality/auditor | task_harness/review | trajectory/tool classification | 新建 QualityGateRunner |
| Provider | simple setup | providers | transports/parsers | Hermes 为主 |

---

## 9. Metis 的最小可行核心

为了最快落地，不建议第一版就做完整平台。建议 v0.1 只做核心：

1. `HookBus`
2. `ToolRegistry`
3. `ProviderTransport`
4. `AgentLoop`
5. `ContextEngine`
6. `StateStore`
7. `Goal/Plan/Step`
8. `ToolGuardrailController`
9. `ToolResultStore`
10. `ArtifactStore`
11. `QualityGateRunner`
12. `PromptAssembler`
13. CLI adapter

v0.1 不需要：

- 完整 Web UI。
- 完整 Swarm。
- 多平台 Gateway。
- 复杂插件市场。
- 大量内置业务工具。
- 复杂评测平台。

v0.1 的标准是：能让一个 9B OpenAI-compatible 模型完成一个多步骤文件/报告/代码类任务，并真实写出产物、验证产物、记录证据。

---

## 10. Metis 的推荐数据模型

### 10.1 SQLite 表

建议默认 SQLite，后续可替换 Postgres。

```sql
sessions(
  id TEXT PRIMARY KEY,
  created_at TEXT,
  updated_at TEXT,
  model TEXT,
  workspace TEXT,
  status TEXT
)

messages(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT,
  role TEXT,
  content TEXT,
  metadata_json TEXT,
  created_at TEXT
)

goals(
  id TEXT PRIMARY KEY,
  session_id TEXT,
  objective TEXT,
  status TEXT,
  acceptance_json TEXT,
  created_at TEXT,
  updated_at TEXT
)

plans(
  id TEXT PRIMARY KEY,
  goal_id TEXT,
  version INTEGER,
  status TEXT,
  created_at TEXT
)

steps(
  id TEXT PRIMARY KEY,
  plan_id TEXT,
  order_index INTEGER,
  title TEXT,
  action TEXT,
  expected_output TEXT,
  verification_method TEXT,
  done_condition TEXT,
  status TEXT,
  metadata_json TEXT
)

tool_calls(
  id TEXT PRIMARY KEY,
  session_id TEXT,
  step_id TEXT,
  tool_name TEXT,
  args_json TEXT,
  result_ref TEXT,
  status TEXT,
  error TEXT,
  created_at TEXT
)

artifacts(
  id TEXT PRIMARY KEY,
  session_id TEXT,
  step_id TEXT,
  type TEXT,
  path TEXT,
  checksum TEXT,
  status TEXT,
  metadata_json TEXT,
  created_at TEXT
)

evidence(
  id TEXT PRIMARY KEY,
  session_id TEXT,
  step_id TEXT,
  claim TEXT,
  source_type TEXT,
  source_ref TEXT,
  confidence REAL,
  created_at TEXT
)

memories(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  scope TEXT,
  category TEXT,
  key TEXT,
  content TEXT,
  tags_json TEXT,
  access_count INTEGER,
  created_at TEXT,
  updated_at TEXT
)

trajectories(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT,
  event TEXT,
  payload_json TEXT,
  created_at TEXT
)
```

### 10.2 文件系统约定

```text
.metis/
  state.db
  artifacts/
  tool-results/
  snapshots/
  trajectories/
  logs/
  skills/
```

工作目录中的 `.metis` 应加入 `.gitignore`，除非用户明确要版本化某些配置。

---

## 11. Prompt 架构

Metis 不应使用单一巨大 system prompt。应使用 PromptAssembler 分层拼装：

```text
Base Identity
Runtime Contract
Current Task Contract
Current Step State
Tool Policy
Memory Context
Workspace Context
Evidence Ledger Summary
Artifact Registry Summary
Skill Instructions
Safety Policy
Output Schema
```

对 9B 模型，PromptAssembler 应短而硬：

```text
You are executing exactly one step.
Current step: ...
Allowed tools: ...
Do not claim completion unless verification passes.
If you need a tool, call exactly one tool.
If you are finalizing, output JSON with status=step_done and evidence_refs.
```

复杂任务的总规则可以放在外部 state，不必每轮全部注入。每轮只注入当前阶段需要的规则。

---

## 12. Tool Result Budget 设计

借鉴 Hermes，Metis 必须内建预算：

```text
per_tool_inline_limit_chars:
  default: 8000
  search: 12000
  read_file: 16000
  shell: 12000
  browser: 10000

per_turn_total_limit_chars:
  small_model: 30000
  balanced: 80000
  deep: 200000

preview_chars:
  small_model: 2000
  balanced: 4000
  deep: 8000
```

当结果超限：

1. 写入 `.metis/tool-results/{tool_call_id}.txt`。
2. 返回 preview。
3. 返回路径。
4. 告诉模型用 `read_artifact_slice` 或 `read_file(offset, limit)`。

这不仅节省上下文，也让证据可追踪。

---

## 13. Quality Gate 详细建议

### 13.1 默认 Gate

1. `artifact_exists`  
   检查承诺的文件是否真实存在。

2. `no_placeholder`  
   检查报告或代码中是否有 TODO、placeholder、示例、mock、dummy、lorem ipsum、待补充等。

3. `requirements_covered`  
   用户需求关键词是否都在计划/产物/最终说明中被处理。

4. `tool_truthfulness`  
   最终回答中的“已运行/已生成/已上传/已测试”必须对应 trajectory 中真实事件。

5. `code_compile`  
   Python 项目跑 `compileall`，JS/TS 项目跑 lint/build，按项目自动识别。

6. `tests_run`  
   若有测试，运行并记录结果。

7. `security_scan_light`  
   检查是否泄露 API key、token、password。

8. `path_safety`  
   检查写入路径是否在 workspace。

9. `final_response_alignment`  
   最终回答是否回答最新用户请求，而不是旧任务。

### 13.2 Gate 失败策略

```text
repairable:
  - run repair prompt
  - rerun gate
  - max repair attempts 2

non_repairable:
  - mark blocked
  - record reason
  - final report must disclose

dangerous:
  - halt
  - emit security.block
```

### 13.3 小模型下的 Gate 优先级

小模型不要跑太多模型裁判。优先使用 deterministic gate：

- 文件检查。
- grep 检查。
- JSON schema 检查。
- 命令退出码。
- 字数/结构检查。
- artifact manifest。

模型裁判只用于语言质量、逻辑一致性这类无法静态判断的部分。

---

## 14. Swarm 与审核团队设计

Metis 的 swarm 不应默认开启。触发条件：

1. 任务涉及多个独立模块。
2. 任务需要研究 + 实现 + 测试 + 审核。
3. 单模型上下文会过长。
4. 用户明确要求多智能体。
5. 当前步骤失败多次，需要第二策略。

推荐内置角色：

1. Planner：拆分任务，定义验收。
2. Explorer：读代码/资料，不改文件。
3. Implementer：实现。
4. Verifier：测试和检查。
5. Auditor：检查是否有伪完成、遗漏、无证据 claim。
6. Synthesizer：合并结果。

每个角色有工具权限：

| 角色 | 默认工具 |
|---|---|
| Planner | read/search/plan |
| Explorer | read/search/web |
| Implementer | read/write/patch/shell |
| Verifier | read/shell/test/artifact |
| Auditor | read/search/trajectory/evidence |
| Synthesizer | read/evidence/artifact |

关键原则：审核团队不能只看模型最终文本，要看 trajectory、artifacts、tests、evidence。

---

## 15. 与 Aurora/Sophia/Hermes 的边界关系

Metis 应成为三者上层或旁路底座，而不是替代业务项目。

未来理想关系：

```text
metis-agent-harness
  provides runtime, control, context, tools, memory, quality

aurora-agent
  imports metis
  registers business-plan / competition tools
  adds domain prompts and artifact validators

sophia-agent
  imports metis
  registers academic/research tools
  adds research-specific quality gates

hermes-agent
  can donate runtime concepts
  may remain independent because it is a broader CLI/gateway product
```

迁移原则：

1. 不要马上把 Aurora/Sophia 改到 Metis。
2. 先在 Metis 中实现核心抽象。
3. 用 adapter 包装 Aurora/Sophia 的一小部分工具验证。
4. 跑真实任务。
5. 再逐步迁移。

---

## 16. 实施路线图

### Phase 0：报告与架构冻结

产物：

- 本报告。
- 模块边界图。
- v0.1 scope。

### Phase 1：Kernel

实现：

- HookBus
- ToolSpec / ToolRegistry
- ProviderTransport base
- OpenAI-compatible provider
- AgentLoop
- NormalizedResponse
- ToolCall parser

验收：

- 能连接一个 OpenAI-compatible endpoint。
- 能注册 3 个工具。
- 能完成多轮工具调用。
- 工具错误返回 JSON。

### Phase 2：State + Task Harness

实现：

- SQLite StateStore
- Goal/Plan/Step
- Task contract
- PromptAssembler

验收：

- 复杂任务自动创建 goal 和 plan。
- 每步有状态。
- 不允许无验证完成。

### Phase 3：Context + Tool Result Budget

实现：

- ContextEngine base
- SimpleCompressor
- ToolResultStore
- per-tool/per-turn budget

验收：

- 大工具输出写入 `.metis/tool-results`。
- prompt 中只保留 preview + path。
- 历史超过阈值自动压缩。

### Phase 4：Quality + Artifact

实现：

- ArtifactStore
- EvidenceLedger
- QualityGateRunner
- 默认 gates

验收：

- 最终报告引用真实 artifact。
- 虚假路径会被拦截。
- 质量失败会触发 repair。

### Phase 5：Small Model Mode

实现：

- small model prompt mode
- limited tool exposure
- parser repair
- step-by-step execution
- tool loop guardrails

验收：

- 使用 9B 模型完成一个真实多步骤任务。
- 有产物。
- 有验证。
- 不伪造完成。

### Phase 6：Swarm

实现：

- analyzer
- decomposer
- role templates
- filtered tools
- stage execution
- synthesizer
- auditor

验收：

- 可并发执行 explorer/verifier。
- 子任务上下文隔离。
- 结果综合引用 evidence。

### Phase 7：Adapters

实现：

- CLI adapter
- MCP server adapter
- business agent adapter example
- research agent adapter example

验收：

- Aurora/Sophia 能以 adapter 形式接入部分工具。
- 不污染 Metis core。

---

## 17. 关键风险

### 风险 1：底座过重

如果 Metis 一开始复制 Sophia/Hermes 全部能力，会变成难维护巨石。应从最小核心开始。

### 风险 2：业务污染

Metis 必须保持场景无关。商业计划、论文、代码、设计等都只能在 adapter 层。

### 风险 3：过度依赖 prompt

Sophia 的 task_harness 很强，但如果只靠 prompt，小模型仍会漂。Metis 要把合约变成状态机和 gate。

### 风险 4：工具 schema 膨胀

小模型不能看太多工具。必须阶段过滤。

### 风险 5：虚假完成

必须使用 trajectory + artifact + evidence 验证最终声明。

### 风险 6：上下文污染

旧摘要、memory、workspace 文件、网页内容都可能带指令。必须 fence 和 scan。

### 风险 7：编码问题

Aurora/Sophia/Hermes 都出现了中文编码显示损坏。Metis 必须统一：

- 源码 UTF-8。
- 文件读写显式 encoding。
- Windows 控制台输出策略。
- 测试覆盖中文 prompt 文件。

### 风险 8：小模型 tool calling 不稳定

必须支持 parser repair 和非标准 tool call 格式。

---

## 18. Metis 设计原则

1. **Harness first, domain later**  
   核心不包含业务场景。

2. **State outside model**  
   长任务状态存在数据库，不靠模型记忆。

3. **Evidence before claim**  
   没有证据的 claim 不能进入最终报告。

4. **Artifact before announcement**  
   先生成和验证产物，再宣布完成。

5. **Tools are capabilities with policy**  
   工具不仅是函数，还有权限、预算、风险、验证策略。

6. **Context is curated, not accumulated**  
   上下文要选择、压缩、外置、隔离。

7. **Small models need narrow tasks**  
   给 9B 的每轮任务必须小、明确、可验证。

8. **Hooks make intelligence observable**  
   所有关键动作必须可记录、可拦截、可复盘。

9. **Quality gates beat self-praise**  
   不相信模型说“已检查”，相信 gate 结果。

10. **Adapters keep core clean**  
    业务能力只能通过 adapter 接入。

---

## 19. 建议的 Metis v0.1 验收任务

为了验证 Metis 是否真的能让 9B 模型高质量工作，建议 v0.1 设一个真实验收任务：

任务类型：给一个已有代码项目生成架构报告并写入文件。

要求：

1. 自动创建 goal。
2. 自动拆分至少 8 个步骤。
3. 每步有 done condition。
4. 读取真实文件。
5. 形成 evidence ledger。
6. 写入 Markdown 报告。
7. 检查报告存在。
8. 检查报告不含 placeholder。
9. 最终回答给出真实路径和 gate 结果。

这个任务与当前需求类似，能很好检验 harness，而不是检验业务知识。

---

## 20. 当前本地项目状态备注

Aurora：

- 当前路径：`D:\LATEXTEST\aurora-agent`
- Git 分支：`master`
- 最新提交：`b5d5ac3`
- 测试状态：已跑通，`764 passed`
- 可作为 Metis lightweight kernel 参考。

Sophia：

- 当前路径：`D:\LATEXTEST\sophia-agent`
- Git 分支：`main`
- 最新远端提交：`e2f892b`
- 本地有三处语法修复未提交：
  - `sophia/cli.py`
  - `sophia/research/meta_analysis.py`
  - `sophia/research/ppt_generator.py`
- 修复后测试状态：已跑通，`2230 passed, 6 skipped`
- 可作为 Metis production harness 机制参考。

Hermes：

- 当前路径：`D:\LATEXTEST\hermes-agent`
- 未在本轮修改。
- 可作为 Metis runtime/provider/context/tool-budget/security 参考。

---

## 21. 最终建议

Metis Agent Harness 的正确方向不是“再做一个 agent 应用”，而是做一套让 agent 应用更容易成功的底座。这个底座最重要的能力不是聊天，而是控制：

- 控制模型看到什么。
- 控制模型能用什么工具。
- 控制任务如何拆分。
- 控制每一步如何验收。
- 控制输出如何落地。
- 控制错误如何恢复。
- 控制证据如何进入最终交付。
- 控制长期经验如何复用。

如果目标是让免费 9B 模型也能产出高质量交付，Metis 必须把“聪明”从模型中移出一部分，放进 harness：

- 规划由 Plan/Step 数据结构承担。
- 记忆由 Memory/StateStore 承担。
- 上下文选择由 ContextEngine 承担。
- 工具选择由 ToolRouter/StagePolicy 承担。
- 防失控由 GuardrailController 承担。
- 验收由 QualityGateRunner 承担。
- 证据由 EvidenceLedger 承担。
- 产物由 ArtifactStore 承担。
- 复盘由 TrajectoryRecorder 承担。

这样，9B 模型不需要一次性完成“理解需求、规划、搜索、执行、验证、总结”的全部认知负担。它只需要在 Metis 给定的窄上下文中完成当前小步骤。整个系统通过状态机、工具、证据、质量门和恢复机制，把许多小步骤稳定地组合成高质量交付。

这就是 Metis 应该从 Aurora、Sophia、Hermes 中抽取出来的核心价值。

