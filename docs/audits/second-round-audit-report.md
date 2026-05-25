# Metis Agent Harness 第二轮问题审计报告

审计时间：2026-05-25

审计范围：

- 首轮任务清单完成状态：`Metis-Agent-Harness-详细任务清单.md`
- 当前源码：`metis/**`
- 当前测试：`tests/**`
- 当前文档：`docs/**`
- 当前验证命令：
  - `python -m pytest -q`
  - `python -m compileall -q metis`

## 当前基线

- 任务清单状态：`DONE=73`，`TODO=0`
- 全量测试基线：`87 passed, 2 skipped`
- 编译检查：通过
- 真实 OpenAI-compatible endpoint smoke：上一轮通过，未在源码或文档中保存真实 API key

## 审计结论

首轮实现已经具备可运行 harness 主干，但第二轮审计发现 3 个必须修复的问题。它们不会阻止现有测试通过，但会影响真实小模型运行质量和“防伪完成”目标。

## 问题 A-001：ToolRouter 阶段分类与内置工具分类不一致

严重级别：High

证据：

- `metis/tools/tool_router.py` 的阶段分类使用 `filesystem`。
- `metis/tools/builtin.py` 中 `read_file` 和 `write_file` 的 category 是 `files`。
- 当 AgentLoop 未传入 `allowed_tools` 时，`ToolRouter` 会按 stage category 过滤，导致内置文件工具不会进入工具 schema。

影响：

- 小模型默认 execute/explore 阶段可能看不到核心文件工具。
- 这会削弱架构报告、修复任务、workspace 分析等真实任务能力。

修复要求：

- 统一 category 命名，至少让 router 同时兼容 `files` 和 `filesystem`。
- 增加回归测试：无 `allowed_tools` 时 small profile 能路由出内置 `read_file`/`write_file`。

## 问题 A-002：严格输出修复失败后 AgentLoop 仍返回 `final`

严重级别：High

证据：

- `metis/runtime/loop.py` 在无 tool_calls 且 strict output 开启时调用 `_repair_final_output`。
- `_repair_final_output` 返回 `None` 时，当前逻辑仍构造 `AgentRunResult(status="final")`。

影响：

- 小模型最终输出违反 JSON contract 且修复失败时，运行状态仍可能被标记为 final。
- 上层如果只检查 status，可能误判任务完成。

修复要求：

- strict output repair 失败时返回 `status="blocked"` 或等价失败状态。
- 增加集成测试：small profile 下两次非法 final 输出必须 blocked，不能 final。

## 问题 A-003：`no_fake_completion` 对“已测试/已运行”证据判断过宽

严重级别：Critical

证据：

- `metis/quality/gates.py` 当前逻辑是：有 artifact、evidence 或任意 tool_results 即认为 completion claim 有证据。
- 任务清单 C2 明确要求：
  - 工具运行声明必须查询 tool_calls。
  - 测试声明必须查询 command result。
  - 没证据时最终回答必须披露未完成或 blocked。

影响：

- 模型声称“已测试”，但只有 `read_file` 结果时也可能通过。
- 这直接削弱“不能虚假完成”的核心目标。

修复要求：

- 将完成声明拆分为类型化证据：
  - `已生成` 需要 artifact 或 artifact evidence。
  - `已运行` 需要 tool result 或 command evidence。
  - `已测试` 需要 `run_shell`/command 且内容包含测试命令或通过状态。
  - `已上传` 需要 upload/git/github 相关证据。
  - `已修复` 需要 write/edit 工具结果或 artifact/evidence。
- 增加单元测试覆盖误报场景。

## 未列为问题但需后续优化

- Scheduler 当前只做表达式解析和下一次触发时间计算，尚未把 schedule 持久化为独立表。任务清单中写了“持久化 schedule”，当前实现可作为轻量版本，但第三轮优化应补齐。
- Adapter 当前是安全的结构检查工具，没有深度复用 Aurora/Sophia 工具链。这个选择符合“不要迁移业务主循环”，但后续可以增加可选 tool wrapping。
- 文档目前可维护但偏骨架化。第三轮优化应扩展 module spec、运行手册和真实案例。

## 修复验证计划

1. 增加 failing tests 覆盖 A-001、A-002、A-003。
2. 修复源码。
3. 执行：
   - `python -m pytest -q`
   - `python -m compileall -q metis`
4. 如果环境变量存在，执行：
   - `python -m pytest -q -m network`

## 修复状态

修复完成时间：2026-05-25

- A-001 已修复：`ToolRouter` 阶段分类兼容 `files`，新增无 allowed filter 的内置文件工具路由测试。
- A-002 已修复：strict final output 修复失败时 `AgentLoop` 返回 `blocked`，新增集成测试。
- A-003 已修复：`no_fake_completion` 改为类型化证据检查，新增“只有 read_file 不能证明已测试”的回归测试。

修复后验证：

- 定向测试：通过。
- 全量测试：`91 passed, 2 skipped`。
- 第三轮优化后全量测试：`100 passed, 2 skipped`。
- 编译检查：通过。
