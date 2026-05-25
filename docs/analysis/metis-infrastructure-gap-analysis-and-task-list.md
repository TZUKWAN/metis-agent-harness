# Metis Agent Harness 基础设施问题分析与任务清单

日期：2026-05-25

## 1. 分析定位

Metis 的目标不是成为 Aurora 或 Sophia 的业务复制品，而是成为一个可复用、场景无关、可扩展的智能体基础设施。它未来应该允许刘总基于同一个 harness 快速开发不同场景智能体，例如商业计划书智能体、学术研究智能体、代码工程智能体、投研智能体、文档交付智能体、数据分析智能体、运营自动化智能体。

因此，本次分析不只看“代码能不能跑”，而是从基础设施视角检查：

1. 一个新场景能不能快速接入。
2. 小模型能不能稳定执行复杂任务。
3. 工具、状态、证据、质量门能不能形成闭环。
4. 插件、Adapter、Skill 能不能长期维护。
5. 是否具备生产可观测、可审计、可恢复能力。
6. 是否能防止模型虚假完成、越权执行、上下文污染。
7. 是否能真实评测 agent 质量，而不是只看单元测试。

## 2. 当前基线

当前本地验证：

- 全量测试：`101 passed, 2 skipped`
- 编译检查：通过
- 首轮任务清单：`DONE=73`，`TODO=0`
- 第三轮优化任务清单：`DONE=6`，`TODO=0`

已有能力：

- OpenAI-compatible Provider。
- FakeProvider。
- ToolSpec、ToolRegistry、ToolDispatcher。
- AgentLoop。
- SQLiteStateStore。
- Goal、Plan、Step、ExecutionController。
- BudgetConfig、ToolResultStore、ContextEngine。
- ArtifactStore、EvidenceLedger、QualityGate。
- FinalizationGuard。
- Recovery、Path Security、Prompt Injection Scanner、Redaction。
- LoopManager、Scheduler。
- Swarm 基础骨架。
- Skill、Plugin、Adapter 基础。
- Aurora/Sophia Adapter 初版。
- E2E fixtures 和真实 API smoke。

## 3. 外部框架参考结论

外部开源 agent infrastructure 的共同趋势：

1. **控制平面化**：生产 agent 不只是 loop，而是需要 tracing、policy、approval、state machine、event log、scheduler、deployment surface。
2. **声明式 Agent 定义**：agent.yaml / config spec / agent definition 逐渐成为多场景复用的核心。
3. **强评测系统**：可靠性主要靠 evaluation pipeline，而不是“框架看起来完整”。
4. **权限与治理**：工具权限、凭据、文件系统、网络、外部副作用必须被明确建模。
5. **多智能体不是重点，编排和审计才是重点**：多 agent 必须绑定角色、上下文隔离、证据合并、失败恢复、最终审核。
6. **记忆和上下文是质量核心**：小模型尤其依赖良好的上下文裁剪、记忆分层、证据优先级和任务状态压缩。
7. **人类介入不是最后审批按钮**：应在高风险工具、副作用、权限升级、失败循环、质量门不通过时介入。

## 4. 总体判断

Metis 现在处于“可运行的基础版 harness”阶段。它已经有核心模块，但还没有达到“可作为长期、多场景、生产级 agent 底座”的水平。

最大差距不是某一个工具没写，而是以下四类基础设施还不够强：

1. **场景开发体验不完整**：缺少声明式 agent/project 模板、scaffold、配置管理和多场景启动方式。
2. **真实小模型能力未被充分验证**：FakeProvider E2E 多，真实 9B/flash 复杂任务少。
3. **控制平面不够完整**：observability、policy、HITL、approval、deployment、job control 还薄。
4. **质量与证据体系不够苛刻**：已有防伪 gate，但还没有覆盖所有交付形态和复杂声明。

## 5. 问题拆解

### P0-01 真实小模型 E2E 不足

现状：

- 真实 API smoke 已通过。
- 但复杂任务主要依赖 FakeProvider。
- `test_local_9b_eval.py` 对真实模型任务集覆盖不足。

风险：

- 不能证明小模型能完成真实多步工具任务。
- 无法知道 parser failure、tool loop、质量门失败、上下文压缩失败的真实概率。

应补：

- 真实模型任务集。
- 自动评测报告。
- 成功率、失败类型、工具调用轨迹统计。

### P0-02 AgentLoop 状态机语义不完整

现状：

- AgentRunResult status 主要是 `final/max_turns/blocked`。
- Strict JSON 中的 `status` 字段没有完全驱动 runtime 状态。
- `needs_more_work`、`blocked`、`done` 没有形成明确状态转移。

风险：

- 模型说 blocked，但 harness 仍可能按 final 处理。
- StepExecutor 无法利用模型结构化状态做更细粒度决策。

应补：

- RuntimeStatus enum。
- StrictOutput -> AgentRunResult 映射。
- Step 状态机：pending/running/verifying/done/failed/blocked/needs_more_work。

### P0-03 FinalizationGuard 仍偏文本规则

现状：

- 已经拆分 `已生成/已运行/已测试/已上传/已修复`。
- 但证据判断仍以关键词和工具类型为主。

风险：

- 复杂场景下误判。
- 比如“已上传 GitHub”需要 remote URL、commit SHA、push command 或 GitHub API 证据，不应只靠文本。

应补：

- Claim type schema。
- Evidence type schema。
- ClaimEvidenceMatcher。
- 每类 claim 的强证据规则。

### P0-04 Evidence 类型体系不完整

现状：

- EvidenceLedger 是通用表。
- ToolEvidenceExtractor 只覆盖 run_shell/write_file。

风险：

- 搜索、API 调用、上传、下载、截图、渲染、文档生成、测试报告等无法形成强证据。

应补：

- EvidenceSourceType enum。
- EvidenceStrength：weak/medium/strong。
- EvidenceClaimLink。
- ArtifactEvidenceExtractor。
- WebEvidenceExtractor。
- GitEvidenceExtractor。
- TestEvidenceExtractor。

### P0-05 QualityGate 不够严格

现状：

- 有 artifact_exists、non_empty、no_placeholder、requirements_covered、no_fake_completion。
- 缺少针对具体交付物的质量门。

风险：

- Markdown 报告空洞但非空也可能通过。
- 代码修复没有 diff 检查、测试覆盖检查。
- 文档交付没有链接、标题、引用、格式完整性检查。

应补：

- MarkdownQualityGate。
- CodeChangeQualityGate。
- TestRunQualityGate。
- GitUploadQualityGate。
- Citation/EvidenceReferenceGate。
- ArtifactDiffGate。

### P0-06 Tool 权限与副作用治理不足

现状：

- ToolSpec 有 side_effect。
- run_shell 仍是 shell=True。
- 没有风险等级、审批策略、命令 denylist/allowlist。

风险：

- 高风险命令可能误执行。
- 新场景 adapter 注册危险工具后缺少统一治理。

应补：

- ToolRiskLevel。
- ToolPolicyEngine。
- CommandClassifier。
- ApprovalRequiredDecision。
- MutatingToolAudit。
- Workspace write allowlist。

### P0-07 Human-in-the-loop 缺失

现状：

- 没有 approval request/response 模型。
- 没有中断、暂停、恢复、用户确认接口。

风险：

- 生产场景中高风险操作无法安全接入。
- “只在最后审批”太晚，副作用可能已经发生。

应补：

- ApprovalRequest。
- ApprovalStore。
- AgentLoop approval interrupt。
- CLI approval prompt。
- ToolDispatcher pre-dispatch approval hook。

### P0-08 ContextEngine 过于简单

现状：

- 主要按字符预算压缩。
- 压缩策略是保留 system + summary + recent。

风险：

- 小模型可能丢关键证据、约束、工具结果。
- 多场景 agent 需要不同上下文策略。

应补：

- ContextItem model。
- ContextPriority scoring。
- Evidence-first packing。
- Memory retrieval。
- Workspace index。
- Compression quality test。

### P0-09 Memory 系统缺失

现状：

- 有 state，但没有长期 memory。
- 没有 facts/preferences/policies/lessons/task patterns 分层。

风险：

- 多场景 agent 无法复用经验。
- 不能学习常见任务流程、用户偏好、项目规范。

应补：

- MemoryStore。
- MemoryType：principle/rule/fact/pattern/log。
- Memory retrieval。
- Memory update gate。
- Cross-session memory summary。

### P0-10 真实评测体系不足

现状：

- pytest 覆盖模块行为。
- 缺少 agent task benchmark。

风险：

- 无法量化小模型质量。
- 无法比较 prompt、context、tool router、模型 profile 的变化收益。

应补：

- EvalTaskSpec。
- EvalRunner。
- EvalMetrics：success/tool_accuracy/evidence_coverage/false_completion/parser_failures/latency/cost。
- Golden task fixtures。
- 真实模型 eval report。

### P1-11 声明式 Agent 定义缺失

现状：

- 有 profile、skill、plugin、adapter。
- 没有统一 agent.yaml。

风险：

- 每个新场景都要写 Python glue。
- 难以复用、迁移、版本化。

应补：

- `agent.yaml` schema。
- AgentDefinitionLoader。
- AgentFactory。
- Tool/skill/quality/profile binding。

### P1-12 场景 Scaffold 缺失

现状：

- 没有 `metis init <scenario>`。

风险：

- 刘总以后开发新场景 agent，起步成本高。

应补：

- `metis init scenario-name`。
- 生成 adapters、skills、evals、docs、tests。
- 模板包括 research/code/docs/business/general。

### P1-13 Plugin 治理不足

现状：

- PluginManager 可加载本地插件。
- 没有权限声明、版本约束、禁用、回滚、签名。

风险：

- 插件可能注册危险工具。
- 插件异常和依赖污染难控。

应补：

- plugin manifest schema。
- permissions。
- version compatibility。
- safe mode。
- disable/quarantine。

### P1-14 Adapter 深度不足

现状：

- Aurora/Sophia adapter 是结构检查工具。

风险：

- 没有真正复用两个项目优秀通用能力。

应补：

- Adapter capability inventory。
- 通用工具包装：read/research/document/quality。
- Adapter contract tests。
- Adapter tool exposure policy。

### P1-15 Swarm 还只是骨架

现状：

- 有 roles、decomposer、bus、orchestrator。
- runner 是外部抽象，未真正绑定 AgentLoop。

风险：

- 多 agent 任务无法生产执行。

应补：

- SwarmAgentRunner。
- Role-specific AgentLoop。
- Shared evidence/artifact bus。
- Audit-enforced synthesis。
- Failure escalation。

### P1-16 Recovery 没有接入核心 provider/tool path

现状：

- RecoveryManager 有。
- AgentLoop/provider call 没有统一包裹 recovery。

风险：

- 网络失败、rate limit、provider 500 不会自动恢复。

应补：

- Provider call recovery。
- Tool call retry policy。
- Retry event telemetry。
- Non-retryable error fast fail。

### P1-17 Observability 仍不足

现状：

- TrajectoryRecorder 有。
- 没有标准 run report、span tree、指标导出。

风险：

- 失败后定位仍靠手查 logs。

应补：

- RunReport。
- Span model。
- Tool timeline。
- Token/cost/latency metrics。
- HTML/Markdown trace report。

### P1-18 Scheduler/Loop 还不是真正任务系统

现状：

- LoopManager 和 SchedulerStore 有基础能力。
- 没有 durable worker、重启恢复、错过补跑策略。

风险：

- 长期后台 agent 不可靠。

应补：

- durable loop runner。
- missed schedule handling。
- failure circuit breaker。
- persistent task queue。

### P1-19 StateStore 缺少正式迁移和并发策略

现状：

- SQLite 表创建和 ALTER 分散在代码中。

风险：

- 后续 schema 变化不可控。
- 多进程并发时容易出问题。

应补：

- schema_version table。
- Migration registry。
- backup before migration。
- concurrency tests。

### P1-20 CLI/API 不够完整

现状：

- CLI 只有基本 doctor/run。
- 没有统一 server/API。

风险：

- 新场景 agent 难以作为服务接入。

应补：

- `metis run`。
- `metis eval`。
- `metis init`。
- `metis inspect`。
- FastAPI server 可选。

### P1-21 配置系统不足

现状：

- 环境变量 + profile dataclass。
- 缺少配置文件和优先级规则。

风险：

- 多模型、多场景、多 adapter 配置困难。

应补：

- metis.yaml。
- env override。
- config validation。
- secrets separation。

### P2-22 文档仍不够教程化

现状：

- 有模块文档。
- 不足以指导一个新场景从零落地。

应补：

- 从零开发新场景 agent。
- 写 adapter。
- 写 plugin。
- 写 eval。
- 接真实模型。
- 部署和调试。

### P2-23 包发布和工程化不足

现状：

- pyproject 有。
- 未验证 wheel、安装后 CLI、跨目录运行。

应补：

- build wheel。
- install smoke。
- CLI entrypoint test。
- package data test。

### P2-24 多模型路由缺失

现状：

- 单 provider/model。

风险：

- 小模型失败时不能自动升级。

应补：

- ModelRouter。
- fallback policy。
- task-based model selection。
- cost/quality tradeoff metrics。

### P2-25 数据和文件交付物管理不足

现状：

- ArtifactStore 记录现有文件。
- 没有版本、diff、manifest、export bundle。

应补：

- ArtifactManifest。
- artifact versioning。
- diff and lineage。
- delivery bundle。

## 6. 总任务清单

### Phase A：真实小模型可用性验证

#### A1 建立真实模型任务集

状态：TODO  
优先级：P0  
目标：验证 9B/free 模型在 Metis 上真实可用。

任务：

1. 创建 `tests/evals/real_model_tasks/`。
2. 定义 10 个任务：
   - 读项目生成架构报告。
   - 修复一个测试失败。
   - 生成 Markdown 文档。
   - 汇总 5 个文件。
   - 使用 shell 运行测试。
   - 生成 artifact 并注册。
   - 识别缺失证据并 blocked。
   - 处理大工具输出。
   - parser repair。
   - no_fake_completion。
3. 每个任务定义：
   - prompt
   - allowed_tools
   - expected_artifacts
   - expected_evidence
   - quality_gates
   - timeout

验收：

- 无 key 时 skip。
- 有 key 时真实运行并输出报告。

测试：

- `tests/e2e/test_real_model_task_suite.py`

#### A2 EvalRunner

状态：TODO  
优先级：P0

任务：

1. 创建 `metis/evals/runner.py`。
2. 实现 EvalTaskSpec。
3. 实现 EvalResult。
4. 统计：
   - success
   - parser_failure
   - tool_failure
   - quality_failure
   - false_completion
   - turns_used
   - tool_calls
   - latency
5. 输出 JSON + Markdown 报告。

验收：

- FakeProvider eval 可稳定通过。
- 真实 provider eval 可输出真实结果。

### Phase B：运行状态机强化

#### B1 RuntimeStatus

状态：TODO  
优先级：P0

任务：

1. 定义 RuntimeStatus enum。
2. 映射 strict output status。
3. AgentRunResult 使用统一状态。
4. StepExecutor 识别 blocked/needs_more_work。

验收：

- 模型返回 `blocked` 时 Step 不得 done。
- 模型返回 `needs_more_work` 时 Step 状态为 needs_more_work。

#### B2 Step 状态机

状态：TODO  
优先级：P0

任务：

1. 定义合法状态转移表。
2. StateStore update_step_status 校验转移。
3. 非法转移抛错。
4. 增加状态转移轨迹记录。

验收：

- failed 不能直接变 done，除非 reset/retry。

### Phase C：证据与质量门升级

#### C1 Evidence Schema

状态：TODO  
优先级：P0

任务：

1. 定义 EvidenceSourceType。
2. 定义 EvidenceStrength。
3. 定义 EvidenceClaimLink。
4. StateStore 增加字段。

验收：

- 每条 evidence 有类型和强度。

#### C2 ClaimEvidenceMatcher

状态：TODO  
优先级：P0

任务：

1. 定义 claim schema。
2. 为生成、测试、上传、修复、运行建立强证据规则。
3. no_fake_completion 使用 matcher。
4. 输出缺失证据解释。

验收：

- `已上传` 必须有 git/github/upload 证据。
- `已测试` 必须有测试命令和 exit_code=0。

#### C3 交付物质量门

状态：TODO  
优先级：P0

任务：

1. MarkdownQualityGate。
2. CodeChangeQualityGate。
3. TestRunQualityGate。
4. ArtifactReferenceGate。
5. ReportCompletenessGate。

验收：

- 空洞报告无法通过。
- 没有测试成功证据无法通过修复任务。

### Phase D：工具安全与审批

#### D1 ToolPolicyEngine

状态：TODO  
优先级：P0

任务：

1. ToolRiskLevel：read/write/execute/network/credential/destructive。
2. ToolPolicy。
3. command allowlist/denylist。
4. mutating tool approval policy。

验收：

- 删除、格式化磁盘、泄露 secret 等命令被阻止。

#### D2 Approval System

状态：TODO  
优先级：P0

任务：

1. ApprovalRequest。
2. ApprovalStore。
3. ToolDispatcher pre-dispatch approval。
4. CLI approval flow。
5. timeout/reject handling。

验收：

- 高风险工具未审批不能执行。

### Phase E：上下文与记忆

#### E1 ContextItem 化

状态：TODO  
优先级：P0

任务：

1. ContextItem。
2. priority/scopes/source。
3. evidence-first packing。
4. recent message packing。
5. compression audit。

验收：

- evidence 和 current task constraints 优先保留。

#### E2 MemoryStore

状态：TODO  
优先级：P0

任务：

1. Memory model。
2. principle/rule/fact/pattern/log。
3. retrieval。
4. update gate。
5. cross-session persistence。

验收：

- 新 session 能读取已确认 rules/facts。

### Phase F：多场景开发基础设施

#### F1 agent.yaml

状态：TODO  
优先级：P1

任务：

1. 定义 schema。
2. 支持 model/profile/tools/skills/adapters/quality_gates。
3. Loader。
4. Validator。
5. AgentFactory。

验收：

- 通过 YAML 创建一个场景 agent。

#### F2 metis init

状态：TODO  
优先级：P1

任务：

1. CLI 增加 init。
2. 生成目录：
   - agent.yaml
   - adapters/
   - skills/
   - evals/
   - tests/
   - README.md
3. 内置模板：
   - research
   - code
   - document
   - business
   - general

验收：

- 新建场景项目后可跑 smoke test。

#### F3 Adapter 能力迁移

状态：TODO  
优先级：P1

任务：

1. 梳理 Aurora 通用能力。
2. 梳理 Sophia 通用能力。
3. 分类：
   - 可迁移到 core
   - 适合 adapter
   - 保持业务侧
4. 包装 3-5 个通用 adapter tools。

验收：

- Metis 可调用真实 Aurora/Sophia 通用工具，而不是只 inspect。

### Phase G：Swarm 生产化

#### G1 SwarmAgentRunner

状态：TODO  
优先级：P1

任务：

1. 每个 role 创建 AgentLoop。
2. 绑定 filtered tools。
3. 隔离 context。
4. 共享 evidence/artifact。

验收：

- explorer + verifier + auditor 真实串联执行。

#### G2 Audit-enforced Synthesis

状态：TODO  
优先级：P1

任务：

1. 子任务必须 audit。
2. audit failed 不进入 synthesis。
3. synthesis 输出 evidence refs。
4. finalization guard 再审。

验收：

- 无证据子任务不能进入最终答案。

### Phase H：Recovery 与观测

#### H1 Recovery 接入 AgentLoop

状态：TODO  
优先级：P1

任务：

1. provider complete 包裹 RecoveryManager。
2. tool dispatch 可配置 retry。
3. rate limit/backoff。
4. recovery events。

验收：

- 网络临时失败可恢复。
- auth/security 不重试。

#### H2 RunReport

状态：TODO  
优先级：P1

任务：

1. Span model。
2. Run timeline。
3. Tool timeline。
4. Token/latency/error metrics。
5. Markdown/JSON export。

验收：

- 任意 E2E run 能生成可读报告。

### Phase I：状态、调度、部署

#### I1 State migration

状态：TODO  
优先级：P1

任务：

1. schema_version。
2. migrations directory。
3. backup before migration。
4. migration tests。

验收：

- 从旧 DB 自动升级到新 schema。

#### I2 Durable Scheduler

状态：TODO  
优先级：P1

任务：

1. 持久化 pending jobs。
2. missed schedule handling。
3. restart resume。
4. circuit breaker。

验收：

- 进程重启后 schedule 不丢。

#### I3 Service API

状态：TODO  
优先级：P2

任务：

1. FastAPI optional server。
2. run endpoint。
3. status endpoint。
4. artifacts endpoint。
5. traces endpoint。

验收：

- 外部系统可调用 Metis agent。

### Phase J：文档和发布

#### J1 教程文档

状态：TODO  
优先级：P2

任务：

1. 从零创建场景 agent。
2. 写 adapter。
3. 写 plugin。
4. 写 eval。
5. 接真实模型。
6. Debug 失败 run。

验收：

- 按文档能创建新场景 agent。

#### J2 包发布验证

状态：TODO  
优先级：P2

任务：

1. build wheel。
2. install smoke。
3. CLI smoke。
4. package data check。

验收：

- 新环境 pip install 后可运行。

## 7. 推荐执行顺序

第一批必须先做：

1. A1 真实模型任务集。
2. A2 EvalRunner。
3. B1 RuntimeStatus。
4. C1 Evidence Schema。
5. C2 ClaimEvidenceMatcher。
6. D1 ToolPolicyEngine。
7. E1 ContextItem 化。

原因：

- 这些直接决定小模型是否真的可用。
- 这些是所有场景智能体共享的底座能力。
- 没有这些，后续 adapter、swarm、plugin 都容易变成表面能力。

第二批：

1. F1 agent.yaml。
2. F2 metis init。
3. H1 Recovery 接入。
4. H2 RunReport。
5. I1 State migration。

第三批：

1. F3 Adapter 能力迁移。
2. G1 SwarmAgentRunner。
3. G2 Audit-enforced Synthesis。
4. I2 Durable Scheduler。
5. J1/J2 文档发布。

## 8. 下一步建议

建议下一轮直接从 **Phase A：真实小模型可用性验证** 开始。理由是：

- 它最能暴露真实问题。
- 它能证明 Metis 是否真的服务于“免费 9B 小模型高质量交付”。
- 它会反向驱动 Context、Evidence、QualityGate、Parser Repair、ToolPolicy 的真实优化。

