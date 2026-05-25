# Metis Agent Harness 第五轮最终验证报告

日期：2026-05-25

## 原始目标核验

目标要求：

1. 基于任务清单完成 Metis Agent Harness 构建。
2. 按要求做测试。
3. 任务清单完成后做第二轮审计，形成问题审计报告。
4. 修复第二轮审计问题。
5. 第三轮做功能优化与丰富策略，形成方案。
6. 基于方案构建任务清单。
7. 基于第三轮任务清单完成任务。
8. 第四轮审计，形成问题审计报告。
9. 修复第四轮审计问题。
10. 第五轮全量测试，确保框架达到可用状态。
11. 使用用户提供的 API 做测试，但不得泄露或硬编码 API key。

## 验证证据

### 1. 首轮任务清单

文件：

- `Metis-Agent-Harness-详细任务清单.md`

状态：

- `状态：TODO` 数量：0
- `状态：DONE` 数量：73

结论：完成。

### 2. 第二轮审计与修复

文件：

- `docs/audits/second-round-audit-report.md`

发现并修复：

- A-001 ToolRouter 分类不一致。
- A-002 strict final output 修复失败仍 final。
- A-003 no_fake_completion 证据判断过宽。

修复证据：

- 新增回归测试。
- 第二轮修复后全量测试通过。
- 第三轮后全量测试仍通过。

结论：完成。

### 3. 第三轮优化方案与任务清单

文件：

- `docs/optimization/third-round-optimization-strategy.md`
- `docs/optimization/third-round-task-list.md`

第三轮任务状态：

- `状态：TODO` 数量：0
- `状态：DONE` 数量：6

完成内容：

- FinalizationGuard。
- ToolEvidenceExtractor。
- Trajectory Hook Installer。
- Scheduler Persistence。
- Adapter Health Check。
- 文档和回归更新。

结论：完成。

### 4. 第四轮审计与修复

文件：

- `docs/audits/fourth-round-audit-report.md`

发现并修复：

- F4-001 ToolEvidenceExtractor 未接入 AgentLoop。
- F4-002 run_shell 缺少 command 字段。

修复证据：

- AgentLoop 自动提取 tool evidence 并写入 EvidenceLedger。
- run_shell 结果包含 command。
- 新增自动 evidence extraction 集成测试。

结论：完成。

### 5. 第五轮全量测试

命令：

```bash
python -m pytest -q
python -m compileall -q metis
```

结果：

- `101 passed, 2 skipped`
- 编译检查通过。

结论：完成。

### 6. 真实 API 测试

命令：

```bash
python -m pytest -q -m network
```

配置：

- `METIS_BASE_URL=https://open.bigmodel.cn/api/paas/v4`
- `METIS_MODEL=glm-4.7-flash`
- `METIS_API_KEY` 仅通过环境变量注入。

结果：

- `2 passed, 101 deselected`

安全核验：

- 已扫描真实 API key 片段，未在项目文件中发现。

结论：完成。

## 最终结论

Metis Agent Harness 已完成当前目标范围内的构建、审计、修复、第三轮优化、第四轮审计修复和第五轮全量验证。

当前框架具备：

- OpenAI-compatible provider。
- 小模型执行模式。
- 工具路由、工具防循环、结果落盘。
- 上下文压缩。
- 状态、目标、计划、步骤执行。
- Artifact/Evidence/QualityGate。
- FinalizationGuard 防伪完成。
- Recovery/Security。
- Loop/Scheduler。
- Swarm/Auditor/Synthesizer。
- Skill/Plugin。
- Aurora/Sophia Adapter 初版。
- E2E fixture 与真实 API smoke。

