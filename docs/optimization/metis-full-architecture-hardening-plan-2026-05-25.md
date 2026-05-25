# Metis 全架构优化加固方案

日期：2026-05-25
对象：`D:\LATEXTEST\metis-agent-harness`
方案性质：面向整个 Metis Agent Harness 的架构审视、问题拆解、加固路线和验收标准，不是 `metis develop` 单模块方案。

## 1. 结论摘要

Metis 当前已经不是单一智能体项目，而是一个面向多场景智能体开发的 harness 底座。它已经具备运行时循环、模型 provider、工具调度、schema 校验、上下文压缩、状态存储、证据抽取、真实性检查、评测、release gate、repair plan、attestation、CLI/TUI/Web 入口和开发者定制入口。

但从“长期作为不同场景智能体基础设施”的标准看，Metis 仍需要继续加固。问题不在于缺一个入口，而在于多个横向底座能力还没有统一成强制性闭环：

1. 任务进入后没有统一强制经过 task contract。
2. prompt 体系已有 assembler 和 manifest prompt，但还没有完整的分层 Prompt Stack。
3. 工具权限已有 guardrails 和路径安全，但还没有生产级权限分级、沙箱等级和工具声明协议。
4. evidence 和 finalization 已有核心机制，但最终声明和证据之间还需要更细的 claim-to-evidence 映射。
5. eval 系统很强，但还需要成为所有 agent、所有发布、所有修复的统一质量门。
6. state 和 checkpoint 能力还需要从 session 存储扩展到长任务恢复、阶段恢复和任务级断点。
7. Web/TUI 已经可用，但还没有达到生产工作台级别。
8. develop 已经是开发者入口，但它只是整体架构的一环，不能成为架构加固的中心。
9. security 当前是基础可用，还不是生产级多用户安全模型。
10. packaging/release/install/version 体系还不完整。

下一阶段的正确方向是：以 task contract、prompt stack、tool permission、state checkpoint、evidence finalization、eval release gate、security boundary、package lifecycle 为主线，把 Metis 从“功能完整的 harness 原型”推进为“可验证、可恢复、可发布、可扩展、可治理的智能体基础设施”。

## 2. 当前真实状态

基于当前工作区复核，项目目录包含以下核心模块：

| 模块 | 当前职责 |
|---|---|
| `runtime` | AgentLoop、模型 profile、budget、execution controller、strict output、finalization。 |
| `providers` | Provider 抽象、FakeProvider、OpenAI-compatible provider、响应解析器。 |
| `tools` | 工具注册、schema、dispatcher、router、guardrails、结果持久化、schema feedback。 |
| `context` | 上下文构建和压缩。 |
| `state` | SQLite session/message/tool call/plan/loop 持久化。 |
| `evidence` | evidence schema、ledger、resolver、matcher、tool result extractor。 |
| `artifacts` | artifact store 和 artifact validators。 |
| `quality` | quality gates 和 gate runner。 |
| `evals` | eval runner、suite validation、real model suite、compare、diagnosis、repair plan、attestation。 |
| `telemetry` | HookBus 集成、timeline、trajectory。 |
| `events` | HookBus 和事件类型。 |
| `recovery` | 错误分类、retry policy、recovery manager。 |
| `loops` | scheduler 和 loop manager。 |
| `swarm` | 任务拆解、角色、bus、orchestrator、auditor、synthesizer。 |
| `skills` | skill index、loader、manager。 |
| `plugins` | plugin API 和 manager。 |
| `adapters` | CLI、Sophia/Aurora adapter、基础 adapter。 |
| `app` | manifest、runtime helper、TUI、FastAPI Web、静态资源。 |
| `develop` | 自然语言开发者定制入口。 |
| `security` | 路径安全、prompt injection scanner、redaction。 |
| `planning` | planning models、task contract。 |
| `prompts` | prompt assembler。 |

当前工作区文件统计：

- Python 源码文件：111。
- 测试文件：99。
- Markdown 文档：168。

最近一次已知全量测试结果来自上一轮真实执行：

- `python -m compileall -q metis` 通过。
- `python -m pytest -q`：`425 passed, 4 skipped`。

说明：本文是架构方案文档，不声称本轮重新运行了全量测试。上述测试结果来自前一轮完成 `metis develop` 改造时的命令输出。

## 3. 目标架构

Metis 的目标架构应分为十四层。

### 3.1 任务进入层

入口包括：

- `metis run`
- `metis tui`
- `metis web`
- `metis develop`
- 未来 API server
- 未来 package/install/export 命令
- 未来外部系统 adapter

目标：所有入口最终都进入统一的任务协议，而不是各自拼消息、各自建 loop、各自决定上下文。

应形成统一接口：

```text
Input Surface -> Task Intake -> Task Contract -> Runtime Session -> AgentLoop
```

### 3.2 Task Contract 层

自然语言任务必须被转成结构化任务契约：

- objective
- scope
- non-goals
- deliverables
- acceptance criteria
- allowed tools
- forbidden tools/actions
- evidence requirements
- artifact requirements
- expected verification commands
- risk flags
- user approval requirements
- completion definition

Task Contract 是 Metis 的核心控制面。没有 task contract，小模型容易误解任务、跳步骤、伪完成、超范围修改。

### 3.3 Prompt Stack 层

Prompt 不能只是字符串拼接。目标结构：

```text
Base Harness Prompt
Security Policy Prompt
Truthfulness/Evidence Prompt
Tool Policy Prompt
App System Prompt
App Developer Prompt
Task Contract Prompt
Workspace Context Prompt
Memory Context Prompt
Recent Conversation Prompt
Output Contract Prompt
```

每一层都要：

- 有来源。
- 有版本。
- 可审计。
- 可启用/禁用。
- 可计算 hash。
- 可进入 eval provenance。

### 3.4 Model Provider 层

Provider 不只是发请求。它应声明能力：

- 是否支持 native tool calling。
- 是否支持 JSON schema output。
- 是否支持 streaming。
- 最大上下文。
- 最大输出。
- 是否支持 thinking 参数。
- 速率限制策略。
- 错误类型。
- 成本和延迟估计。

小模型运行时需要根据 provider capability 自动选择：

- parser chain。
- schema repair 强度。
- prompt 冗余度。
- tool call 数量限制。
- finalization 检查强度。

### 3.5 工具执行层

工具层要从“能注册、能执行、能校验”升级到“权限治理、沙箱治理、结果治理、证据治理”。

目标工具元数据：

- name
- description
- input_schema
- output_schema
- permission_level
- side_effect_level
- network_required
- credential_required
- workspace_scope
- evidence_emits
- timeout_policy
- retry_policy
- redaction_policy
- audit_policy

权限等级建议：

| 等级 | 含义 |
|---|---|
| `read_only` | 只读文件、读取状态、检索信息。 |
| `workspace_write` | 只能写 workspace 内文件。 |
| `shell_safe` | 允许安全命令。 |
| `shell_dangerous` | 涉及删除、移动、发布、外部执行等高风险命令。 |
| `network` | 允许访问网络。 |
| `credential_access` | 需要读取或使用密钥。 |
| `external_publish` | 会向 GitHub、云服务、外部系统发布结果。 |

### 3.6 状态、记忆和 checkpoint 层

当前已有 SQLite 状态能力，但应进一步升级：

- session checkpoint
- task checkpoint
- phase checkpoint
- tool result checkpoint
- plan checkpoint
- approval checkpoint
- recovery checkpoint
- interrupted-run resume

目标：长任务中断后，Metis 可以明确知道：

- 已完成什么。
- 哪些任务有证据。
- 哪些任务失败。
- 哪些任务被跳过。
- 当前应该从哪里恢复。
- 是否需要重新审批。

### 3.7 Evidence 和真实性层

Metis 的重要优势是防止假完成。下一步应把 evidence 体系升级成更细粒度的声明验证系统。

目标结构：

```text
Final Answer Claim -> Claim Type -> Required Evidence Type -> Evidence Resolver -> Verdict
```

示例：

| 最终声明 | 必需证据 |
|---|---|
| “已生成文件” | artifact exists / write_file tool result |
| “已运行测试” | command evidence with exact command and exit code |
| “已上传 GitHub” | GitHub API result / remote URL evidence |
| “已调用 API” | provider/tool call evidence |
| “已修复 bug” | failing test before + passing test after 或明确复现证据 |
| “Web UI 可用” | server start evidence + HTTP/browser smoke evidence |

当前已有 evidence extractor、ledger、resolver、matcher 和 finalization guard，但还需要把 claim mapping 做得更系统。

### 3.8 Artifact 和交付层

Artifact 不只是文件，它应该有：

- artifact id
- path
- type
- producer
- task id
- input hash
- output hash
- validation status
- attestation status
- references
- portability status

下游 agent package 也应作为 artifact 管理。

### 3.9 Eval 和质量门层

Eval 应成为 Metis 的统一验收体系，而不是附属工具。

应覆盖：

- runtime eval
- tool schema eval
- parser repair eval
- evidence eval
- finalization eval
- app shell eval
- develop eval
- package eval
- security eval
- real small-model eval
- regression compare
- release gate

所有重要改动都应对应 eval。所有下游 agent 生成时也应自动生成自己的 eval suite。

### 3.10 Recovery 和修复闭环层

当前已有 compare、diagnose、repair tasks、repair plan、attestation、preflight。下一步要把它从 eval 工具链升级为通用修复闭环：

```text
Failure -> Diagnosis -> Repair Task -> Repair Plan -> Approved Execution -> Verification -> Release Gate
```

关键缺口：

- repair execution 仍偏 preflight，不是真正完整自动执行器。
- repair plan 与 code patch 的映射不够强。
- 修复后的回归测试和证据绑定还可以加强。

### 3.11 Swarm 和任务编排层

Swarm 现在有 decomposition、orchestrator、auditor、synthesizer。下一步要把它与 task contract 和 evidence 绑定：

- 每个子任务必须来自 task contract。
- 每个子任务必须有 owner role。
- 每个子任务必须有 verification。
- auditor 必须检查证据。
- synthesizer 不得合成未证实完成。

### 3.12 Security 层

当前安全模型是基础可用。生产级安全需要：

- workspace isolation
- path policy profiles
- command policy profiles
- credential vault
- auth
- RBAC
- session isolation
- prompt injection taint tracking
- external content trust labels
- audit log
- approval workflow for dangerous tools

### 3.13 App Surface 层

CLI/TUI/Web 应该共享：

- manifest
- prompt stack
- task contract builder
- provider config
- tool policy
- state backend
- evidence finalization
- session history

不能让 CLI、TUI、Web 形成三套分叉逻辑。

### 3.14 Packaging 和发布层

Metis 需要让下游 agent 可迁移、可安装、可验证、可升级：

- `metis package build`
- `metis package verify`
- `metis package install`
- `metis package export`
- package manifest version
- compatibility check
- eval suite included
- prompt hash included
- slash commands included
- app manifest included

## 4. 当前关键问题清单

### P0：Task Contract 没有成为所有入口强制核心

当前有 `planning/task_contract.py`，但整体运行链路仍允许直接从自然语言 message 进入 AgentLoop。这样会导致：

- CLI、TUI、Web、develop 的任务理解不一致。
- finalization 不一定知道完整验收标准。
- evidence 只验证声明，不一定验证全部用户需求。
- eval 与真实运行之间存在协议差异。

应修复为：所有入口先生成或加载 task contract，再进入 runtime。

### P0：Prompt Stack 不够系统

当前有 `PromptAssembler`，也有 app manifest prompt path，但还不是强类型 Prompt Stack。风险：

- system/developer/app/task/evidence/tool/context 顺序不稳定。
- 不能为每层 prompt 单独记录 hash。
- eval provenance 难以复现某次运行的完整 prompt 结构。
- 下游 agent prompt 变更难以被 gate 检测。

### P0：工具权限模型不够细

现有工具 guardrails 和 path security 是重要基础，但还缺统一权限声明。风险：

- 下游 agent 无法明确声明自己需要哪些工具权限。
- Web/TUI 场景下危险工具缺少明确审批边界。
- 外部发布、网络访问、凭据访问缺少统一治理。

### P0：Evidence finalization 需要更强 claim mapping

当前 finalization guard 已能防止部分假完成，但下一步应覆盖所有高风险声明：

- tested
- fixed
- generated
- uploaded
- deployed
- verified
- searched
- called API
- reviewed
- merged
- released

每类声明都应有对应 evidence resolver。

### P1：State/checkpoint/resume 不够完整

长任务需要恢复能力。当前 session state 和 loop scheduler 是基础，但还缺：

- task-level checkpoint
- phase-level checkpoint
- approve checkpoint
- recovery state
- resumable CLI command

### P1：Eval release gate 没有覆盖所有架构层

eval 模块很强，但要成为统一发布门，需要覆盖：

- prompt stack hash
- task contract hash
- tool permission manifest
- app surface smoke
- package portability
- security policy
- downstream agent generated eval

### P1：Repair execution 闭环还不完整

repair plan 已经很细，但自动执行、执行证据、失败恢复、补丁审计仍需加强。

### P1：Web/TUI 还不是生产级工作台

Web/TUI 目前是可用 shell，但不是成熟开发/运行管理界面。缺：

- session persistence
- auth
- task/evidence panel
- eval result panel
- approval UI
- package management UI

### P2：Provider capability registry 缺失

不同模型能力差异很大。Metis 需要知道 provider 能力，而不是只知道 model name/base_url。

### P2：Plugin/skill 生态协议需要收紧

当前有 plugins/skills，但需要更清晰的声明协议：

- 插件能注册什么工具。
- 需要什么权限。
- 提供什么 eval。
- 是否修改 prompt stack。
- 是否需要凭据。
- 如何卸载。

### P2：文档需要从“过程文档”升级为“架构基线文档”

当前 iteration 文档非常多，但顶层 `architecture.md`、`module-spec.md`、`security-model.md` 偏薄。需要建立：

- Architecture Decision Records。
- Runtime Protocol Spec。
- Task Contract Spec。
- Tool Permission Spec。
- Evidence Contract Spec。
- Package Spec。

## 5. 加固原则

1. 入口可以多个，协议必须一个。
2. 模型可以弱，harness 控制面必须强。
3. 所有完成声明必须可验证。
4. 所有工具调用必须有权限、schema、审计和失败反馈。
5. 所有长任务必须可 checkpoint 和 resume。
6. 所有下游 agent 必须可 package、可 eval、可迁移。
7. 所有重要 prompt/config/eval 变更必须进入 provenance。
8. 安全策略必须默认保守，高风险操作需要显式审批。
9. develop 是开发入口，不是架构中心。
10. 架构加固应优先补横向底座能力，再补场景功能。

## 6. 分阶段实施方案

### 阶段一：统一 Task Contract 和 Prompt Stack

目标：让所有入口进入同一个任务协议和 prompt 组装链路。

任务：

1. 设计 `TaskContractV1`。
2. 让 `metis run` 从用户输入生成 task contract。
3. 让 TUI/Web 每轮消息生成或继承 task contract。
4. 让 `metis develop` 的 development package 也写 task contract。
5. 设计 `PromptStack` 数据结构。
6. 改造 `PromptAssembler` 使用 PromptStack。
7. 每层 prompt 记录 source、type、hash、enabled。
8. AgentLoop trace 记录 prompt stack hash。
9. eval provenance 记录 task contract hash 和 prompt stack hash。

验收：

- CLI/TUI/Web/develop 都能产生或加载 task contract。
- 测试证明 prompt 层顺序稳定。
- 测试证明 manifest prompt、task contract、tool policy、strict output 都进入 PromptStack。
- eval report 中出现 task contract hash 和 prompt stack hash。

### 阶段二：工具权限和安全边界

目标：把工具系统从 schema 安全升级到权限安全。

任务：

1. 扩展 `ToolSpec`，增加 permission metadata。
2. 定义工具权限等级。
3. manifest 增加 allowed permissions。
4. dispatcher 执行前检查 tool permission。
5. 高风险工具需要 approval token。
6. `run_shell` 增加命令风险分类。
7. network tool 增加域名 allowlist。
8. credential 使用必须走 redaction/audit。
9. eval 增加 tool permission violation cases。

验收：

- 未授权工具调用被阻断。
- 高风险 shell 命令在无 approval 时被阻断。
- workspace 外路径写入被阻断。
- permission metadata 出现在 `metis eval list-tools`。

### 阶段三：Evidence Claim Mapping

目标：把“防假完成”从规则变成结构化声明验证系统。

任务：

1. 定义 `ClaimType`。
2. 定义 `EvidenceRequirement`。
3. 让 finalization guard 解析最终回答中的完成声明。
4. 不同 claim type 映射不同 evidence resolver。
5. 支持“证据不足时必须改为未完成/需继续”。
6. eval 增加 fake completion regression cases。
7. final report 输出 claim verification table。

验收：

- “已测试”但没有测试命令证据时 blocked。
- “已上传”但没有 GitHub/API 证据时 blocked。
- “已生成文件”但文件不存在时 blocked。
- 有证据时 final 可以通过。

### 阶段四：Checkpoint、Resume 和长任务恢复

目标：让长任务具备可靠恢复能力。

任务：

1. 定义 `RunCheckpoint`。
2. 每个阶段写 checkpoint。
3. 每个 tool result 绑定 checkpoint。
4. 每个 task 状态持久化。
5. 增加 `metis run resume`。
6. 增加 `metis develop resume`。
7. 中断后恢复时读取 last stable checkpoint。
8. resume 后不重复执行已证明完成的任务。

验收：

- 模拟中断后能恢复。
- 已完成任务不会重复执行。
- 缺证据任务会重新验证。
- resume report 明确列出恢复点。

### 阶段五：Eval Release Gate 全面化

目标：让 eval 成为所有架构层的发布门。

任务：

1. 定义 release profile：dev/candidate/release。
2. package 必须带 eval suite。
3. task contract/prompt stack/tool permission/package manifest 都进入 eval provenance。
4. gate 检查 prompt hash drift。
5. gate 检查 permission drift。
6. gate 检查 package portability。
7. gate 检查 app surface smoke。
8. gate 检查 evidence claim mapping。

验收：

- `metis eval gate --profile release` 可以拒绝缺失 provenance 的 run。
- 下游 agent package 缺 eval suite 时 verify 失败。
- prompt stack hash 变化时 compare 能识别。

### 阶段六：Repair Execution 闭环

目标：从 repair plan 走到真实修复执行和验证。

任务：

1. repair plan phase 绑定 executable tasks。
2. 增加 repair executor。
3. executor 只执行 verified repair plan。
4. 每个 repair task 写执行证据。
5. 失败时写 failure diagnosis。
6. 修复后自动跑 targeted eval。
7. targeted eval 通过后再跑 release gate。

验收：

- 无 attestation 的 repair plan 不能执行。
- 执行失败有结构化原因。
- 执行成功必须绑定测试证据。

### 阶段七：App Shell 和 Developer UX 生产化

目标：让 CLI/TUI/Web/develop 共享底座能力。

任务：

1. CLI/TUI/Web 共用 TaskContract builder。
2. Web session 持久化。
3. Web 显示 task contract/evidence/tool calls。
4. TUI 显示当前阶段、工具调用、证据状态。
5. develop 增加 scan/apply/verify/resume，但保持其为开发入口，不抢占 runtime 架构中心。
6. 增加 API server 模式。

验收：

- 三个运行入口行为一致。
- 同一 manifest 在 CLI/TUI/Web 中 prompt stack hash 一致。
- Web 不泄露 API key。

### 阶段八：Packaging、安装和发布

目标：让下游 agent 可迁移、可验证、可发布。

任务：

1. 定义 package manifest。
2. `metis package build`。
3. `metis package verify`。
4. `metis package install`。
5. `metis package export`。
6. package 包含 prompts、manifest、slash commands、eval suite、README、verification report。
7. package verify 跑 portability、manifest、prompt hash、eval suite schema。

验收：

- 生成的 agent package 可以复制到另一台机器。
- 另一台机器能 verify。
- verify 失败时原因明确。

## 7. 推荐优先级

### 必须优先做的 P0

1. Task Contract 强制入口。
2. Prompt Stack 强类型化。
3. Tool Permission Model。
4. Evidence Claim Mapping。

原因：这四项是 harness 底座质量的核心。如果不做，后续 develop、Web、package、eval 都会继续在弱协议上扩展。

### 第二优先级 P1

1. Checkpoint/Resume。
2. Release Gate 全面化。
3. Repair Execution。
4. App Shell 统一行为。

原因：这四项决定 Metis 能否处理长任务、回归、修复和多入口一致性。

### 第三优先级 P2

1. Provider Capability Registry。
2. Plugin/Skill Manifest。
3. Package Lifecycle。
4. Web/TUI 产品化。
5. 顶层架构文档重写。

原因：这些会显著提升可用性和生态能力，但要建立在 P0/P1 的底座之上。

## 8. 建议下一轮实施范围

下一轮不建议继续只做 develop。建议做一个“架构底座第一阶段加固包”，范围如下：

1. 新增 `TaskContractV1`。
2. CLI/TUI/Web/develop 统一进入 task contract。
3. 新增 `PromptStack`。
4. AgentLoop 使用 PromptStack。
5. trace/eval provenance 写入 task contract hash 和 prompt stack hash。
6. 补单元测试和集成测试。
7. 更新 `architecture.md`、`module-spec.md`、`testing-strategy.md`。

这一阶段完成后，Metis 的所有入口都会先进入统一协议，后续再加工具权限、claim mapping、resume、package 都会更稳。

## 9. 验收标准

整体架构加固不能只看“测试通过”，必须按能力验收。

### 架构验收

- 所有入口路径收敛到统一 task contract。
- 所有 prompt 输入通过 PromptStack。
- 运行 trace 能还原任务契约和 prompt 结构。
- 工具调用受 schema 和 permission 双重约束。
- 最终回答受 evidence claim mapping 约束。

### 测试验收

- 单元测试覆盖新增数据结构和边界条件。
- 集成测试覆盖 CLI/TUI/Web 入口一致性。
- eval 覆盖小模型常见错误。
- release gate 能拒绝缺 provenance、缺 evidence、缺 schema 的结果。

### 使用验收

- 开发者能用同一个 manifest 在 CLI/TUI/Web 运行。
- 下游 agent 能生成、验证、打包。
- 长任务中断后能恢复。
- 失败后能诊断、生成 repair plan、执行修复、回归验证。

### 真实性验收

- 没有证据不能声明完成。
- 没有测试不能声明测试通过。
- 没有上传证据不能声明上传完成。
- 没有文件证据不能声明生成完成。
- 所有最终报告必须列出证据、未完成项和残余风险。

## 10. 最终目标状态

完成上述加固后，Metis 应达到以下状态：

1. 它不是某个场景智能体，而是稳定的智能体 harness 底座。
2. 开发者可以基于 manifest/prompt/tool/eval/package 快速创建下游 agent。
3. 弱模型在 Metis 上运行时，能被 task contract、prompt stack、tool schema、permission、evidence、finalization、eval gate 共同约束。
4. 所有交付物都有证据链。
5. 所有发布都有 release gate。
6. 所有长任务都有 checkpoint。
7. 所有修复都有 diagnosis、repair plan、执行证据和回归验证。
8. 所有入口共享同一套 runtime contract。
9. 所有下游 agent 可打包、可迁移、可验证。
10. 整个系统的核心价值从“模型聪明”转为“harness 可靠”。

## 11. 当前方案对上一版偏差的修正

上一版建议过度聚焦 `metis develop`，这是不完整的。正确位置是：

- `metis develop` 是开发者入口。
- `metis run/tui/web` 是运行入口。
- `runtime/tools/evidence/evals/security/state` 才是架构底座。
- 架构加固应优先补横向能力，而不是继续围绕 develop 做局部增强。

因此，本方案把 `develop` 降回“入口层和开发者体验层”的位置，把第一优先级调整为：

1. Task Contract。
2. Prompt Stack。
3. Tool Permission。
4. Evidence Claim Mapping。

这是更符合 Metis 作为通用 agent harness 的长期方向。
