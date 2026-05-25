# Metis Agent Harness 第四轮问题审计报告

审计时间：2026-05-25

审计范围：

- 第三轮新增优化模块
- AgentLoop 运行闭环
- Evidence/Finalization/Telemetry/Scheduler/Adapter 连接点
- 当前验证命令：`python -m pytest -q`

## 当前基线

- 第三轮优化任务清单：全部 DONE
- 全量测试：`100 passed, 2 skipped`
- 编译检查：通过

## 审计结论

第三轮优化新增模块本身有测试，但发现 2 个运行闭环连接问题。它们不影响现有测试通过，但会削弱“证据自动化”和“最终防伪完成”的实际效果。

## 问题 F4-001：ToolEvidenceExtractor 未接入 AgentLoop

严重级别：High

证据：

- `metis/evidence/extractor.py` 已实现 `ToolEvidenceExtractor`。
- `metis/runtime/loop.py` 在 tool call 完成后只记录 tool_calls，没有调用 extractor，也没有把提取结果写入 EvidenceLedger。

影响：

- run_shell/write_file 等工具结果不会自动进入证据账本。
- FinalizationGuard 虽然可读取 EvidenceLedger，但实际 AgentLoop 不会自动填充证据。

修复要求：

- AgentLoop 增加可选 `evidence_extractor`。
- 当 `evidence_ledger` 存在时，工具调用后自动提取并记录证据。
- 增加集成测试：run_shell 后 EvidenceLedger 中出现 command evidence。

## 问题 F4-002：run_shell 工具结果缺少 command 字段

严重级别：Medium

证据：

- `metis/tools/builtin.py` 的 `run_shell` 返回 `exit_code/stdout/stderr`，但没有返回实际 command。
- `ToolEvidenceExtractor` 会优先读取 `command`，缺失时只能退化为 `run_shell`。

影响：

- 测试、运行、上传等声明的证据可追溯性不足。
- 审计报告无法精确说明运行过哪条命令。

修复要求：

- `run_shell` 返回 `command` 字段。
- 增加测试确认 command 被记录。

## 修复验证计划

1. 新增集成测试覆盖自动 evidence extraction。
2. 更新内置工具 run_shell 输出。
3. 执行：
   - `python -m pytest -q`
   - `python -m compileall -q metis`
4. 最终执行第五轮全量测试和真实 endpoint smoke。

## 修复状态

修复完成时间：2026-05-25

- F4-001 已修复：AgentLoop 在 `evidence_ledger` 存在时自动调用 `ToolEvidenceExtractor`，并将 command/write evidence 写入 EvidenceLedger。
- F4-002 已修复：内置 `run_shell` 工具结果新增 `command` 字段。

修复后验证：

- 定向测试：`tests/integration/test_agent_loop_evidence_extraction.py` 与 `tests/unit/test_evidence_extractor.py` 通过。
- 全量测试：`101 passed, 2 skipped`。
- 编译检查：通过。
