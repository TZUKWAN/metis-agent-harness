# Metis Agent Harness 基础设施级问题拆解与任务清单

日期：2026-05-25  
范围：`D:\LATEXTEST\metis-agent-harness`  
定位：面向不同场景智能体开发的通用 harness 底座，不绑定 Aurora、Sophia、计划书、代码修复、报告生成等任何单一业务场景。

## 1. 总判断

Metis 当前已经具备一个可运行的 harness 原型：有 AgentLoop、Provider、ToolRegistry、ToolDispatcher、StateStore、ArtifactStore、EvidenceLedger、QualityGate、ContextEngine、Recovery、Swarm、Skill、Plugin、Adapter、EvalRunner 等模块，且当前全量测试结果为 `112 passed, 2 skipped`。

但测试通过不等于已经达到“多场景智能体基础设施”的生产要求。现在最大的问题不是某个模块缺失，而是多个核心能力还没有形成严格闭环：

1. 模型声明完成，但 harness 不能总是证明完成。
2. 工具可以运行，但工具权限、风险、审批、证据提取还不够严格。
3. 有上下文压缩，但没有 evidence-first、task-state-first、role-aware 的上下文装配策略。
4. 有 swarm 骨架，但多智能体之间缺少强制审计、隔离、恢复、合成准入。
5. 有 eval runner，但真实 9B/free 模型任务集还不够系统，不能量化质量上限。
6. 有 adapter/plugin/skill，但还缺少声明式 agent 工程化体验，不能低成本创建新场景智能体。

所以 Metis 下一阶段的任务不是继续堆功能，而是把“可用模块”升级成“可信控制平面”。只有做到这一点，才可能让较弱的 9B 模型通过 harness 的结构化约束、工具闭环、证据验证、上下文管理和多角色审计产出高质量交付物。

## 2. 设计目标重新定义

Metis 的核心目标应拆成八句话：

1. 让任意新场景 agent 可以通过配置、模板和少量 adapter 快速创建。
2. 让小模型永远在明确任务合约、有限工具集、可验证交付条件内工作。
3. 让每一次工具调用都有权限、风险、输出预算、证据和轨迹记录。
4. 让每一个完成声明都能被 artifact、tool result、test result、git/API result 或人工审批记录支撑。
5. 让上下文不是简单消息截断，而是按任务、证据、约束、记忆、工具结果优先级重组。
6. 让多智能体不是并发聊天，而是带角色隔离、审计准入、失败恢复和证据合成的工作流。
7. 让真实模型质量可以被 benchmark、报告、指标和回归测试长期追踪。
8. 让 harness 本身可安装、可配置、可观测、可恢复、可扩展、可审计。

## 3. 当前状态摘要

### 3.1 已具备能力

- `AgentLoop` 能执行模型调用、工具调用、严格输出修复、最终校验。
- `OpenAICompatibleProvider` 能接 OpenAI-compatible API。
- `FakeProvider` 能支撑确定性测试。
- `ToolRegistry`、`ToolDispatcher`、`ToolSpec`、`ToolContext` 已有基础工具机制。
- `allowed_tools` 已开始在 dispatcher 层执行，不只是 prompt 约束。
- `RuntimeStatus` 已开始统一 final、blocked、needs_more_work 等状态语义。
- `StrictOutputParser` 已开始拒绝额外字段和错误类型。
- `EvidenceLedger`、`ClaimEvidenceMatcher`、`ToolEvidenceExtractor` 已形成初版证据链。
- `ArtifactStore`、`QualityGateRunner`、`FinalizationGuard` 已能拦截部分虚假完成。
- `ContextEngine`、`SimpleContextCompressor` 已能做基础预算压缩。
- `EvalRunner` 已有基础任务评估、JSON/Markdown 报告能力。
- `SwarmOrchestrator`、`SwarmBus`、`Auditor`、`ResultSynthesizer` 已有多智能体骨架。
- `Skill`、`Plugin`、`Adapter` 已有扩展点。
- 当前测试：`112 passed, 2 skipped`。

### 3.2 关键风险

- 测试覆盖的是模块可运行性，不等于真实 agent 任务质量。
- Claim 识别偏中文短语，英文或变体完成声明可能漏检。
- Evidence 匹配仍偏文本关键词，容易被弱证据或失败工具污染。
- Strict output 中的 `status=done`、`evidence_refs`、`artifact_refs` 没有完整进入 FinalizationGuard 的 typed 校验链。
- `run_shell` 仍使用 `shell=True`，缺少正式命令策略和危险命令治理。
- Hook/quality/telemetry 之间没有完整审计事件链。
- Context 缺少结构化 item、优先级、证据保留、工具结果摘要和记忆召回。
- Swarm 仍偏执行容器，没真正成为“计划、执行、验证、审计、合成”的可靠组织系统。
- README 仍停留在早期 Sprint 描述，与当前实际模块数量不匹配。
- 项目目录当前不是 git 仓库，无法直接通过 `git status` 追踪变更来源。

## 4. 问题域拆解

### 4.1 Harness 控制平面

现状：

- AgentLoop 是核心，但它还承担过多职责。
- 状态、工具、证据、质量、上下文、恢复、telemetry 没有统一 RunContext。
- ExecutionController 还没成为全局工作流状态机。

风险：

- 新场景接入后，业务 adapter 容易绕过核心控制平面。
- 多轮任务失败时，无法统一判断是模型失败、工具失败、证据不足、质量门失败还是上下文丢失。

任务：

1. 定义 `RunContext`：包含 run_id、session_id、goal_id、step_id、role_id、workspace、profile、budget、policy、stores、trace。
2. AgentLoop、ToolDispatcher、QualityGateRunner、EvidenceExtractor、ContextEngine 统一接收 `RunContext` 或可追踪子上下文。
3. 定义 `RunStateMachine`：created、planning、running、tool_waiting、verifying、blocked、needs_more_work、final、failed、cancelled。
4. 把 `ExecutionController` 升级为 Step/Run 编排层，不只是简单调用 AgentLoop。
5. 所有状态变化写入 StateStore 和 trajectory。

验收：

- 任意一次 run 能导出完整状态变化列表。
- blocked、needs_more_work、quality_failed、tool_failed、parser_failed 都能区分。
- 新 adapter 无法绕过核心状态记录。

### 4.2 完成声明与证据链

现状：

- 已有 `EvidenceLedger` 和 `ClaimEvidenceMatcher`。
- 但 claim 识别和 evidence 匹配仍偏弱。

风险：

- 模型说“report generated”“tests passed”“uploaded to GitHub”可能没有被中文 claim schema 检出。
- 任意 artifact 或任意 tool result 可能错误支持“已生成/已运行”。
- 失败的 pytest 输出如果被记录为 command evidence，可能污染完成判断。

任务：

1. 扩展 `CompletionClaim`：
   - generated / created / written / saved / exported
   - ran / executed / called / checked
   - tested / tests passed / verified
   - uploaded / pushed / published / synced
   - fixed / repaired / patched / resolved
   - reviewed / audited / validated
2. 将 claim 从 enum 字符串升级为 `ClaimPattern`：
   - claim_type
   - language
   - regex/patterns
   - required_evidence_types
   - required_strength
   - negative_patterns
3. 引入 `EvidenceResolver`：
   - artifact evidence 必须能回查 ArtifactStore。
   - tool evidence 必须能回查 ToolResultStore 或 StateStore tool_calls。
   - command evidence 必须包含 command、exit_code、stdout/stderr ref、status。
   - git evidence 必须包含 command/API、remote、commit 或 push result。
   - test evidence 必须包含 command、exit_code=0、summary。
4. 引入 `EvidenceClaimLink`：
   - claim_id
   - evidence_id
   - match_rule
   - confidence/strength
   - created_at
5. Matcher 不再只看文本，而是按 typed policy 匹配。
6. FinalizationGuard 接收 parsed strict output，当 `status=done/final` 时强制校验 refs。
7. 如果 final text 中有完成声明但没有强证据，必须返回 blocked 或 needs_more_work。

验收：

- “tests passed” 没有成功测试证据时必须 blocked。
- “uploaded to GitHub” 没有 git/API 成功证据时必须 blocked。
- 伪造 `source_ref=missing-id` 不能通过。
- 失败命令不能支持 tested/ran/fixed。
- 中英文完成声明均能被识别。

### 4.3 Artifact 交付物系统

现状：

- ArtifactStore 能注册文件。
- Validators 有存在、非空、placeholder 等基础检查。

风险：

- 不能表达 artifact 类型、版本、来源、生成步骤、diff、校验和。
- 报告、代码、图片、表格、文档、压缩包等交付物缺少 typed gate。

任务：

1. 定义 `ArtifactManifest`：
   - artifact_id
   - path
   - type
   - media_type
   - created_by_tool
   - source_step_id
   - checksum
   - size
   - version
   - parent_artifact_ids
   - quality_gate_results
2. 注册 artifact 时计算 checksum 和 size。
3. 支持 artifact versioning。
4. 支持 artifact diff：
   - text diff
   - json diff
   - code diff
   - binary metadata diff
5. 为常见交付类型提供 gate：
   - Markdown report gate
   - code change gate
   - test report gate
   - config file gate
   - data file gate
   - document bundle gate
6. 输出 delivery bundle：
   - artifacts
   - manifest
   - evidence links
   - quality report
   - run trace

验收：

- 任意 final artifact 可追踪到产生它的工具调用和 step。
- 空报告、placeholder 报告、无引用报告无法通过对应 gate。
- 代码修复 artifact 必须关联 diff 和测试证据。

### 4.4 工具治理与安全

现状：

- `allowed_tools` 已在 dispatcher 层检查。
- `ToolSpec` 有 side_effect、allowed_roles 等字段。
- `run_shell` 仍是 `shell=True`。

风险：

- prompt 层约束不可靠，必须由 dispatcher/policy 强制执行。
- shell 命令可以绕过路径安全。
- 高风险操作缺少审批、阻断、记录、重试和审计策略。

任务：

1. 定义 `ToolRiskLevel`：
   - safe_read
   - workspace_write
   - execute
   - network
   - credential
   - destructive
   - external_publish
2. 定义 `ToolPolicyEngine`：
   - allowed_tools
   - allowed_roles
   - allowed_paths
   - denied_paths
   - allowed_network_hosts
   - denied_commands
   - approval_required
   - max_runtime_seconds
   - max_output_chars
3. 将 `run_shell` 拆成：
   - `run_command`：默认不走 shell，参数列表执行。
   - `run_shell`：高风险，默认禁用或需审批。
   - `run_test`：专门运行测试并提取结构化结果。
4. 引入 `CommandClassifier`：
   - 识别 rm/del/format/registry/credential/exfiltration/network publish 等危险命令。
   - 区分 read-only、test、build、write、destructive。
5. Dispatcher pre-dispatch 必须返回 allow/deny/approval_required。
6. Tool result 必须记录：
   - policy_decision
   - risk_level
   - exit_code
   - duration
   - output_ref
   - evidence_refs
7. Hook 异常不应悄悄 fail-open：安全 hook 出错应按策略 fail-closed。

验收：

- 未允许工具不会执行。
- 非授权角色不会执行工具。
- 危险命令被阻断或进入 approval。
- shell 失败结果不会记为 ok。
- 所有工具副作用可审计。

### 4.5 Human-in-the-loop 与审批

现状：

- 没有正式 ApprovalRequest/ApprovalStore。

风险：

- 生产场景里发布、上传、删除、大范围修改、联网访问等动作不能安全托管。

任务：

1. 定义 `ApprovalRequest`：
   - approval_id
   - run_id
   - tool_name
   - arguments_summary
   - risk_level
   - reason
   - expires_at
   - status
2. 定义 `ApprovalDecision`：
   - approved/rejected/expired
   - approver
   - constraints
   - note
3. ToolDispatcher 遇到 approval_required 时返回 blocked/awaiting_approval。
4. CLI 提供 approval list/approve/reject。
5. API 层预留审批接口。
6. 审批结果写入 evidence 和 trajectory。

验收：

- 高风险工具未审批不执行。
- 审批通过后能恢复运行。
- 审批拒绝后 run 明确 blocked。

### 4.6 上下文工程

现状：

- ContextEngine 按字符预算压缩。
- SimpleContextCompressor 保留 system、summary、recent。

风险：

- 小模型最需要的是高价值上下文，而不是最近上下文。
- 关键证据、约束、done condition、工具结果摘要可能被压掉。

任务：

1. 定义 `ContextItem`：
   - type：system/task/constraint/plan/step/evidence/artifact/tool_result/memory/recent_message/error
   - priority
   - source
   - token_estimate
   - expires_after_step
   - role_scope
2. 定义 `ContextPackPlan`：
   - pinned items
   - high priority evidence
   - current step contract
   - recent messages
   - summaries
   - omitted refs
3. ContextEngine 从简单 message list 升级为 item packing。
4. Evidence-first packing：final 或 verification 阶段优先保留证据和 artifact refs。
5. Error-aware packing：连续失败时优先保留失败原因、修复尝试、约束。
6. Role-aware packing：swarm 中不同角色看到不同上下文。
7. Context compression 需要可测试：
   - hard budget
   - 不丢 system
   - 不丢 current task
   - 不丢 required evidence
   - 不丢 unresolved errors

验收：

- 任何压缩后 `final_chars <= max_chars`。
- 当前 step 和 done condition 永远保留。
- verification 阶段 evidence refs 优先保留。
- small profile 下不会把全部工具 schema 和长工具输出塞给模型。

### 4.7 记忆系统

现状：

- 有 StateStore，但没有长期 MemoryStore。

风险：

- 跨任务无法复用用户偏好、项目规则、经验教训、场景模板。
- 多场景 agent 每次都重新学习。

任务：

1. 定义 `MemoryRecord`：
   - memory_id
   - type：rule/fact/preference/pattern/lesson/project_context
   - scope：global/project/agent/session
   - confidence
   - source_evidence_id
   - created_at/updated_at
2. 定义 `MemoryStore`。
3. 定义 memory write gate：只有有证据或用户明确指令时写入。
4. 定义 memory retrieval：按 task、agent、project、role 检索。
5. 定义 memory decay/update：过期、冲突、替换。
6. ContextEngine 接入 memory items。

验收：

- 新 session 能召回 project rules。
- 未经证据支持的模型猜测不能写入长期记忆。
- 冲突记忆需要明确覆盖策略。

### 4.8 真实模型评测

现状：

- 有 EvalRunner。
- 真实模型 e2e 仍不够覆盖复杂任务。

风险：

- 无法证明 9B/free 模型在 Metis 上真的能产出高质量成果。
- 无法比较 prompt、profile、tool policy、context 策略的改动收益。

任务：

1. 建立 `tests/evals/real_model_tasks/`。
2. 至少定义 20 个 benchmark：
   - 读项目生成架构报告
   - 修复 failing test
   - 生成并校验 Markdown 文档
   - 运行测试并解释失败
   - 识别缺失证据并 blocked
   - 处理超长工具输出
   - 根据 artifact refs 最终回答
   - 多工具任务
   - 需要 parser repair 的任务
   - 需要拒绝危险工具的任务
   - 需要多角色审计的任务
   - 需要上下文压缩的任务
   - 需要 git 上传证据的模拟/真实任务
   - 需要 API 调用证据的任务
   - 需要中文长文档交付的任务
   - 需要英文 claim 检测的任务
   - 需要失败恢复的任务
   - 需要插件工具的任务
   - 需要 adapter 工具的任务
   - 需要人类审批的任务
3. 指标：
   - success_rate
   - false_completion_rate
   - evidence_coverage
   - artifact_quality
   - parser_failure_rate
   - tool_failure_rate
   - quality_gate_failure_rate
   - blocked_correctness
   - turns_used
   - latency
   - cost/token
4. 输出：
   - JSON
   - Markdown
   - trend history
   - failure taxonomy

验收：

- 没有 API key 时 skip，不伪造。
- 有 API key 时真实运行。
- 每次改核心模块后可以跑 benchmark 子集。
- 真实失败必须记录为失败，不用假数据补齐。

### 4.9 Swarm 生产化

现状：

- SwarmOrchestrator 能按 stage 调 runner。
- ResultSynthesizer 已开始过滤 audit failed。

风险：

- 多智能体可能只是多个弱模型输出堆叠。
- 没有严格角色隔离、共享证据、审计准入，反而扩大错误。

任务：

1. 定义 `SwarmRunContext`。
2. 每个 role 使用独立 AgentLoop：
   - planner
   - explorer
   - implementer
   - verifier
   - auditor
   - synthesizer
3. Role-specific tools：
   - explorer 只读/搜索
   - implementer 可写但需 policy
   - verifier 可运行测试
   - auditor 可读证据和质量结果
   - synthesizer 只合成已审计内容
4. SwarmBus 持久化。
5. 子任务结果必须包含：
   - status
   - claims
   - evidence_refs
   - artifact_refs
   - errors
   - confidence
6. Auditor 必须对每个子任务输出 verdict。
7. Synthesis 只能使用 audit passed 的结果。
8. 任一关键子任务 blocked 时，总任务不得 final。

验收：

- 没证据的子任务不能进入 final synthesis。
- 子 agent 无法调用超出 role 的工具。
- swarm run 可导出完整审计报告。

### 4.10 Skill、Plugin、Adapter 工程化

现状：

- 已有基础 Skill/Plugin/Adapter。
- 但缺少完整声明式开发体验。

风险：

- 新场景 agent 仍要写大量 glue code。
- 插件权限不清晰，可能污染核心。

任务：

1. 定义 `agent.yaml`：
   - name
   - description
   - model_profile
   - provider
   - tools
   - skills
   - plugins
   - adapters
   - quality_gates
   - eval_tasks
   - policies
2. 定义 `metis init <scenario>`：
   - 创建 agent.yaml
   - 创建 adapters/
   - 创建 skills/
   - 创建 evals/
   - 创建 tests/
   - 创建 README
3. Plugin manifest 升级：
   - permissions
   - version
   - compatible_metis
   - registered_tools
   - side_effects
   - risk_levels
4. Adapter contract tests：
   - register tools
   - tool schemas valid
   - policy metadata complete
   - no core mutation
5. 把 Aurora/Sophia 中真正通用的 harness 能力迁移到 core，把业务场景能力留在 adapter。

验收：

- 一个新场景可通过 `metis init` 生成骨架。
- 只改 agent.yaml 就能绑定不同工具/质量门/模型 profile。
- 插件危险权限会被 policy 引擎识别。

### 4.11 可观测性与审计

现状：

- 有 HookBus、TrajectoryRecorder。
- QualityGateRunner 和 telemetry 还没有完整事件闭环。

风险：

- 失败后定位成本高。
- 不能证明每一步为何通过或失败。

任务：

1. 定义 span model：
   - run span
   - model call span
   - tool call span
   - context build span
   - quality gate span
   - evidence match span
   - approval span
2. QualityGateRunner emit：
   - quality.started
   - quality.passed
   - quality.failed
3. EvidenceMatcher emit：
   - evidence.match_started
   - evidence.match_passed
   - evidence.match_failed
4. RunReport：
   - status
   - timeline
   - model usage
   - tool calls
   - artifacts
   - evidence
   - quality gates
   - failures
   - final decision
5. 支持 JSON/Markdown/HTML 三种报告。

验收：

- 任意 e2e run 生成可读报告。
- 质量门失败能看到输入摘要和失败原因。
- 最终 blocked 能追踪到哪个 claim 缺证据。

### 4.12 恢复、重试、调度

现状：

- RecoveryManager、Scheduler、LoopManager 有基础能力。
- 未完全接入 provider/tool/swarm。

风险：

- 网络错误、rate limit、临时工具失败无法系统恢复。
- 长期任务不可可靠运行。

任务：

1. Provider call 接入 RecoveryManager。
2. Tool dispatch 接入 retry policy。
3. 区分 retryable 和 non-retryable：
   - network timeout 可重试
   - auth failed 不重试
   - policy denied 不重试
   - parser failed 可 repair
4. Scheduler 增强：
   - durable queue
   - missed schedule handling
   - restart resume
   - circuit breaker
5. Swarm stage 失败恢复：
   - retry agent
   - fallback role
   - escalate to auditor
   - blocked with reasons

验收：

- 模拟 provider timeout 可以恢复。
- auth/policy 错误不会盲目重试。
- 调度任务进程重启后不丢。

### 4.13 配置、密钥和模型路由

现状：

- 当前主要靠环境变量和 dataclass profile。

风险：

- 多模型、多场景、多 adapter 配置不可维护。
- API key 容易误写入文档或源码。

任务：

1. 定义 `metis.yaml`。
2. 配置优先级：
   - CLI args
   - env vars
   - project metis.yaml
   - user config
   - defaults
3. Secrets 单独处理，不写入 run report 明文。
4. ModelRouter：
   - by task type
   - by risk
   - by context length
   - by failure fallback
   - by quality profile
5. 支持 no-cost-is-priority 模式：质量优先，不以省 token 为目标。

验收：

- 同一 agent.yaml 可切换 provider/model。
- run report 不泄露 API key。
- 小模型失败后可按策略升级模型或要求更多证据。

### 4.14 安装、发布与仓库工程

现状：

- 当前目录不是 git repo。
- pyproject 存在，但需要安装、wheel、CLI smoke 验证。

风险：

- 另一台电脑无法稳定复现。
- 变更历史不可追踪。

任务：

1. 初始化或确认 git 仓库归属。
2. 建立 `.gitignore`：
   - `.metis/`
   - `__pycache__/`
   - `.pytest_cache/`
   - secrets
   - local eval outputs
3. 验证 `pip install -e .`。
4. 验证 wheel build。
5. 验证安装后 CLI。
6. README 更新为当前真实状态。
7. 文档索引整理：
   - architecture
   - module spec
   - security model
   - testing strategy
   - extension guide
   - eval report
   - task breakdown

验收：

- 新机器 clone 后可安装、测试、运行 smoke。
- README 不再描述过期 Sprint。
- 没有 secret 被提交。

## 5. 优先级任务清单

### P0：必须先做，否则 harness 不可信

1. 完成 typed evidence policy：强证据、弱证据、source resolver、claim link。
2. FinalizationGuard 接入 parsed strict output 和 refs 校验。
3. 扩展多语言 claim 检测，覆盖中文、英文、常见同义表达。
4. run_shell 改造为安全命令体系，失败命令不得污染 evidence。
5. ToolPolicyEngine 落地，dispatcher 强制执行风险、角色、工具、路径策略。
6. ContextItem 和 evidence-first packing 落地。
7. Eval benchmark 扩展到真实小模型任务集。
8. RunReport 落地，支持每次 run 复盘。
9. QualityGateRunner 接入 HookBus 和 telemetry。
10. Swarm audit-enforced synthesis 落地。

### P1：通用场景开发能力

1. agent.yaml schema。
2. AgentDefinitionLoader 和 AgentFactory。
3. metis init scaffold。
4. Plugin manifest 权限和版本治理。
5. Adapter contract tests。
6. MemoryStore。
7. Approval system。
8. Provider/tool recovery 深度接入。
9. State migration。
10. ModelRouter。

### P2：生产化能力

1. Durable scheduler。
2. Optional service API。
3. Artifact delivery bundle。
4. HTML trace report。
5. wheel build/install smoke。
6. CI 配置。
7. 文档教程化。
8. 多模型评测趋势报告。
9. 插件 quarantine/safe mode。
10. 跨平台 Windows/Linux 测试。

## 6. 建议执行顺序

### Sprint A：防伪完成闭环

目标：模型不能虚假声明完成。

任务：

1. Claim schema 多语言化。
2. EvidenceResolver。
3. EvidenceClaimLink。
4. FinalizationGuard 接 strict parsed output。
5. 失败工具结果不支持完成 claim。
6. 补充测试：
   - 英文 completed claim 被识别。
   - 伪造 source_ref 被拒绝。
   - pytest 失败不能支持 tested。
   - GitHub upload 没有 push/API 证据被拒绝。

验收命令：

```powershell
python -m pytest -q tests/unit/test_claim_evidence_matcher.py tests/unit/test_finalization_guard.py tests/integration/test_agent_loop_finalization_guard.py
python -m pytest -q
```

### Sprint B：工具策略与命令安全

目标：所有工具副作用进入 policy 控制。

任务：

1. ToolRiskLevel。
2. ToolPolicyEngine。
3. run_command/run_test/run_shell 分层。
4. CommandClassifier。
5. approval_required 状态。
6. tool result policy metadata。

验收命令：

```powershell
python -m pytest -q tests/unit/test_tools.py tests/unit/test_tool_guardrails.py tests/unit/test_path_security.py tests/integration/test_agent_loop_allowed_tools_enforced.py
python -m pytest -q
```

### Sprint C：上下文与小模型稳定性

目标：9B/free 模型拿到的是高价值上下文，不是随机截断文本。

任务：

1. ContextItem。
2. ContextPackPlan。
3. evidence-first packing。
4. role-aware packing。
5. error-aware packing。
6. compression audit tests。

验收命令：

```powershell
python -m pytest -q tests/unit/test_context_compressor.py tests/integration/test_agent_loop_context.py
python -m pytest -q
```

### Sprint D：真实模型 benchmark

目标：用真实任务证明 Metis 对小模型有质量提升。

任务：

1. 20 个 EvalTaskSpec。
2. failure taxonomy。
3. trend report。
4. glm-4.7-flash endpoint 真实测试。
5. false completion 指标。

验收命令：

```powershell
python -m pytest -q tests/unit/test_eval_runner.py
python -m pytest -q tests/e2e/test_local_9b_eval.py
```

### Sprint E：Swarm 生产化

目标：多智能体成为可靠工作流，而不是并发输出。

任务：

1. Role-specific AgentLoop。
2. 持久化 SwarmBus。
3. Auditor 强制准入。
4. Synthesis evidence refs。
5. blocked propagation。

验收命令：

```powershell
python -m pytest -q tests/unit/test_result_synthesizer.py tests/integration/test_swarm_orchestrator.py tests/integration/test_swarm_auditor.py
python -m pytest -q
```

### Sprint F：场景开发工程化

目标：以后开发新 agent 不从零写代码。

任务：

1. agent.yaml。
2. AgentFactory。
3. metis init。
4. plugin permissions。
5. adapter contract tests。
6. tutorial docs。

验收：

- 用 scaffold 创建一个 `research-agent`。
- 不改 core，只通过 agent.yaml + skill + adapter 跑通 smoke。

## 7. 立即可执行的细任务

下面这些任务粒度较小，适合马上进入开发：

1. 删除 `metis/quality/gates.py` 中旧版 `_claim_has_evidence` 死代码，避免维护误判。
2. 给 `ClaimEvidenceMatcher` 增加英文 claim 单元测试。
3. 给 `StrictOutputParser` 增加 extra keys、错误 refs 类型、非字符串 summary 的测试。
4. 给 `AgentLoop` 增加 `status=done` 但 refs 缺失的 blocked 测试。
5. 给 `ContextEngine` 增加 hard budget 边界测试。
6. 给 `run_shell` 增加失败命令不产生成功 evidence 的测试。
7. 给 `ToolDispatcher` 增加 security hook fail-closed 测试。
8. 给 `ResultSynthesizer` 增加嵌套 failed result 不进入合成的测试。
9. README 更新当前模块状态和运行方式。
10. 创建 `docs/roadmap.md`，把本文任务按 sprint 映射为执行路线。

## 8. 完成定义

Metis 不能以“代码写完”作为完成。必须满足：

1. 全量测试通过。
2. 至少 20 个真实/半真实 agent benchmark 可运行。
3. 任意 final claim 都能追踪 evidence。
4. 任意 artifact 都能追踪生成步骤。
5. 任意工具副作用都能追踪 policy decision。
6. 任意 blocked 都有明确原因。
7. 任意质量门失败都能复盘。
8. 新场景 agent 可以通过 scaffold 创建。
9. 小模型失败可以通过 parser repair、context packing、tool restriction、quality gate、swarm audit 被纠正或阻断。
10. 没有真实证据时，Metis 宁可 blocked，也不能虚假完成。

