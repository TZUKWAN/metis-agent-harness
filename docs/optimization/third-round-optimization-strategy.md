# Metis Agent Harness 第三轮功能优化与丰富策略

日期：2026-05-25

## 目标

第三轮优化不改变 Metis 的核心定位：它仍然是场景无关的 agent harness 底座。优化重点是把首轮和第二轮形成的能力连接得更紧，使小模型在真实任务中更难虚假完成、更容易复盘、更方便扩展。

## 优化原则

1. 优先补强 harness 层，不引入 Aurora/Sophia 的业务场景耦合。
2. 所有新增能力必须有测试。
3. 真实 endpoint 测试继续可 skip，但不能伪造成功。
4. 不以“更多抽象”为目标，只补当前运行闭环中缺失的关键连接点。

## 优化方向

### O3.1 FinalizationGuard

现状：QualityGate 已存在，但 AgentLoop 最终输出只做 strict JSON 检查，没有统一执行最终防伪质量门。

优化：

- 新增 `FinalizationGuard`。
- AgentLoop 返回 final 前执行 `no_fake_completion`。
- 如果最终声明缺少证据，状态改为 `blocked`。
- 可接入 ArtifactStore 和 EvidenceLedger。

收益：

- 防止上层只看 AgentRunResult.status 而误判。
- 将 C2 防伪完成机制从独立 gate 变成运行时默认保护。

### O3.2 EvidenceExtractor

现状：EvidenceLedger 可记录证据，但工具结果到证据之间缺少标准提取器。

优化：

- 新增 `ToolEvidenceExtractor`。
- 将 `run_shell`、`write_file`、artifact 相关工具结果提取为可写入 ledger 的 claim。
- 支持测试命令识别。

收益：

- 为最终防伪 gate 提供类型化证据。
- 降低适配器和业务层重复实现证据提取逻辑。

### O3.3 Trajectory Hook Installer

现状：TrajectoryRecorder 能手动记录，但还没有一键挂到 HookBus。

优化：

- 新增 `install_trajectory_hooks`。
- 捕获 agent/model/tool/quality/context/recovery/swarm 关键事件。
- 支持 JSONL 导出。

收益：

- E2E run 可复盘。
- 审计报告可以引用轨迹证据。

### O3.4 Scheduler Persistence

现状：Scheduler 能解析表达式，但 schedule 没有独立持久化记录。

优化：

- StateStore 增加 schedules 表。
- SchedulerStore 支持 create/get/list。
- 保存 loop_id、expression、next_run_at、status。

收益：

- Loop/Scheduler 从表达式工具变成可维护任务系统。

### O3.5 Adapter Health Check

现状：Aurora/Sophia adapter 能注册结构检查工具，但缺少统一健康检查接口。

优化：

- Adapter 增加 `health_check`。
- Aurora/Sophia 返回路径存在、关键文件存在、工具可注册数量。

收益：

- 用户可以快速判断 adapter 是否可用。
- 后续扩展业务工具前有基础健康门。

### O3.6 文档深化

现状：docs 已存在，但偏骨架。

优化：

- 补充第三轮新增模块文档。
- 更新测试策略和扩展指南。

收益：

- 项目达到更接近可交付状态。

## 验收标准

- 新增任务清单全部 DONE。
- 新增模块均有单元或集成测试。
- 全量测试通过。
- 编译检查通过。
- 网络测试在配置存在时真实运行，配置缺失时 skip。

