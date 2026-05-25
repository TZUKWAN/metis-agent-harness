# Metis Agent Harness 构建方案

生成时间：2026-05-25  
目标项目目录：`D:\LATEXTEST\metis-agent-harness`  
依据文档：`Metis-Agent-Harness-架构抽取与设计报告.md`

---

## 1. 文档目标

本文档用于把上一份架构抽取报告进一步转化为可执行的 Metis 构建方案。

上一份报告回答的是：

- Aurora、Sophia、Hermes 三个项目分别有哪些 harness 层能力。
- 哪些能力应该抽象为场景无关的智能体底座。
- Metis 应该采用什么总体架构。
- 如何让免费或低成本 9B 模型在该架构上高质量运行。

本文档回答的是：

- Metis 第一版到底怎么建。
- 哪些模块先做，哪些模块后做。
- 每个模块的职责、接口、输入输出、依赖关系是什么。
- 如何组织目录结构。
- 如何设计核心数据模型。
- 如何设计运行流程。
- 如何设计小模型适配模式。
- 如何验证不是“写了个壳”，而是真的具备 harness 底座能力。
- 如何逐步接入 Aurora、Sophia 这类场景 agent。

本文档不包含示例业务数据，不假设未实现能力已经完成，不把业务 agent 能力写入 Metis 核心。Metis 的定位始终是“场景无关的智能体运行底座”。

---

## 2. Metis 的一句话定位

Metis Agent Harness 是一个面向小模型和生产交付的通用智能体底座。它负责把模型包装成可规划、可执行、可验证、可恢复、可复盘、可扩展的 agent runtime，使不同业务项目可以在它之上注册自己的工具、提示、技能、质量门和交付格式。

Metis 不追求成为一个全能业务智能体。它追求成为一个稳定的 agent harness：

- 让模型少猜。
- 让状态外置。
- 让工具受控。
- 让输出可验。
- 让过程可追。
- 让失败可修。
- 让场景可插拔。

---

## 3. 构建原则

### 3.1 Harness 与场景彻底分离

Metis 核心不能写入商业计划书、论文、竞赛、代码修复、法律、医疗、财务等具体场景逻辑。

业务场景只能通过以下扩展点接入：

- Tool plugin
- Prompt fragment
- Skill
- Quality gate
- Artifact validator
- Role template
- Adapter

核心模块只关心通用问题：

- 任务怎么拆。
- 状态怎么存。
- 工具怎么调。
- 上下文怎么控。
- 证据怎么记。
- 产物怎么管。
- 质量怎么验。
- 失败怎么恢复。
- 多智能体怎么协同。

### 3.2 小模型优先

Metis 默认按小模型能力设计，尤其是 9B 级模型。不是先假设模型很强，再做兼容；而是先假设模型不稳定，再用架构补偿。

设计上必须默认：

- 模型会忘。
- 模型会编。
- 模型会提前说完成。
- 模型会生成错误 JSON。
- 模型会反复调用失败工具。
- 模型会被长上下文带偏。
- 模型不擅长在几十个工具中选择。

所以 Metis 的核心是控制和验证，不是堆提示词。

### 3.3 状态外置

Metis 不能把复杂任务状态放在模型上下文里。上下文只是模型当前执行窗口，不能作为真实状态源。

真实状态必须存在：

- SQLite / Postgres。
- Artifact manifest。
- Evidence ledger。
- Trajectory log。
- Snapshot。

模型每轮只读取当前必要状态。

### 3.4 产物优先

Metis 不能只生成回答。凡是用户要交付成果，Metis 应优先生成可检查 artifact：

- Markdown 报告。
- JSON 结果。
- 文档。
- 代码文件。
- 配置文件。
- 图表。
- 日志。
- 测试报告。

最终回答只是 artifact 的说明，不是 artifact 本身的替代品。

### 3.5 验证优先

Metis 不信任模型自称完成。完成必须由 runtime 验证：

- 文件存在。
- 测试执行。
- 命令退出码。
- JSON schema 校验。
- 产物检查。
- 需求覆盖。
- 无占位符。
- 无伪造证据。

### 3.6 渐进构建

Metis 不应第一版就复制 Hermes 的全套 runtime，也不应一次性迁移 Sophia/Aurora。应按阶段构建：

1. 最小可用 agent loop。
2. 状态化任务执行。
3. 工具预算与上下文控制。
4. 质量门与产物管理。
5. 小模型模式。
6. Swarm 与审核。
7. 插件与业务适配。

---

## 4. 总体架构

Metis 推荐采用四层架构。

```text
Application Adapter Layer
  场景工具、领域提示、领域质量门、输出模板、角色模板

Cognitive Harness Layer
  任务合约、计划、步骤、上下文、记忆、技能、证据、质量门、产物

Control Plane Layer
  事件、hook、goal、loop、scheduler、snapshot、trajectory、swarm

Runtime Kernel Layer
  模型调用、transport、tool-call parser、工具派发、预算、错误恢复
```

### 4.1 Runtime Kernel Layer

职责：

- 模型适配。
- 消息格式转换。
- 工具调用循环。
- tool call 解析。
- 工具结果预算。
- provider retry。
- token usage 记录。
- 统一响应结构。

该层尽量不懂任务，只懂“怎么跑”。

### 4.2 Control Plane Layer

职责：

- 生命周期事件。
- hook 拦截。
- goal 状态。
- loop 调度。
- snapshot。
- trajectory。
- swarm execution record。

该层负责“过程控制”和“可观测性”。

### 4.3 Cognitive Harness Layer

职责：

- 任务拆分。
- 当前步骤注入。
- 上下文压缩。
- 记忆召回。
- 证据登记。
- 产物登记。
- 质量验证。
- 技能选择。
- 小模型执行合约。

该层负责“把模型变成靠谱执行者”。

### 4.4 Application Adapter Layer

职责：

- 业务工具注册。
- 业务提示注入。
- 业务技能加载。
- 业务产物验证。
- 业务角色模板。

该层可有多个独立包，例如：

- `metis-aurora-adapter`
- `metis-sophia-adapter`
- `metis-code-agent-adapter`
- `metis-office-agent-adapter`

---

## 5. 推荐目录结构

Metis 初始工程推荐结构如下：

```text
metis-agent-harness/
  pyproject.toml
  README.md
  CHANGELOG.md
  LICENSE
  .gitignore
  docs/
    architecture.md
    build-plan.md
    module-spec.md
    small-model-mode.md
    security-model.md
    extension-guide.md
    testing-strategy.md
  metis/
    __init__.py
    agent.py
    config.py
    runtime/
      __init__.py
      loop.py
      execution_controller.py
      response.py
      errors.py
      budgets.py
    events/
      __init__.py
      hooks.py
      event_types.py
      telemetry.py
    providers/
      __init__.py
      base.py
      router.py
      openai_compat.py
      anthropic.py
      local_openai.py
      parsers/
        __init__.py
        base.py
        openai_native.py
        hermes_xml.py
        qwen_xml.py
        json_block.py
        repair.py
    prompts/
      __init__.py
      assembler.py
      base.py
      contracts.py
      fragments.py
      context_files.py
    tools/
      __init__.py
      spec.py
      registry.py
      dispatcher.py
      permissions.py
      result_store.py
      result_classifier.py
      guardrails.py
      builtin/
        __init__.py
        files.py
        shell.py
        state.py
        artifacts.py
        quality.py
    state/
      __init__.py
      store.py
      sqlite_store.py
      models.py
      migrations.py
    planning/
      __init__.py
      goal.py
      plan.py
      step.py
      planner.py
      task_contract.py
      todo.py
    context/
      __init__.py
      engine.py
      compressor.py
      workspace.py
      summarizer.py
      budget.py
    memory/
      __init__.py
      provider.py
      manager.py
      sqlite_provider.py
      fences.py
    artifacts/
      __init__.py
      store.py
      manifest.py
      validators.py
    evidence/
      __init__.py
      ledger.py
      claims.py
    quality/
      __init__.py
      gates.py
      runner.py
      checks.py
      repair.py
    recovery/
      __init__.py
      manager.py
      retry.py
      classifier.py
    security/
      __init__.py
      paths.py
      redaction.py
      prompt_injection.py
      sandbox.py
    loops/
      __init__.py
      loop_manager.py
      scheduler.py
      heartbeat.py
    swarm/
      __init__.py
      analyzer.py
      decomposer.py
      roles.py
      bus.py
      orchestrator.py
      synthesizer.py
      auditor.py
    skills/
      __init__.py
      manager.py
      loader.py
      index.py
      factory.py
    plugins/
      __init__.py
      api.py
      manager.py
    telemetry/
      __init__.py
      trajectory.py
      metrics.py
      logs.py
    adapters/
      __init__.py
      cli.py
      mcp_server.py
      web.py
  tests/
    unit/
    integration/
    e2e/
    fixtures/
```

### 5.1 为什么这样拆

这套目录结构刻意避免把所有东西放进 `agent.py`。Metis 的核心价值在于机制可组合，所以每个模块必须边界清晰。

拆分逻辑：

- `runtime` 管模型调用循环。
- `events` 管 hook 和事件。
- `providers` 管模型适配。
- `tools` 管工具注册与调用。
- `state` 管数据库状态。
- `planning` 管目标、计划和步骤。
- `context` 管上下文。
- `memory` 管长期记忆。
- `artifacts` 管产物。
- `evidence` 管证据。
- `quality` 管验收。
- `recovery` 管错误恢复。
- `security` 管安全。
- `loops` 管自动循环。
- `swarm` 管多智能体。
- `skills` 管可复用流程。
- `plugins` 管扩展机制。
- `telemetry` 管轨迹与指标。
- `adapters` 管入口。

---

## 6. 版本路线图

### 6.1 v0.1：最小可用 Kernel

目标：能完成一个单 agent 多轮工具调用任务。

必须实现：

- Config
- HookBus
- ToolSpec
- ToolRegistry
- ToolDispatcher
- OpenAI-compatible Provider
- Native OpenAI tool-call parser
- Hermes XML tool-call parser
- AgentLoop
- NormalizedResponse
- Tool result JSON normalize
- 基础文件工具
- 基础 shell 工具
- CLI adapter

不做：

- Swarm
- SkillFactory
- Web UI
- MCP server
- 复杂 memory
- 复杂 quality gates

验收任务：

- 注册 `read_file`、`write_file`、`run_shell` 三个工具。
- 模型能读取一个文件、写出一个报告、运行一次检查命令。
- 所有工具调用进入 trajectory。
- 工具失败返回结构化 JSON。

### 6.2 v0.2：状态化任务 Harness

目标：让复杂任务不再依赖模型脑内记忆。

必须实现：

- SQLite StateStore
- Session
- Goal
- Plan
- Step
- TaskContract
- PromptAssembler
- StepExecutor
- EvidenceLedger 最小版

验收任务：

- 用户输入复杂任务后自动创建 Goal。
- 生成至少多个 Step。
- 每个 Step 有 done condition。
- Step 完成需要 evidence ref。
- 最终输出包含 completion proof。

### 6.3 v0.3：上下文与工具结果预算

目标：让小模型不会被大上下文和大工具输出压垮。

必须实现：

- ContextEngine base
- SimpleContextCompressor
- ToolResultStore
- per-tool result budget
- per-turn aggregate budget
- persisted output pointer
- read persisted result slice

验收任务：

- 工具输出超过阈值时写入 `.metis/tool-results`。
- 模型上下文只看到 preview 和路径。
- 历史超过阈值时压缩。
- 摘要明确标注 reference only。

### 6.4 v0.4：Artifact 与 Quality Gate

目标：解决“说完成但没产物/没验证”的问题。

必须实现：

- ArtifactStore
- ArtifactManifest
- Validators
- QualityGateRunner
- 默认 gates：
  - artifact_exists
  - no_placeholder
  - requirements_covered
  - command_exit_zero
  - json_schema_valid
  - no_fake_completion

验收任务：

- 生成报告后 ArtifactStore 记录路径和 checksum。
- 如果最终回答引用不存在文件，quality gate 失败。
- 如果报告包含 TODO/placeholder，quality gate 失败。
- Gate 失败后进入 repair。

### 6.5 v0.5：Small Model Mode

目标：为 9B 模型提供专门执行模式。

必须实现：

- small model prompt profile
- stage-based tool exposure
- strict output schema
- parser repair
- one-step-at-a-time execution
- max tool schema count
- tool-call loop guardrail
- no-progress detector

验收任务：

- 使用本地或 OpenAI-compatible 9B 模型跑一个真实任务。
- 每轮工具数量不超过配置上限。
- 工具调用错误可修复或停止。
- 最终产物真实存在且通过质量门。

### 6.6 v0.6：Swarm 与审核

目标：支持复杂任务拆分、多角色并发和审核团队。

必须实现：

- SwarmAnalyzer
- TaskDecomposer
- RoleTemplate
- FilteredToolRegistry
- SwarmBus
- Stage execution
- ResultSynthesizer
- Auditor

验收任务：

- 一个任务分为 Explorer、Implementer、Verifier、Auditor。
- Explorer 无写权限。
- Implementer 有写权限。
- Verifier 执行测试。
- Auditor 检查 evidence 和 artifact。
- Synthesizer 只综合通过验证的结果。

### 6.7 v0.7：Skill 与 Plugin

目标：让成功工作流可复用，让业务能力可插拔。

必须实现：

- SkillManager
- SkillLoader
- SkillIndex
- Plugin API
- PluginManager
- 工具插件注册
- prompt fragment 注册
- quality gate 注册

验收任务：

- 新增一个外部插件注册工具。
- 新增一个 skill 被任务匹配并加载。
- skill 不污染 core。

### 6.8 v1.0：稳定底座

目标：Metis 可以作为 Aurora/Sophia 新架构底座试点。

必须实现：

- CLI 稳定。
- MCP server 可选。
- 完整测试。
- 文档完整。
- Aurora adapter 初版。
- Sophia adapter 初版。
- 9B 模型评测报告。

验收任务：

- 用 Metis 跑通至少 3 类真实任务：
  - 代码/文件任务。
  - 报告生成任务。
  - 多工具调研任务。
- 所有任务有 artifact、evidence、quality gate、trajectory。

---

## 7. 核心模块详细设计

## 7.1 Config

### 职责

统一管理 Metis 的运行配置。

### 配置范围

- workspace
- model provider
- model name
- base_url
- api_key
- max_turns
- context mode
- small model mode
- tool budget
- quality gate policy
- security policy
- state db path
- artifact path
- log level

### 推荐结构

```python
@dataclass
class ModelConfig:
    provider: str
    model: str
    base_url: str = ""
    api_key: str = ""
    max_turns: int = 20
    temperature: float = 0.2
    max_tokens: int | None = None
    tool_call_format: str = "auto"

@dataclass
class HarnessConfig:
    workspace: str
    state_db: str
    context_mode: str = "small"
    small_model_mode: bool = True
    max_tools_per_turn: int = 12

@dataclass
class BudgetConfig:
    per_tool_chars: int = 8000
    per_turn_chars: int = 30000
    preview_chars: int = 2000

@dataclass
class MetisConfig:
    model: ModelConfig
    harness: HarnessConfig
    budget: BudgetConfig
```

### 小模型默认值

```yaml
small_model_mode: true
max_turns: 16
temperature: 0.2
max_tools_per_turn: 8
per_tool_chars: 6000
per_turn_chars: 24000
preview_chars: 1500
context_mode: small
```

---

## 7.2 HookBus

### 职责

作为 Metis 的事件神经系统。

### 必须支持

- register
- emit
- remove
- list
- priority
- blocked
- exception isolation

### 关键事件

```text
agent.session_start
agent.pre_run
agent.post_run
agent.error
agent.session_end

model.pre_call
model.post_call
model.error

tool.pre_dispatch
tool.post_dispatch
tool.error
tool.result_persisted
tool.guardrail_warn
tool.guardrail_block

goal.created
goal.updated
goal.completed
goal.blocked

plan.created
step.started
step.completed
step.failed
step.verified

context.compressed
memory.store
memory.recall
artifact.created
quality.failed
quality.passed
recovery.retry
trajectory.record
```

### 构建优先级

HookBus 是 v0.1 必须实现的模块，因为后续所有机制都依赖它解耦。

---

## 7.3 ToolSpec / ToolRegistry / ToolDispatcher

### 职责

把工具从普通函数升级为受控能力。

### ToolSpec 字段

```python
@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict
    handler: Callable[[dict, ToolContext], Any]
    category: str = "general"
    side_effect: str = "read"  # read | write | network | destructive
    max_result_chars: int | None = None
    allowed_roles: list[str] | None = None
    requires_permission: bool = False
    retry_policy: str = "default"
    verification: str | None = None
```

### ToolContext 字段

```python
@dataclass
class ToolContext:
    session_id: str
    goal_id: str | None
    step_id: str | None
    workspace: str
    state: StateStore
    artifacts: ArtifactStore
    evidence: EvidenceLedger
    hooks: HookBus
```

### Dispatch 流程

```text
1. 找到 ToolSpec。
2. 校验参数 schema。
3. 检查工具权限。
4. 执行 tool.pre_dispatch hooks。
5. 检查 guardrail。
6. 调用 handler。
7. 标准化 result。
8. 超预算则持久化。
9. 记录 tool_call。
10. 触发 tool.post_dispatch。
11. 返回 compact result。
```

### 小模型策略

ToolRegistry 不应直接把所有工具 schema 给模型。必须有 ToolRouter：

```python
schemas = tool_router.select(
    task_type=current_task.type,
    step=current_step,
    model_profile="small",
    max_tools=8,
)
```

---

## 7.4 ProviderTransport

### 职责

隔离不同模型 API 的差异。

### 接口

```python
class ProviderTransport(ABC):
    api_mode: str

    def convert_messages(self, messages: list[dict]) -> Any:
        ...

    def convert_tools(self, tools: list[dict]) -> Any:
        ...

    def build_kwargs(self, model: str, messages: list[dict], tools: list[dict] | None, **params) -> dict:
        ...

    async def call(self, kwargs: dict) -> Any:
        ...

    def normalize_response(self, raw: Any) -> NormalizedResponse:
        ...
```

### NormalizedResponse

```python
@dataclass
class NormalizedResponse:
    content: str
    reasoning: str | None
    tool_calls: list[ToolCall]
    finish_reason: str
    usage: dict
    raw: Any
```

### 第一版支持

v0.1：

- OpenAI-compatible chat completions。
- native tool_calls。
- Hermes XML parser。

v0.5：

- Qwen XML parser。
- JSON block parser。
- repair parser。

v1.0：

- Anthropic。
- Local Ollama/LM Studio adapter。
- OpenRouter routing。

---

## 7.5 Tool Call Parser

### 为什么重要

9B 模型不一定稳定支持标准 tool calling。它可能输出：

```text
<tool_call>{"name":"read_file","arguments":{"path":"README.md"}}</tool_call>
```

也可能输出：

```json
{"tool":"read_file","args":{"path":"README.md"}}
```

也可能输出错误 JSON。

### Parser 链

```text
1. NativeOpenAIParser
2. HermesXMLParser
3. QwenXMLParser
4. JsonBlockParser
5. RepairParser
6. NoToolFallback
```

### Parser 输出

```python
@dataclass
class ParsedToolCall:
    id: str
    name: str
    arguments: dict
    raw: str
    confidence: float
```

### Repair 策略

解析失败时：

1. 记录 parser error。
2. 给模型一次短反馈。
3. 要求只返回一个合法 tool call。
4. 最多 repair 2 次。
5. 仍失败则转为 final/block。

---

## 7.6 AgentLoop

### 职责

执行一个受控模型工具循环。

### 输入

```python
AgentRunRequest:
  session_id
  user_message
  goal_id
  step_id
  model_config
  allowed_tools
  max_turns
```

### 输出

```python
AgentRunResult:
  status: final | need_more_steps | blocked | failed
  final_text
  tool_calls
  artifacts
  evidence
  usage
  errors
```

### 循环逻辑

```text
for turn in max_turns:
  assemble prompt
  call model
  normalize response
  if tool calls:
    validate and dispatch
    append compact tool results
    continue
  else:
    run final parser
    return result

if max_turns reached:
  mark failed or blocked
```

### 重要控制点

- 每轮前 context preflight。
- 每轮后 token usage update。
- 每轮 tool call guardrail reset。
- 每次工具结果可能外置。
- 任何最终声明必须进入 quality gate。

---

## 7.7 StateStore

### 职责

保存 session、message、goal、plan、step、tool_call、artifact、evidence、trajectory。

### 初始实现

SQLite。

### 为什么 SQLite

- 本地 agent 友好。
- 零服务依赖。
- 适合 Windows。
- Aurora/Sophia 已经大量使用 SQLite。
- 后续可扩展 Postgres。

### 必须支持

- create_session
- append_message
- create_goal
- update_goal
- create_plan
- update_step
- record_tool_call
- record_artifact
- record_evidence
- query_current_state
- export_handoff_packet

### HandoffPacket

```json
{
  "session_id": "...",
  "goal": "...",
  "current_step": "...",
  "completed_steps": [],
  "pending_steps": [],
  "decisions": [],
  "evidence": [],
  "artifacts": [],
  "failures": [],
  "next_action": "..."
}
```

---

## 7.8 Planning：Goal / Plan / Step

### Goal

Goal 表示用户真实目标。

字段：

- id
- objective
- status
- acceptance_criteria
- constraints
- created_at
- updated_at

### Plan

Plan 表示目标的执行方案。

字段：

- id
- goal_id
- version
- steps
- status

### Step

Step 是小模型每轮工作的最小单位。

字段：

- id
- title
- action
- required_inputs
- expected_output
- allowed_tools
- verification_method
- done_condition
- status
- evidence_refs
- artifact_refs
- errors

### Step 状态机

```text
pending -> running -> verifying -> done
pending -> running -> failed -> running
pending -> running -> blocked
```

### 完成规则

Step 不能由模型一句“完成了”直接完成。必须满足：

- done_condition 有证据。
- verification_method 已执行。
- 结果写入 StateStore。

---

## 7.9 TaskContract

### 职责

把用户任务变成模型必须遵守的执行合约。

### 合约内容

- 当前唯一目标。
- 当前唯一步骤。
- 不允许跳步。
- 不允许虚假完成。
- 允许工具。
- 禁止行为。
- 输出格式。
- 完成条件。

### 小模型合约模板

```text
You are executing one controlled step.

Goal:
{goal}

Current step:
{step}

Allowed tools:
{tools}

Done condition:
{done_condition}

Rules:
- Do not claim completion unless the done condition is verified.
- If a tool is needed, call exactly one tool.
- If no tool is needed, return the required JSON status.
- Do not invent files, outputs, data, citations, tests, or tool results.
```

---

## 7.10 PromptAssembler

### 职责

按层组合 prompt，而不是维护一个巨大 system prompt。

### 输入组件

- base identity
- runtime rules
- task contract
- current state
- allowed tools
- memory context
- workspace context
- evidence summary
- artifact summary
- skill instructions
- safety policy
- output schema

### 输出

OpenAI-style messages。

### 设计要点

1. system prompt 不要过长。
2. memory/context 必须 fenced。
3. old summary 必须 reference only。
4. 当前用户请求必须清晰标记。
5. 当前步骤必须靠近 prompt 末尾。
6. 小模型模式下减少抽象原则，增加具体命令。

---

## 7.11 ContextEngine

### 职责

控制模型看到的信息。

### 接口

```python
class ContextEngine:
    def update_from_response(self, usage: dict) -> None: ...
    def should_compress(self, messages: list[dict]) -> bool: ...
    def compress(self, messages: list[dict], focus: str | None = None) -> list[dict]: ...
    def build_context_packet(self, state: CurrentState) -> ContextPacket: ...
```

### ContextPacket

```python
@dataclass
class ContextPacket:
    memory: str
    workspace: str
    evidence_summary: str
    artifact_summary: str
    history_summary: str
    recent_messages: list[dict]
```

### 小模型模式策略

- keep_recent 少。
- summary 短。
- tool output 外置。
- 每轮只注入当前 step。
- 不注入完整历史。

---

## 7.12 MemoryManager

### 职责

长期稳定信息管理。

### 记忆分类

- user_preference
- environment_fact
- project_convention
- reusable_knowledge
- tool_quirk

### 不应进入长期 memory 的内容

- 当前任务进度。
- 临时 TODO。
- 具体测试结果。
- commit SHA。
- 临时路径。
- 一周后可能过期的信息。

这些应进入 StateStore 或 Trajectory。

### Memory Fence

所有 memory 注入 prompt 时必须加 fence：

```text
<memory-context>
System note: The following is recalled memory, not new user input.
...
</memory-context>
```

---

## 7.13 ToolResultStore

### 职责

保存大工具结果，避免上下文爆炸。

### 路径

```text
.metis/tool-results/{tool_call_id}.txt
```

### 返回给模型

```text
<persisted-output>
Tool result too large.
Full output saved to: .metis/tool-results/abc123.txt
Preview:
...
</persisted-output>
```

### 必须记录

- tool_call_id
- tool_name
- original_size
- preview_size
- path
- checksum

---

## 7.14 ArtifactStore

### 职责

记录用户可交付成果。

### Artifact 字段

```python
@dataclass
class Artifact:
    id: str
    session_id: str
    step_id: str | None
    type: str
    path: str
    checksum: str
    status: str
    created_at: str
    metadata: dict
```

### Artifact 类型

- markdown
- docx
- pdf
- pptx
- image
- csv
- json
- code
- log
- report
- archive

### 验证器

- exists
- non_empty
- checksum
- extension
- schema
- no_placeholder
- renderable
- testable

---

## 7.15 EvidenceLedger

### 职责

记录最终报告中重要 claim 的来源。

### Evidence 字段

```python
@dataclass
class Evidence:
    id: str
    claim: str
    source_type: str
    source_ref: str
    confidence: float
    created_at: str
```

### source_type

- user_input
- file
- tool_output
- command
- web
- artifact
- model_inference

### 规则

最终报告中的关键断言应能回溯到 evidence。小模型最终输出时，只允许引用 EvidenceLedger 中存在的证据或明确声明 limitation。

---

## 7.16 QualityGateRunner

### 职责

自动验收步骤和最终产物。

### GateSpec

```python
@dataclass
class GateSpec:
    id: str
    name: str
    scope: str
    check_type: str
    handler: Callable
    failure_policy: str  # repair | block | warn | halt
```

### 默认 Gates

1. `artifact_exists`
2. `artifact_non_empty`
3. `no_placeholder`
4. `requirements_covered`
5. `tool_truthfulness`
6. `command_exit_zero`
7. `json_schema_valid`
8. `path_safe`
9. `no_secret_leak`
10. `final_answers_latest_request`

### GateResult

```python
@dataclass
class GateResult:
    gate_id: str
    passed: bool
    severity: str
    message: str
    evidence_refs: list[str]
    repair_hint: str | None
```

### Repair 流程

```text
1. gate fails
2. if failure_policy=repair:
   2.1 build repair prompt
   2.2 run limited model/tool loop
   2.3 rerun gate
   2.4 max 2 attempts
3. if still fails:
   mark blocked or failed
```

---

## 7.17 ToolGuardrailController

### 职责

防止工具调用失控。

### 检测类型

- 同一工具同一参数失败重复。
- 同一工具连续失败。
- idempotent 工具无进展重复。
- mutating 工具危险重复。
- 每分钟工具调用过多。
- 单轮工具调用过多。

### 决策类型

- allow
- warn
- block
- halt

### 小模型默认阈值

```yaml
exact_failure_warn_after: 2
exact_failure_block_after: 4
same_tool_failure_warn_after: 3
same_tool_failure_halt_after: 6
idempotent_no_progress_warn_after: 2
idempotent_no_progress_block_after: 4
max_tool_calls_per_turn: 8
```

---

## 7.18 RecoveryManager

### 职责

错误分类、重试、退避、降级。

### ErrorCategory

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

### 策略

- network：jittered retry。
- rate_limit：backoff + credential/provider failover。
- auth：不重试，标记 blocked。
- context：触发 compression。
- parser：repair parser。
- tool：换参数或换工具。
- validation：repair artifact。
- security：halt。

---

## 7.19 Security

### 职责

保护文件系统、凭据、上下文和工具边界。

### 默认策略

1. 写操作限制在 workspace。
2. 禁止写敏感路径。
3. 禁止读取内部 cache/skill hub 文件。
4. context 文件注入前扫描 prompt injection。
5. 工具输出进入最终回答前脱敏。
6. 所有 mutating 工具需要 side_effect 标注。

### 敏感路径

- `.ssh`
- `.aws`
- `.gnupg`
- `.kube`
- `.docker`
- `.env`
- `.netrc`
- `.npmrc`
- `.pypirc`
- shell rc files
- system directories

---

## 7.20 Swarm

### v0.6 之后实现

Swarm 不进入最小核心，但接口要提前预留。

### 组件

- SwarmAnalyzer
- TaskDecomposer
- RoleTemplateBank
- FilteredToolRegistry
- SwarmBus
- StageExecutor
- ResultSynthesizer
- Auditor

### RoleTemplate

```python
@dataclass
class RoleTemplate:
    role_id: str
    name: str
    mission: str
    scope: str
    allowed_tools: list[str]
    forbidden_actions: list[str]
    output_schema: dict
    quality_gates: list[str]
```

### 默认角色

- planner
- explorer
- implementer
- verifier
- auditor
- synthesizer

### 审核团队原则

审核不能只看最终文本。必须看：

- trajectory
- tool calls
- artifacts
- evidence
- test results
- quality gate results

---

## 7.21 Skills

### 职责

保存可复用工作流。

### Skill 文件结构

```text
skills/
  skill-name/
    SKILL.md
    assets/
    scripts/
    templates/
```

### Skill Metadata

```yaml
name: ...
description: ...
triggers:
  - ...
allowed_tools:
  - ...
quality_gates:
  - ...
```

### 加载策略

小模型模式下：

- 先注入 skill index。
- 命中后加载完整 skill。
- 完整 skill 可裁剪。
- 每次只加载 1-3 个相关 skill。

---

## 8. 9B 小模型模式详细方案

## 8.1 目标

让 9B 模型在 Metis 上能够完成真实、多步骤、有产物、有验证的任务。

不是让 9B 模型变成大模型，而是把任务切到它能稳定完成的尺度。

## 8.2 执行约束

小模型模式默认：

- 一轮只执行一个步骤。
- 一次只允许一个工具调用。
- 每轮工具数量不超过 8。
- Prompt 不超过模型上下文的 40%-50%。
- 工具结果默认短 preview。
- 超过预算就外置。
- 最终回答前必须跑质量门。

## 8.3 Prompt Profile

小模型 prompt 必须短、硬、具体。

避免：

- 长篇价值观。
- 多层抽象原则。
- 同时要求十几件事。
- 大段历史。
- 大量工具。

推荐格式：

```text
SYSTEM:
You are Metis Executor. Follow the current step only.

CURRENT GOAL:
...

CURRENT STEP:
...

ALLOWED TOOLS:
...

DONE CONDITION:
...

OUTPUT RULE:
Return either exactly one tool call or a JSON status object.
Do not claim completion without evidence.
```

## 8.4 工具暴露策略

按阶段暴露工具：

### Explore

- list_files
- read_file
- search_files

### Plan

- goal_update
- plan_update
- step_update

### Execute

- write_file
- patch_file
- run_shell

### Verify

- run_shell
- artifact_check
- quality_check

### Finalize

- artifact_list
- evidence_list
- final_report

## 8.5 Parser Repair

小模型 tool call 格式错误时：

```text
The previous tool call was invalid JSON.
Return exactly one valid tool call:
<tool_call>{"name":"...","arguments":{...}}</tool_call>
```

最多两次。两次失败后：

- 如果能回答，则走 no-tool final。
- 如果不能回答，则 blocked。

## 8.6 小模型评测集

必须建立 Metis 自己的评测集。

### Eval 1：文件报告任务

输入：一个小型代码仓库。  
目标：分析架构并写报告。  
验收：

- 报告存在。
- 报告引用真实文件。
- 无 placeholder。
- 至少读取 5 个真实文件。
- final answer 路径真实。

### Eval 2：修复任务

输入：一个有语法错误的小项目。  
目标：修复并跑测试。  
验收：

- 测试从失败到通过。
- diff 只改必要文件。
- final answer 不虚报。

### Eval 3：调研任务

输入：明确主题。  
目标：联网检索并写来源报告。  
验收：

- 有真实 URL。
- 引用可追踪。
- 不编造来源。

### Eval 4：多步骤产物任务

输入：生成一个小工具或文档。  
目标：产物 + 验证。  
验收：

- artifact manifest 有记录。
- quality gates 通过。

---

## 9. 测试策略

## 9.1 单元测试

覆盖：

- HookBus priority / blocked。
- ToolRegistry register / dispatch / error。
- ToolCallParser。
- ToolResultStore。
- StateStore。
- ArtifactStore。
- EvidenceLedger。
- QualityGateRunner。
- Security path checks。
- ContextCompressor。

## 9.2 集成测试

覆盖：

- AgentLoop + fake provider + fake tools。
- Planner + StateStore。
- Tool result persistence + context assembly。
- Quality gate repair loop。
- Parser repair。

## 9.3 E2E 测试

覆盖：

- 真实 OpenAI-compatible endpoint。
- 本地小模型 endpoint。
- 文件产物任务。
- 测试修复任务。
- 报告生成任务。

## 9.4 回归测试

每次修改核心 harness 后运行：

```text
python -m pytest tests/unit
python -m pytest tests/integration
python -m pytest tests/e2e --run-local-model
```

## 9.5 质量指标

Metis 不能只看测试通过，还要看 agent 运行质量：

- task success rate
- artifact success rate
- false completion rate
- average turns
- average tool calls
- parser failure rate
- repair success rate
- quality gate failure rate
- context compression count
- tool result spill count
- cost/token usage

---

## 10. Aurora / Sophia 接入方案

## 10.1 接入原则

不要直接把 Aurora/Sophia 改造成 Metis。先做 adapter。

## 10.2 Aurora Adapter

Aurora 可先接入：

- business plan tools
- competition tools
- quality tools
- export tools
- visual tools

Adapter 负责：

- 把 Aurora tool register 转换为 Metis ToolSpec。
- 把 Aurora domain prompt 作为 prompt fragment。
- 把 Aurora quality auditor 作为 quality gate。

不迁移：

- AuroraAgent 主循环。
- Aurora Swarm。
- Aurora Memory。

先做旁路验证。

## 10.3 Sophia Adapter

Sophia 可先接入：

- research tools
- writing tools
- review tools
- citation tools
- journal tools
- ppt tools

Adapter 负责：

- 将研究工具注册为 Metis tools。
- 将 Sophia task_harness 迁移为 Metis TaskContract。
- 将 paper quality checks 迁移为 QualityGate。

不迁移：

- SophiaAgent 主体。
- 大量业务工具默认不全部暴露。

## 10.4 验证方式

同一个用户任务分别用：

1. 原 Aurora/Sophia。
2. Metis + Adapter。

比较：

- 成功率。
- 产物质量。
- 工具调用次数。
- 虚假完成率。
- 小模型可用性。

---

## 11. 开发顺序建议

严格按下面顺序，不建议跳。

### Step 1：初始化 Python 包

创建：

- `pyproject.toml`
- `metis/__init__.py`
- 基础 config。

### Step 2：HookBus

先做事件系统，后续全部挂 hook。

### Step 3：ToolSpec / ToolRegistry

先让工具能注册和执行。

### Step 4：FakeProvider

为了测试不要依赖真实模型，先做 fake provider。

### Step 5：OpenAICompatibleProvider

连接真实 OpenAI-compatible endpoint。

### Step 6：AgentLoop

实现多轮工具调用循环。

### Step 7：StateStore

保存 session、messages、tool_calls。

### Step 8：Goal/Plan/Step

把任务状态化。

### Step 9：PromptAssembler

把状态注入 prompt。

### Step 10：ToolResultStore

解决大输出。

### Step 11：ArtifactStore / EvidenceLedger

解决真实产物和证据。

### Step 12：QualityGateRunner

解决验收。

### Step 13：SmallModelMode

收紧 prompt、工具、parser、预算。

### Step 14：Swarm

最后做多智能体。

---

## 12. 第一版最小代码骨架

### 12.1 MetisAgent

```python
class MetisAgent:
    def __init__(self, config: MetisConfig):
        self.config = config
        self.hooks = HookBus()
        self.state = SQLiteStateStore(config.state_db)
        self.tools = ToolRegistry(hooks=self.hooks)
        self.provider = ProviderRouter(config.model)
        self.context = ContextEngine(...)
        self.artifacts = ArtifactStore(...)
        self.evidence = EvidenceLedger(...)
        self.quality = QualityGateRunner(...)
        self.loop = AgentLoop(...)

    async def run(self, user_message: str) -> AgentRunResult:
        ...
```

### 12.2 AgentLoop

```python
class AgentLoop:
    async def run(self, request: AgentRunRequest) -> AgentRunResult:
        messages = self.prompt_assembler.build(request)
        for turn in range(request.max_turns):
            response = await self.provider.call(messages, tools=request.tools)
            if response.tool_calls:
                tool_messages = await self.dispatch_tools(response.tool_calls)
                messages.extend(tool_messages)
                continue
            return self.finalize(response)
        return self.max_turns_reached()
```

### 12.3 ToolRegistry

```python
class ToolRegistry:
    def register(self, spec: ToolSpec) -> None:
        ...

    def schemas(self, filter: ToolFilter | None = None) -> list[dict]:
        ...

    def dispatch(self, name: str, args: dict, context: ToolContext) -> ToolResult:
        ...
```

---

## 13. 文档体系

Metis 需要随代码一起维护文档。

### 必备文档

1. `README.md`  
   项目定位、快速开始。

2. `docs/architecture.md`  
   总体架构。

3. `docs/build-plan.md`  
   构建路线。

4. `docs/module-spec.md`  
   模块接口。

5. `docs/small-model-mode.md`  
   9B 小模型模式。

6. `docs/security-model.md`  
   安全边界。

7. `docs/extension-guide.md`  
   如何注册业务工具/技能/质量门。

8. `docs/testing-strategy.md`  
   测试与验收。

---

## 14. 风险与规避

### 风险 1：一开始做太大

规避：v0.1 只做 kernel，不做 swarm。

### 风险 2：业务能力混入核心

规避：所有业务工具必须通过 adapter 注册。

### 风险 3：小模型无法稳定 tool call

规避：parser chain + repair + limited tools。

### 风险 4：工具输出撑爆上下文

规避：ToolResultStore 第一阶段就实现。

### 风险 5：质量门沦为形式

规避：优先 deterministic gate，不依赖模型自评。

### 风险 6：编码问题

规避：

- 全部源码 UTF-8。
- 文件读写显式 `encoding="utf-8"`。
- Windows 控制台显示不作为文件正确性的唯一依据。
- 测试读取中文文档并校验内容。

### 风险 7：状态数据库变复杂

规避：v0.1 只存 session/message/tool_call，v0.2 再加入 goal/plan/step。

### 风险 8：Swarm 带来不可控复杂度

规避：v0.6 后再做，且先做串行 stage，再做并行。

---

## 15. 里程碑验收标准

### v0.1 Done

- 能运行 CLI。
- 能连接 OpenAI-compatible provider。
- 能注册并调用工具。
- 能多轮 tool loop。
- 有测试。
- 有 trajectory。

### v0.2 Done

- 有 Goal/Plan/Step。
- 能按 step 执行。
- Step completion 需要验证。
- 状态可恢复。

### v0.3 Done

- 大工具输出外置。
- 上下文可压缩。
- 小模型上下文保持短。

### v0.4 Done

- ArtifactStore 可用。
- EvidenceLedger 可用。
- QualityGateRunner 可用。
- 最终回答不能引用不存在 artifact。

### v0.5 Done

- 9B 小模型跑通真实任务。
- 工具数量受控。
- Parser repair 生效。
- 虚假完成被拦截。

### v1.0 Done

- Aurora/Sophia adapter 初版可用。
- 至少 3 类真实任务跑通。
- 完整文档。
- 完整测试。
- 有小模型评测报告。

---

## 16. 推荐立即执行的下一步

如果下一步开始实际开发，建议只做 Phase 1，不要跳到完整系统。

立即任务：

1. 创建 Python package 骨架。
2. 写 `pyproject.toml`。
3. 实现 `HookBus`。
4. 实现 `ToolSpec` / `ToolRegistry`。
5. 实现 `FakeProvider`。
6. 实现 `AgentLoop` 最小版本。
7. 写 unit tests。
8. 写一个 CLI demo。

第一轮不要接 Aurora/Sophia，不要做 Swarm，不要做 Web UI。先证明 Metis 作为 harness kernel 能稳定运行。

---

## 17. 最终构建判断

Metis 的成功标准不是“有多少工具”，而是：

- 一个弱模型能不能在它上面完成强任务。
- 复杂任务能不能拆成可执行步骤。
- 每步能不能验证。
- 产物是不是真实存在。
- 失败能不能恢复。
- 最终报告有没有证据。
- 业务场景能不能不改核心地接入。

如果 Metis 做到了这些，它就不是一个普通 agent wrapper，而是一个真正可复用的 agent harness 底座。

