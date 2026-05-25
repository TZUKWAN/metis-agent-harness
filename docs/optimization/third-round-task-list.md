# Metis 第三轮优化任务清单

## T3.1 FinalizationGuard

状态：DONE

任务：

- 创建 `metis/runtime/finalization.py`。
- 实现 `FinalizationGuard`。
- AgentLoop final 前执行防伪 gate。
- 缺证据时返回 blocked。

测试：

- `tests/unit/test_finalization_guard.py`
- `tests/integration/test_agent_loop_finalization_guard.py`

## T3.2 ToolEvidenceExtractor

状态：DONE

任务：

- 创建 `metis/evidence/extractor.py`。
- 从 `ToolResult` 提取 command/write/test 证据。
- 支持 dict 和 dataclass 两种 tool result 输入。

测试：

- `tests/unit/test_evidence_extractor.py`

## T3.3 Trajectory Hook Installer

状态：DONE

任务：

- 创建 `metis/telemetry/hooks.py`。
- 实现 `install_trajectory_hooks`。
- 覆盖 agent/model/tool/context/recovery/swarm 关键事件。

测试：

- `tests/integration/test_trajectory_hooks.py`

## T3.4 Scheduler Persistence

状态：DONE

任务：

- StateStore 增加 schedules 表。
- `metis/loops/scheduler.py` 增加 `SchedulerStore`。
- 支持 create/get/list/update_next_run。

测试：

- `tests/unit/test_scheduler_store.py`

## T3.5 Adapter Health Check

状态：DONE

任务：

- Adapter base 增加 `health_check`。
- Aurora/Sophia Adapter 实现健康检查。

测试：

- `tests/unit/test_adapter_health.py`

## T3.6 文档和回归

状态：DONE

任务：

- 更新 docs。
- 更新第二轮审计报告的修复状态。
- 全量测试与编译。

测试：

- `python -m pytest -q`
- `python -m compileall -q metis`
