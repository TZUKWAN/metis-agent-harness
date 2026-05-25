# Metis Agent Harness 完整技术报告

日期：2026-05-25  
对象：`D:\LATEXTEST\metis-agent-harness` 当前工作区  
报告性质：基于当前文件系统源码、文档、测试和命令输出的技术审计报告  

## 1. 结论摘要

Metis Agent Harness 当前已经从一个基础 runtime kernel 扩展为一个面向“小模型高可靠智能体”的通用 harness 底座。它的核心目标不是实现某个具体业务智能体，而是提供一套可复用的智能体基础设施：模型适配、工具调度、上下文压缩、状态持久化、证据追踪、质量门、评估体系、修复计划、制品 attestation、开发者工作台，以及可复用 CLI/TUI/Web 入口。

截至本报告生成时，项目具备以下事实状态：

- Python 源码文件数量：111 个。
- 测试文件数量：104 个。
- 文档文件数量：168 个。
- 包名：`metis-agent-harness`。
- Python 要求：`>=3.11`。
- 核心运行依赖：`httpx>=0.27`。
- UI 可选依赖：`fastapi>=0.110`、`uvicorn>=0.27`。
- 命令行入口：`metis = "metis.adapters.cli:main"`。
- 最近一次全量本地测试结果：`421 passed, 4 skipped`。
- 最近一次编译检查：`python -m compileall -q metis` 通过。

客观评价：

1. Metis 当前已经达到“本地可运行、核心链路可验证、面向多场景智能体开发可复用”的阶段。
2. 项目的主要强项在于：严格工具约束、证据导向、评估和修复闭环、面向 9B/flash 小模型的控制面设计、可审计 artifact、可复用 app shell、独立开发者入口。
3. 项目仍不是“完整生产平台”形态：没有完整用户权限系统、没有多租户服务端、没有稳定发布包流程、没有真正持久化的 Web 会话数据库、真实模型 e2e 仍受外部 API 限流影响。
4. 对于“作为智能体底座，让开发者在其上快速定制不同场景智能体”的目标，当前架构方向是成立的，并且已经提供了 `metis develop` 作为开发者工作流入口。

## 2. 项目定位

Metis 的定位是 domain-neutral agent harness，即“不绑定业务场景的智能体运行底座”。它不应该预设智能体一定是论文助手、项目管理助手、代码助手或计划书助手，而是提供一个统一的可靠运行框架，让开发者通过 manifest、prompt、工具、adapter、eval、slash command 等方式快速构建面向某个具体场景的智能体。

它面对的核心问题包括：

- 免费或低成本 9B/flash 模型能力不稳定，容易遗漏步骤、编造完成、错误调用工具。
- 多工具智能体容易出现参数格式错误、越权路径访问、重复失败调用、没有证据却声称完成。
- 场景智能体如果每次都重写 CLI/TUI/Web UI，会造成大量重复工程。
- 智能体改造如果直接改核心架构，会导致底座不可维护。
- 没有评估、比较、质量门、修复计划和 artifact attestation 的智能体很难形成可重复质量闭环。

Metis 的解决思路是把模型能力不足的部分尽量转移到 harness 控制面：

- 工具调用前做 schema guard。
- 工具执行后记录结构化结果。
- 输出前做 strict finalization 和 evidence check。
- 评估结果进入 comparison、diagnosis、repair task、repair plan。
- 修复计划、eval stubs、targeted suite、preflight result 都写 attestation。
- 开发新智能体时先分析、出方案、等批准，再拆任务和应用变更。

## 3. 代码结构总览

当前 `metis/` 下主要模块如下：

| 模块 | 职责 |
|---|---|
| `runtime` | AgentLoop、多轮执行、模型 profile、预算、strict output、finalization、执行控制。 |
| `providers` | 模型 provider 抽象、fake provider、OpenAI-compatible provider、响应解析器。 |
| `tools` | ToolSpec、工具注册、工具路由、dispatcher、schema validation、guardrails、结果存储。 |
| `context` | 上下文构建和压缩。 |
| `state` | SQLite 状态持久化。 |
| `evidence` | evidence schema、ledger、resolver、matcher、tool result evidence extractor。 |
| `artifacts` | artifact store 和 artifact validators。 |
| `quality` | quality gates 和 gate runner。 |
| `evals` | eval runner、suite validation、real model suite、compare、diagnosis、repair plan、attestation。 |
| `telemetry` | hooks、timeline、trajectory。 |
| `events` | HookBus 和事件类型。 |
| `recovery` | 错误分类、retry policy、recovery manager。 |
| `loops` | scheduler 和 loop manager。 |
| `swarm` | 任务拆解、角色、编排、审查、结果综合。 |
| `skills` | skill index、loader、manager。 |
| `plugins` | plugin API 和 manager。 |
| `adapters` | CLI、Sophia adapter、Aurora adapter、基础 adapter。 |
| `app` | 可复用 CLI/TUI/Web app shell 所需 manifest、runtime、TUI、FastAPI Web。 |
| `develop` | `metis develop` 开发者工作流。 |
| `security` | 路径安全、prompt injection scanner、redaction。 |
| `planning` | task contract 和 planning model。 |
| `prompts` | prompt assembler。 |

这个结构已经比较接近“框架型项目”而不是“单一智能体项目”。业务场景应通过 adapter、tool、prompt、manifest、eval suite 和 slash command 接入，而不应该直接改 runtime 核心。

## 4. 核心执行链路

### 4.1 AgentLoop

`metis/runtime/loop.py` 是运行时核心。它负责：

1. 接收 `AgentRunRequest`。
2. 按 profile 获取工具 schema。
3. 构建压缩后的上下文。
4. 调 provider 获取模型响应。
5. 如果模型没有 native tool calls，则通过 parser chain 尝试解析文本工具调用。
6. 校验工具调用数量限制。
7. 执行工具调用。
8. 记录 tool result、trace event、hook event。
9. 在没有 tool call 时进入 finalization。
10. strict output 开启时，尝试修复最终输出。
11. strict output 修复失败时返回 `blocked`，而不是伪装成 `final`。

这个设计对小模型很关键：小模型容易输出非标准 JSON、工具调用格式不稳定、过度调用工具或在没有证据时直接给最终答案。AgentLoop 把这些问题集中在 runtime 层治理。

### 4.2 Provider 抽象

`metis/providers/base.py` 定义 provider 接口。当前有：

- `FakeProvider`：用于测试。
- `OpenAICompatibleProvider`：用于 OpenAI-compatible chat completions endpoint。

`OpenAICompatibleProvider` 支持：

- `METIS_BASE_URL`
- `METIS_API_KEY`
- `METIS_MODEL`
- `METIS_PROVIDER_MAX_RETRIES`
- `METIS_PROVIDER_RETRY_BACKOFF_SECONDS`

它已经加入 429、5xx、timeout、transport error 的重试逻辑。真实测试中，智谱接口曾返回 `429 Too Many Requests`，项目没有伪造通过，而是把外部限流作为 network test skip 条件处理。

### 4.3 Tool 层

工具系统由以下文件组成：

- `metis/tools/spec.py`
- `metis/tools/registry.py`
- `metis/tools/tool_router.py`
- `metis/tools/dispatcher.py`
- `metis/tools/schema_validator.py`
- `metis/tools/schema_feedback.py`
- `metis/tools/guardrails.py`
- `metis/tools/result_store.py`
- `metis/tools/builtin.py`

当前工具层的关键能力：

1. 工具注册和 schema 暴露。
2. 根据 stage、profile、allowed tools 做工具路由。
3. 工具参数执行前 JSON schema 校验。
4. schema 错误生成 repair feedback。
5. 工具调用 guardrails。
6. 工具结果持久化和超大输出存储。
7. 内置文件和命令工具。
8. `run_shell` 结果保留 command 字段，便于 evidence extractor 判断“测试/命令是否真实运行”。

### 4.4 Context 与预算

`metis/context` 和 `metis/runtime/budgets.py` 提供上下文预算控制。小模型上下文和指令遵循能力较弱，因此 Metis 需要把消息、工具结果、证据、最近上下文做压缩和取舍。

项目当前支持：

- context engine 构建最终 messages。
- 超预算压缩。
- 工具结果外置存储。
- profile 级预算控制。

这部分仍是可继续增强的区域：当前已经可用，但还可以进一步做分层记忆、长期知识压缩、任务阶段感知上下文选择。

## 5. 证据、真实性和防伪完成机制

Metis 的核心设计之一是避免模型“说完成但没有完成”。

相关模块：

- `metis/evidence/schema.py`
- `metis/evidence/ledger.py`
- `metis/evidence/resolver.py`
- `metis/evidence/matcher.py`
- `metis/evidence/extractor.py`
- `metis/runtime/finalization.py`
- `metis/quality/gates.py`

已经实现的关键机制：

1. 从 tool result 提取 evidence。
2. command/write/test 等不同证据类型区分。
3. finalization guard 检查最终输出引用的 evidence。
4. strict profile 要求 done evidence refs。
5. `no_fake_completion` gate 对“已测试”“已生成”“已上传”“已运行”等声明做类型化证据要求。
6. 没有足够证据时应 blocked 或 needs_more_work，而不是 final。

这对 9B 模型尤其重要，因为小模型最容易“语言上完成”，但没有真实命令、文件、测试、上传或运行证据。

## 6. 安全模型

相关文件：

- `docs/security-model.md`
- `metis/security/paths.py`
- `metis/security/prompt_injection.py`
- `metis/security/redaction.py`
- `metis/tools/guardrails.py`

已有能力：

1. 路径安全检查，阻止路径逃逸。
2. 敏感路径拒绝。
3. Prompt injection 文本扫描。
4. 凭据 redaction。
5. 工具 guardrails。
6. 对外部上下文和工具输出做基础安全治理。

当前安全模型是基础可用，不是完整企业安全平台。尚未覆盖：

- 多用户权限模型。
- Web UI 登录认证。
- 组织级 RBAC。
- 审计日志服务化。
- sandbox isolation。
- 远程工具权限审批流。

## 7. 评估系统

`metis/evals` 是当前项目最复杂、最成熟的模块之一。

主要文件：

- `runner.py`
- `suite_run.py`
- `suite_validation.py`
- `real_model_suite.py`
- `gate.py`
- `compare.py`
- `attestation.py`
- `failures.py`
- `provenance.py`

### 7.1 Eval Suite

Metis 支持版本化 eval suite：

- 文档：`docs/evals/suite-schema.md`
- JSON schema：`docs/evals/suite-schema-v1.json`
- 代码验证：`metis/evals/suite_validation.py`

支持两类 task entry：

1. 直接 `EvalTaskSpec`。
2. 带 repair metadata 的 wrapped task entry。

Eval task 能表达：

- prompt
- allowed tools
- expected artifacts
- required evidence sources
- requirement criteria
- quality gates
- schema repair expectations
- artifact verification fixture
- target run dirs

### 7.2 Real Small Model Eval

`metis/evals/real_model_suite.py` 定义真实小模型评估任务。测试文件 `tests/e2e/test_local_9b_eval.py` 覆盖：

- eval suite task 定义。
- report writer。
- stable run directory。
- latest pointer。
- configured endpoint run。

网络测试受外部 API 限制影响。当前处理方式是：配置了真实 endpoint 才运行；如果 provider 明确返回 429，则标记为 skip，而不是伪造结果。

### 7.3 Generic Eval Suite

`metis/evals/suite_run.py` 支持任意 loadable eval suite JSON。它可以：

- validate suite。
- 判断是否需要模型执行。
- 对 `requires_model_execution=false` 的 artifact verification fixture 离线运行。
- 生成 pre-run contract。
- 写 eval report、manifest、task specs。
- 支持 gate、compare latest、compare baseline。

### 7.4 Gate

`metis/evals/gate.py` 提供 release gate：

- success rate
- failed tasks
- invalid tool calls
- schema violations
- schema repair hint recovery
- retry budget exhaustion
- pre-dispatch blocks
- trajectory failures
- failure clusters
- critical remediations
- suite schema evidence
- task contract evidence
- provenance evidence
- pre-run contract evidence
- run attestation evidence

这意味着 Metis 的质量判断不只是“模型回答了”，而是要求 artifact、evidence、schema、trajectory、attestation 都满足门槛。

## 8. 比较、诊断、修复闭环

`metis/evals/compare.py` 已经实现了一条较完整的修复链：

1. `compare_eval_runs()`
2. `diagnose_eval_comparison()`
3. `build_repair_tasks_from_diagnosis()`
4. `build_repair_plan()`
5. `build_eval_stubs_from_repair_tasks()`
6. `materialize_eval_suite()`
7. `repair-execute` preflight
8. `repair-execute` attempt status persistence

### 8.1 Compare

比较能力包括：

- success rate drift
- newly failed tasks
- recovered tasks
- still failed tasks
- regressed metrics
- task spec drift
- environment drift
- provenance hash drift
- pre-run/post-run mismatch
- attestation trust state
- cluster count trend
- severity upgrade/downgrade
- quality gate drift
- requirement gap
- artifact path diagnostic summary

### 8.2 Diagnosis 和 Repair Tasks

Diagnosis 会把 comparison 的 regression reasons 转成结构化 entries。Repair tasks 会记录：

- reason
- priority
- owner area
- task ids
- cluster keys
- artifact paths
- timeline paths
- run metadata
- schema repair hint events
- quality gate changes
- trust state
- likely source modules
- recommended action
- suggested eval

这让小模型后续修复时不需要从自然语言长报告中猜问题来源。

### 8.3 Repair Plan

Repair plan 已有 phase 概念：

- `phase-0-restore-artifact-trust`
- `phase-0b-repair-suite-hygiene`
- `phase-1-stop-release-blockers`
- `phase-2-add-targeted-evals`
- `phase-3-stabilize-owners`

每个 phase 有：

- phase id
- title
- description
- phase type
- hard precondition
- blocks
- required completed preconditions
- status
- blocked_by
- task_ids
- task_count

Plan 顶层有：

- task_count
- tasks
- priority_buckets
- owner_areas
- phases
- phase_status_summary
- next_actions

### 8.4 Repair Execute

CLI 中已有：

- `metis eval repair-execute`
- `metis eval verify-repair-preflight`

`repair-execute` 当前是确定性的 preflight 和 attempt recorder，不是自动改代码的模型执行器。它会检查：

- repair-plan attestation
- repair-plan load
- requested phase executable
- targeted eval stubs attestation
- targeted eval suite attestation

它可以写：

- `repair-execute-preflight.json`
- `repair-execute-preflight.md`
- `repair-execute-preflight-attestation.json`
- `repair-execute-preflight-attestation.md`
- `repair-execute-attempt/repair-execute-attempt.json`
- `repair-execute-attempt/repair-execute-attempt.md`
- `updated-repair-plan/repair-plan.json`
- `updated-repair-plan/repair-plan.md`
- `updated-repair-plan/repair-plan-attestation.json`
- `updated-repair-plan/repair-plan-attestation.md`

客观边界：它还不是完整的“自动执行修复 agent”。它提供的是修复执行前控制面和状态持久化，为未来真实 repair executor 提供安全入口。

## 9. Artifact Attestation

`metis/evals/attestation.py` 支持多种 attestation：

1. Run artifact attestation。
2. Repair plan attestation。
3. Targeted eval stubs attestation。
4. Targeted eval suite attestation。
5. Repair execute preflight attestation。

Attestation 记录：

- in-toto statement type
- predicateType
- schema_version
- subject
- SHA256 digest
- size_bytes
- builder
- output/run dir
- profile
- task count
- artifact count
- generated_at

还支持可选 HMAC 签名：

- `METIS_ATTESTATION_SIGNING_KEY`
- `METIS_ATTESTATION_KEY_ID`
- `METIS_REQUIRE_ATTESTATION_SIGNATURE`

如果配置签名 key，写出的 attestation 会包含 signature。验证时：

- 签名存在但 key 缺失会失败。
- key_id 不匹配会失败。
- HMAC mismatch 会失败。
- 设置 `METIS_REQUIRE_ATTESTATION_SIGNATURE=1` 时，unsigned attestation 会失败。

这使得 Metis 的制品链从“本地 digest 可验证”进一步走向“CI/操作者信任边界可验证”。

## 10. App Surfaces：CLI/TUI/Web

当前项目已经有 manifest-driven app shell。

相关文件：

- `metis/app/manifest.py`
- `metis/app/runtime.py`
- `metis/app/tui.py`
- `metis/app/web.py`
- `metis/app/web_assets/templates/index.html`
- `metis/app/web_assets/static/app.js`
- `metis/app/web_assets/static/style.css`
- `docs/app-surfaces.md`

### 10.1 Manifest

`AgentAppManifest` 字段：

- name
- subtitle
- description
- version
- workspace
- model
- base_url
- profile
- icon_text

加载来源：

- `metis-agent.json`
- `METIS_APP_MANIFEST`
- `METIS_APP_NAME`
- `METIS_APP_SUBTITLE`
- `METIS_APP_DESCRIPTION`
- `METIS_APP_VERSION`
- `METIS_WORKSPACE`
- `METIS_MODEL`
- `METIS_BASE_URL`
- `METIS_PROFILE`
- `METIS_APP_ICON`

### 10.2 用户运行入口

当前 CLI 支持：

- `metis run --manifest metis-agent.json`
- `metis tui --manifest metis-agent.json`
- `metis web --manifest metis-agent.json`
- `metis app init`
- `metis app show`

Web UI 是从 Sophia 风格的 ChatGPT-like 单页界面思路抽象出来，但已经改成 Metis 通用 shell，不绑定 Sophia 的研究场景。它支持：

- sidebar brand area
- session list
- WebSocket chat
- HTTP chat fallback
- model/profile/workspace label
- manifest-driven brand

客观边界：

- Web session 当前以内存方式保存，不是数据库持久化。
- 没有登录认证。
- 没有多用户隔离。
- 前端是轻量原生 HTML/CSS/JS，不是大型 React/Vue 项目。

## 11. Developer Workbench：`metis develop`

这是最新加入的开发者入口，目标是面向“基于 Metis 开发新智能体”的流程，而不是普通用户运行智能体。

相关文件：

- `metis/develop/workflow.py`
- `docs/developer-workbench.md`
- `metis/swarm/decomposer.py`
- `tests/unit/test_develop_workflow.py`
- `tests/unit/test_cli_eval.py`

### 11.1 命令

交互式：

```powershell
metis develop
```

非交互 proposal：

```powershell
metis develop --request "Build a grant writing agent" --name "Grant Builder"
```

批准后生成实际改造产物：

```powershell
metis develop --request "Build a grant writing agent" --name "Grant Builder" --approve
```

### 11.2 默认流程

`metis develop` 的设计原则：

1. 用户描述目标智能体。
2. Metis 形成分析报告。
3. Metis 形成改造方案。
4. 默认等待用户批准。
5. 批准后写 branding、prompts、Claude Code command、Codex command、task files。
6. 任务拆解足够细，适配小模型执行。
7. 任务拆解逻辑同步到 `metis.swarm.decomposer.decompose_development_plan()`。

### 11.3 输出文件

未批准也会写：

- `analysis-report.json`
- `analysis-report.md`
- `adaptation-plan.json`
- `adaptation-plan.md`
- `task-breakdown.json`
- `task-breakdown.md`

批准后额外写：

- `metis-agent.json`
- `prompts/<agent>-system.md`
- `prompts/<agent>-developer.md`
- `.claude/commands/<agent>.md`
- `.codex/commands/<agent>.md`
- `metis-dev-tasks.json`

### 11.4 关键限制

当前 `metis develop` 还不是一个真正联网检索和自动修改当前项目所有文件的完整 agent。它已经实现了 workflow skeleton、报告/方案/任务生成、批准门槛和产物写入；但“充分检索各种资料”目前以 research query 形式进入报告，还没有内置浏览器/search executor 自动抓取外部资料。

如果要进一步生产化，需要补：

- research tool runner。
- source citation artifact。
- approval state persistence。
- patch generation executor。
- applied diff review。
- UI 化 develop 对话界面。

## 12. Swarm 与任务编排

`metis/swarm` 当前包含：

- analyzer
- auditor
- bus
- decomposer
- filtered registry
- orchestrator
- roles
- synthesizer

默认 `TaskDecomposer` 会拆：

1. explore
2. implement
3. verify
4. audit

新增 `decompose_development_plan()` 用于 developer workflow。它按 phase 和 allowed changes 拆细任务，每个 task 包含：

- id
- phase_id
- title
- surface
- instruction
- verification
- status

这符合“模型性能有限，需要拆得足够细”的方向。当前拆解是 deterministic template，不是模型动态规划。它可靠、可测试，但灵活性有限。

## 13. CLI 入口汇总

当前 `metis.adapters.cli` 支持的主要命令：

### 基础

- `metis doctor`
- `metis run`
- `metis tui`
- `metis web`
- `metis app init`
- `metis app show`
- `metis develop`

### Trace

- `metis trace show`

### Eval

- `metis eval real-small-model`
- `metis eval compare`
- `metis eval gate`
- `metis eval diagnose`
- `metis eval repair-plan`
- `metis eval verify-repair-plan`
- `metis eval verify-eval-stubs`
- `metis eval verify-targeted-suite`
- `metis eval repair-execute`
- `metis eval verify-repair-preflight`
- `metis eval eval-stubs`
- `metis eval materialize-stubs`
- `metis eval run-suite`
- `metis eval validate-suite`
- `metis eval list-tools`
- `metis eval list-quality-gates`

CLI 已经从简单入口发展为整个 harness control plane 的操作接口。

## 14. Sophia/Aurora/Hermes 抽取情况

项目背景中，Metis 是从 Sophia、Aurora 以及 Hermes 的 harness 思路中抽取出来的。当前代码中有：

- `metis/adapters/sophia.py`
- `metis/adapters/aurora.py`
- 对应 integration tests：
  - `tests/integration/test_sophia_adapter.py`
  - `tests/integration/test_aurora_adapter.py`

Web UI 的通用 shell 复用了 Sophia Web UI 的产品思路：侧边栏、会话、ChatGPT-like message area、settings/workspace/model surface。但 Metis 没有把 Sophia 的研究业务逻辑带入核心，而是保留了 domain-neutral shell。

这是正确方向：场景项目可以复用 UI/harness，但场景知识不应该污染 Metis core。

## 15. 测试状态

当前测试目录：

- `tests/unit`
- `tests/integration`
- `tests/e2e`
- `tests/fixtures`

最近一次全量结果：

```text
421 passed, 4 skipped
```

最近一次编译：

```powershell
python -m compileall -q metis
```

结果：通过。

网络测试状态：

- `tests/integration/test_openai_compat_network.py`
- `tests/e2e/test_local_9b_eval.py`

网络测试依赖真实 `METIS_BASE_URL`、`METIS_API_KEY`、`METIS_MODEL`。当外部接口返回 429 时，测试会 skip 并说明是 external provider rate limited。这个处理是客观的：它没有伪造模型结果，也没有把外部速率限制当成代码失败。

## 16. 文档状态

重要文档：

- `README.md`
- `docs/architecture.md`
- `docs/module-spec.md`
- `docs/security-model.md`
- `docs/small-model-mode.md`
- `docs/testing-strategy.md`
- `docs/extension-guide.md`
- `docs/app-surfaces.md`
- `docs/developer-workbench.md`
- `docs/evals/suite-schema.md`
- `docs/evals/repair-plan-ci-recipe.md`
- `docs/evals/9b-eval-report.md`
- `docs/iteration/*`
- `docs/audits/*`

文档数量很大，优点是演进历史完整；缺点是部分早期中文文档存在编码显示异常，且 `README.md` 仍然写着 “Sprint 1 runtime-kernel build phase”，已经落后于当前实际能力。建议后续更新 README 的 current scope，避免外部读者低估项目成熟度。

## 17. 当前成熟能力清单

可以认为已基本可用的能力：

1. AgentLoop 多轮运行。
2. OpenAI-compatible provider。
3. Fake provider 测试。
4. 工具注册和执行。
5. 工具 schema validation。
6. schema repair feedback。
7. tool call parser chain。
8. strict output parsing。
9. finalization guard。
10. evidence ledger/resolver/matcher/extractor。
11. context compression。
12. runtime profiles。
13. tool result store。
14. path security。
15. prompt injection scanner。
16. redaction。
17. quality gates。
18. eval runner。
19. real small model eval suite。
20. generic eval suite runner。
21. suite schema validation。
22. eval gate。
23. eval comparison。
24. diagnosis。
25. repair task generation。
26. repair plan。
27. repair phase status。
28. repair plan enforcement。
29. targeted eval stubs。
30. materialized targeted suite。
31. run attestation。
32. repair plan attestation。
33. targeted eval artifact attestation。
34. repair execute preflight。
35. repair execution attempt status。
36. HMAC signed attestations。
37. app manifest。
38. reusable CLI/TUI/Web app surfaces。
39. developer workbench。
40. swarm decomposer/orchestrator/auditor/synthesizer 基础能力。

## 18. 主要风险和不足

### 18.1 不是完整生产 SaaS

Metis 是本地/框架型 harness，不是多租户服务。Web UI 没有认证、授权、用户隔离、审计服务和数据库会话持久化。

### 18.2 `metis develop` 仍是工作流骨架

它已经有分析、方案、批准、任务拆解和产物写入，但它还没有真正调用搜索工具抓取资料，也没有自动 patch 当前项目。它更像“开发者改造流程生成器”，不是完整 autonomic builder。

### 18.3 自动修复还停留在 preflight/attempt 层

Repair pipeline 已经可以诊断和规划，但真实执行修复代码仍需要外部 agent 或后续 repair executor。当前 `repair-execute` 不会自动改业务代码。

### 18.4 文档存在历史噪音

`docs/iteration` 很完整，但对新读者来说信息量过大。需要新增一个“当前稳定 API 和推荐路径”文档，把历史迭代与当前用法分开。

### 18.5 Git 状态缺失

当前 `D:\LATEXTEST\metis-agent-harness` 不是 git 仓库，因此无法用 git diff、commit history、branch、remote 作为证据。报告只能基于当前文件系统和测试命令。

### 18.6 外部模型 e2e 受 API 限流影响

真实网络测试不稳定不是代码层 bug，而是账号速率限制。生产验证需要稳定额度或本地模型 endpoint。

## 19. 建议路线图

### 优先级 P0

1. 更新 README，使其反映当前真实能力，而不是 Sprint 1。
2. 给 `metis develop` 增加真实 research executor：
   - web search
   - source capture
   - citation artifact
   - research-report attestation
3. 给 Web UI 增加 develop mode 页面：
   - 用户描述智能体需求
   - 显示分析报告
   - 显示方案
   - 用户批准/修改
   - 展示任务拆解
   - 应用改造产物
4. 给 app shell 加持久化 session store。
5. 定义稳定的 downstream agent project template。

### 优先级 P1

1. 实现 repair executor：
   - consume verified preflight
   - apply patch or prompt/tool changes
   - update repair plan
   - run targeted eval
   - write attested attempt result
2. 增加 `metis develop --interactive-web` 或 `metis develop --web`。
3. 增强 plugin/tool registration，使 downstream agent 更少改源码。
4. 增加 manifest schema。
5. 对 `.claude/commands` 和 `.codex/commands` 定义更完整模板。

### 优先级 P2

1. Web UI 登录认证。
2. 多 workspace 管理。
3. 多 provider/model profile UI。
4. 可视化 eval dashboard。
5. 可视化 repair plan / task board。
6. Agent package export/import。

## 20. 总体判断

Metis 当前已经具备一个高质量智能体 harness 的基础形态，尤其适合你的目标：让性能有限的 9B/flash 模型通过强 harness 控制面产出更可靠结果。

它的价值不在于“模型更聪明”，而在于：

- 把任务拆小。
- 把工具调用收紧。
- 把证据记录下来。
- 把最终回答约束住。
- 把评估和修复变成结构化闭环。
- 把开发新智能体的流程变成分析、方案、批准、拆解、实现、验证。
- 把 CLI/TUI/Web 入口抽象成 manifest-driven reusable app shell。

当前可以客观称为：

```text
本地可用、可测试、可扩展、面向多场景智能体开发的 Metis harness 原型/早期工程化版本。
```

还不应称为：

```text
完整生产 SaaS 平台、完全自动修复平台、完全自主开发智能体工厂。
```

如果下一阶段继续推进，最应该优先做的是把 `metis develop` 从“开发流程产物生成器”推进成“带真实检索、用户审批、自动应用补丁、自动验证、Web 可视化”的开发者工作台。
