# Metis 全架构修复任务清单

日期：2026-05-25
来源方案：`docs/optimization/metis-full-architecture-hardening-plan-2026-05-25.md`

## 1. 执行原则

本任务清单面向整个 Metis harness 架构，不以 `metis develop` 为中心。执行顺序按底座依赖关系排列：先统一任务协议和 prompt 栈，再补工具权限、证据声明映射、checkpoint、release gate、repair execution、package lifecycle 和生产化界面。

每个任务必须满足：

- 有明确修改范围。
- 有对应测试或可复现实证。
- 不用伪实现冒充完成。
- 不把局部入口增强当成全架构修复。
- 不破坏现有 CLI/TUI/Web/develop 入口。

## 2. P0 任务

### P0-01 定义 `TaskContractV1`

- 模块：`metis/planning/task_contract.py`
- 内容：
  - 增加结构化任务契约数据结构。
  - 包含 objective、scope、deliverables、acceptance criteria、allowed tools、evidence requirements、artifact requirements、verification commands、completion definition。
  - 提供 `to_dict()`、`stable_json()`、`contract_hash()`、`to_prompt()`。
  - 提供从自然语言任务构建契约的 helper。
- 验收：
  - 单元测试证明 hash 稳定。
  - 单元测试证明 prompt 包含 objective、验收标准、证据要求。

### P0-02 定义 `PromptStack`

- 模块：`metis/prompts/assembler.py`
- 内容：
  - 增加 `PromptLayer` 和 `PromptStack`。
  - 每层包含 type、source、content、version、enabled、hash。
  - stack 提供 `stack_hash()` 和 `to_system_content()`。
  - `PromptAssembler` 兼容旧接口，同时支持 build stack。
- 验收：
  - 单元测试证明层顺序稳定。
  - 单元测试证明禁用层不进入 system content。
  - 单元测试证明 hash 随内容变化。

### P0-03 入口统一构建 contract 和 prompt stack

- 模块：`metis/app/runtime.py`、`metis/adapters/cli.py`
- 内容：
  - CLI/TUI/Web app runtime 的用户任务先转成 `TaskContractV1`。
  - manifest system/developer prompt 进入 PromptStack。
  - runtime messages 由 PromptStack 生成。
- 验收：
  - app runtime 测试证明 system prompt、developer prompt、task contract 同时进入第一条 system message。
  - CLI run 继续正常构建 AgentRunRequest。

### P0-04 trace 记录 contract 和 prompt stack hash

- 模块：`metis/runtime/response.py`、`metis/runtime/loop.py`
- 内容：
  - `AgentRunRequest` 增加 `task_contract_hash`、`prompt_stack_hash`。
  - `agent.start` trace event 记录这两个 hash。
- 验收：
  - 集成测试证明 trace events 中包含 hash。

### P0-05 develop package 写入 task contract

- 模块：`metis/develop/workflow.py`
- 内容：
  - 生成下游 agent 包时写入 `task-contract.json/md`。
  - task contract 与 requirement、manifest、prompt path 关联。
- 验收：
  - develop workflow 测试证明 proposal 产物中存在 task contract。

### P0-06 工具权限模型

- 模块：`metis/tools/spec.py`、`metis/tools/dispatcher.py`、`metis/app/manifest.py`
- 内容：
  - 定义 tool permission level。
  - ToolSpec 增加 permission metadata。
  - manifest 增加 allowed tool permissions。
  - dispatcher 执行前检查权限。
- 验收：
  - 未授权工具调用被阻断。
  - 权限元数据出现在工具 inventory。

### P0-07 Evidence Claim Mapping

- 模块：`metis/runtime/finalization.py`、`metis/evidence/*`
- 内容：
  - 定义 claim type。
  - 将 tested、generated、uploaded、fixed、verified 等声明映射到证据类型。
  - finalization guard 输出 claim verification table。
- 验收：
  - 无测试证据时不能声明“已测试”。
  - 无文件证据时不能声明“已生成”。

## 3. P1 任务

### P1-01 Checkpoint/Resume

- 定义 `RunCheckpoint`。
- 每个阶段、每个 tool result、每个 task 状态可恢复。
- 增加 `metis run resume` 和 `metis develop resume`。

### P1-02 Eval Release Gate 全面化

- release profile：dev/candidate/release。
- gate 检查 prompt stack hash、task contract hash、tool permission、package portability。

### P1-03 Repair Execution

- repair plan 绑定 executable tasks。
- verified repair plan 才能执行。
- 每个 repair task 写执行证据。

### P1-04 App Shell 行为统一

- CLI/TUI/Web 共享 task contract builder、PromptStack、manifest、provider config、state backend。
- Web/TUI 增加 task/evidence/tool call 可视化。

## 4. P2 任务

### P2-01 Provider Capability Registry

- provider 声明 native tool calling、JSON output、streaming、context、output limit、thinking 支持。

### P2-02 Plugin/Skill Manifest

- 插件声明工具、权限、eval、prompt stack 修改、凭据需求和卸载方式。

### P2-03 Package Lifecycle

- `metis package build`
- `metis package verify`
- `metis package install`
- `metis package export`

### P2-04 顶层架构文档重写

- 重写 `architecture.md`。
- 扩展 `module-spec.md`。
- 新增 Runtime Protocol、Task Contract、Tool Permission、Evidence Contract、Package Spec。

## 5. 当前执行批次

本批次执行：

1. P0-01 `TaskContractV1`
2. P0-02 `PromptStack`
3. P0-03 入口统一构建 contract 和 prompt stack
4. P0-04 trace hash
5. P0-05 develop package 写入 task contract

不在本批次完成但保持在后续目标内：

- P0-06 工具权限模型。
- P0-07 Evidence Claim Mapping。
- P1/P2 全部任务。

## 6. 本批次完成状态

当前已完成并验证：

- P0-01 `TaskContractV1` 基础结构。
- P0-02 `PromptStack` 基础结构。
- P0-03 CLI/app runtime 统一构建 task contract 和 prompt stack。
- P0-04 `AgentRunRequest` 和 `AgentLoop` trace 记录 contract/prompt hash。
- P0-05 `metis develop` proposal 产物写入 `task-contract.json/md`。
- P0-06 工具权限模型基础版：`ToolSpec.permission_level`、`ToolContext.allowed_tool_permissions`、`AgentRunRequest.allowed_tool_permissions`、dispatcher 执行前权限阻断、eval tool inventory 权限字段。
- P0-07 Evidence Claim Mapping 基础版：`ClaimEvidenceMatcher` 输出 `claim_verifications`，覆盖 tested/generated/uploaded/fixed 既有声明，并新增 verified/reviewed/called_api/deployed/merged/released 等高风险声明类型。
- P1-01 Checkpoint/Resume 基础结构：SQLite `run_checkpoints` 表、`record_checkpoint()`、`list_checkpoints()`、`latest_checkpoint()`，AgentLoop 在有 state backend 时记录 `agent.start` 和 finalization checkpoint。
- P1-02 Eval Release Gate 全面化基础版：新增 `dev/candidate/release` gate profiles，CLI `metis eval gate --profile` 可选择档位。
- P2-03 Package Lifecycle 基础版：新增 `metis package build`、`metis package verify`、`metis package install`、`metis package export`，记录 package 文件 hash，校验 manifest、prompt paths、README、hash 完整性，candidate/release 档要求 eval suite，安装前和导出前执行 dev 验证。
- 顶层文档已同步：`docs/architecture.md`、`docs/module-spec.md`、`docs/testing-strategy.md`。

当前聚焦验证：

- `python -m compileall -q metis` 通过。
- `python -m pytest tests/unit/test_task_contract.py tests/unit/test_prompt_assembler.py tests/unit/test_app_runtime.py tests/unit/test_develop_workflow.py tests/unit/test_cli_eval.py tests/integration/test_agent_loop_contract_trace.py -q`：`74 passed`。
- `python -m pytest tests/unit/test_tools.py tests/unit/test_tool_policy.py tests/unit/test_app_manifest.py tests/unit/test_app_runtime.py tests/integration/test_agent_loop_tool_permission.py tests/integration/test_agent_loop_allowed_tools_enforced.py tests/unit/test_cli_eval.py -q`：`88 passed`。
- `python -m pytest tests/unit/test_final_truthfulness_gate.py tests/unit/test_finalization_guard.py tests/integration/test_agent_loop_finalization_guard.py tests/unit/test_claim_evidence_matcher.py tests/unit/test_claim_evidence_matcher_strict.py -q`：`16 passed`。
- `python -m pytest tests/unit/test_state_store.py tests/integration/test_agent_loop_checkpoints.py tests/integration/test_agent_loop_state.py -q`：`5 passed`。
- `python -m pytest tests/unit/test_eval_gate.py tests/unit/test_package_lifecycle.py tests/unit/test_cli_eval.py -q`：`89 passed`。
- `python -m pytest tests/unit/test_package_lifecycle.py tests/unit/test_cli_eval.py -q`：`69 passed`。

仍未完成，保留在后续修复目标内：

- P1 Checkpoint/Resume 的 CLI resume 命令、Repair Execution、App Shell 行为统一。
- P2 Provider Capability Registry、Plugin/Skill Manifest、顶层架构文档完整规范化。

## 7. 本批次完成标准

- `python -m compileall -q metis` 通过。
- P0-01 至 P0-05 对应单元/集成测试通过。
- 全量测试通过或明确列出失败原因和修复计划。
- 文档中的当前执行批次状态真实反映代码现状。
