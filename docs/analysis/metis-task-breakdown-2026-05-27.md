# Metis 完善方案 — 最高细粒度任务清单

**版本**: v0.2.0  
**日期**: 2026-05-27  
**生成依据**: `docs/analysis/metis-gap-analysis-2026-05-27.md`

---

## 阅读指南

- **每个任务都是最小可执行单元**，不可再拆分
- **验收标准**: 任务完成后必须满足的具体、可验证的条件
- **依赖**: 必须先完成的其他任务（如无依赖则留空）
- **工作量**: 人天（1人全职1天）
- **文件路径**: 该任务主要涉及的新建或修改文件

---

## Phase 1: 可用性加固（2 周 / 10 个工作日）

### 功能 1: HITL Web 审批界面（3.5 天）

**目标**: 让 Web UI 用户可以查看和审批 pending 的工具调用请求，解决 HITL 在 Web 模式下写操作卡住的问题。

#### 1.1 后端 API 设计

| ID | 任务名称 | 描述 | 文件路径 | 工作量 | 依赖 | 验收标准 |
|----|---------|------|---------|--------|------|---------|
| 1.1.1 | 定义 HITL API 序列化模型 | 创建 `HitlPendingResponse`、`HitlActionRequest`、`HitlHistoryResponse` Pydantic 模型，用于 API 输入输出校验 | `metis/app/hitl_schemas.py` | 0.25d | - | 模型包含所有必要字段，通过 mypy 类型检查 |
| 1.1.2 | 创建 HITL API Router | 新建 FastAPI APIRouter，注册到 web.py 的 app 实例，前缀 `/api/v1/hitl` | `metis/app/hitl_api.py` | 0.25d | 1.1.1 | Router 注册成功，`/api/v1/hitl` 前缀生效 |
| 1.1.3 | 实现 GET /hitl/pending | 返回当前所有 `ApprovalStatus.PENDING` 的审批请求列表，按创建时间倒序 | `metis/app/hitl_api.py` | 0.25d | 1.1.2 | 返回列表格式正确，空列表时返回 `[]` |
| 1.1.4 | 实现 POST /hitl/{request_id}/approve | 根据 request_id 找到 pending 请求，状态改为 APPROVED，触发 asyncio.Event 通知等待中的 loop | `metis/app/hitl_api.py` | 0.25d | 1.1.3 | 审批后请求状态变为 APPROVED，404 时返回合理错误 |
| 1.1.5 | 实现 POST /hitl/{request_id}/deny | 根据 request_id 找到 pending 请求，状态改为 DENIED，触发 asyncio.Event 通知等待中的 loop | `metis/app/hitl_api.py` | 0.25d | 1.1.4 | 拒绝后请求状态变为 DENIED，返回 block_reason |
| 1.1.6 | 实现 GET /hitl/history | 返回最近 N 条（默认 50）审批记录，支持按状态过滤（approved/denied/pending/timeout） | `metis/app/hitl_api.py` | 0.25d | 1.1.5 | 支持 `?status=` 查询参数，分页可选 |
| 1.1.7 | 实现 WebSocket /hitl/stream | 当新的 pending 请求产生时，通过 WebSocket 推送给所有连接的前端客户端 | `metis/app/hitl_api.py` | 0.5d | 1.1.3 | 新 pending 产生时，前端 1 秒内收到推送 |
| 1.1.8 | HITL API 集成测试 | 编写 pytest 测试：创建 pending 请求、审批、拒绝、历史查询、WebSocket 推送 | `tests/unit/test_hitl_api.py` | 0.5d | 1.1.7 | 所有测试用例通过 |

#### 1.2 HITL Loop 集成改造

| ID | 任务名称 | 描述 | 文件路径 | 工作量 | 依赖 | 验收标准 |
|----|---------|------|---------|--------|------|---------|
| 1.2.1 | 改造 ApprovalStore 支持 asyncio.Event | 在 `ApprovalStore` 中增加 `wait_for(request_id)` 方法，使用 `asyncio.Event` 让调用者异步等待审批结果 | `metis/hitl/store.py` | 0.25d | - | `wait_for` 可以在审批状态变更时被唤醒 |
| 1.2.2 | 改造 HITLApprover.request_approval 支持 Web 阻塞模式 | 在非交互式模式下，写操作 pending 后调用 `store.wait_for()` 阻塞等待，而非立即返回 | `metis/hitl/core.py` | 0.25d | 1.2.1 | Web 模式下写操作会阻塞，直到被审批或超时 |
| 1.2.3 | 实现审批超时机制 | `wait_for` 支持 `timeout_seconds` 配置，超时后状态变为 TIMEOUT，loop 继续执行（视为拒绝） | `metis/hitl/core.py` | 0.25d | 1.2.2 | 超时后状态正确变为 TIMEOUT，loop 收到 block_reason |
| 1.2.4 | 在 AgentLoop 中处理 HITL 阻塞异常 | 当 HITL 拒绝或超时时，loop 正确处理 `ctx["blocked"]`，记录轨迹事件，继续下一轮 | `metis/runtime/loop.py` | 0.25d | 1.2.3 | 拒绝/超时不导致 loop 崩溃，trace event 正确记录 |
| 1.2.5 | HITL Loop 集成测试 | 测试：开启 HITL 的 agent 执行写操作 → pending → 审批通过 → 工具执行 → 审批拒绝 → 工具被 block | `tests/unit/test_hitl_loop.py` | 0.5d | 1.2.4 | 完整流程测试通过 |

#### 1.3 前端审批面板

| ID | 任务名称 | 描述 | 文件路径 | 工作量 | 依赖 | 验收标准 |
|----|---------|------|---------|--------|------|---------|
| 1.3.1 | 设计审批面板 HTML 结构 | 在 `index.html` 中添加审批面板 DOM：铃铛图标按钮、下拉面板、pending 列表、历史记录入口 | `metis/app/web_assets/templates/index.html` | 0.25d | - | DOM 结构语义清晰，a11y 友好 |
| 1.3.2 | 实现审批面板 CSS 样式 | 面板悬浮在右上角，pending 项有边框区分，Approve 绿色按钮，Deny 红色按钮，适配暗色主题 | `metis/app/web_assets/static/style.css` | 0.25d | 1.3.1 | 与现有暗色主题视觉一致，hover 状态清晰 |
| 1.3.3 | 实现铃铛图标与红点通知 | 页面加载时轮询 `/hitl/pending`，pending 数量 > 0 时显示红点数字，点击展开面板 | `metis/app/web_assets/static/app.js` | 0.25d | 1.1.3 | 红点数字准确，点击展开/收起正常 |
| 1.3.4 | 实现 pending 列表渲染 | 从 API 获取 pending 列表，渲染每项的工具名、参数摘要、风险级别（根据 rule 名称判断），Approve/Deny 按钮 | `metis/app/web_assets/static/app.js` | 0.25d | 1.3.3 | 列表渲染正确，参数过长时截断 |
| 1.3.5 | 实现 Approve/Deny 交互 | 点击按钮调用对应 API，成功后从列表移除该项，更新红点计数，显示 toast 通知 | `metis/app/web_assets/static/app.js` | 0.25d | 1.3.4 | API 调用成功，UI 即时反馈，错误时显示 alert |
| 1.3.6 | 实现审批历史页面/弹窗 | 点击"历史记录"显示已审批/已拒绝的请求列表，包含时间、工具名、结果、操作人 | `metis/app/web_assets/static/app.js` | 0.25d | 1.1.6 | 历史记录正确显示，空状态时友好提示 |
| 1.3.7 | 实现 WebSocket 实时推送 | 连接 `/ws/hitl`，收到新 pending 推送时即时更新铃铛红点，无需轮询 | `metis/app/web_assets/static/app.js` | 0.25d | 1.1.7 | WebSocket 断线自动重连，收到推送即时更新 |
| 1.3.8 | HITL 前端端到端测试 | 使用 Playwright 测试：执行写操作 → 铃铛红点出现 → 点击审批 → 操作成功 → 红点消失 | 测试脚本 | 0.5d | 1.3.7 | Playwright 测试通过 |

**功能 1 总计**: 3.5 天

---

### 功能 2: 配置热重载与 Settings 入口（1.5 天）

**目标**: Web UI 和 TUI 都支持随时修改 provider 配置，修改后立即生效无需重启。

#### 2.1 后端热重载机制

| ID | 任务名称 | 描述 | 文件路径 | 工作量 | 依赖 | 验收标准 |
|----|---------|------|---------|--------|------|---------|
| 2.1.1 | 实现 provider 热重建函数 | 封装 `_reload_provider(app)`：关闭旧 provider 的 http client，调用 `build_provider()` 重建，更新 `app.state.provider` | `metis/app/web.py` | 0.25d | - | 重建后新 provider 可以正常调用 API |
| 2.1.2 | 实现配置保存 + 热重载原子操作 | 在 `/api/v1/setup` PATCH 中，先保存 `metis-agent.json`，再调用 `_reload_provider()`，任一失败则回滚 | `metis/app/web.py` | 0.25d | 2.1.1 | 保存和热重载原子性保证，失败时配置不丢失 |
| 2.1.3 | 增加配置变更 HookBus 事件 | 热重载成功后，通过 HookBus 发送 `config.changed` 事件，携带变更字段列表 | `metis/app/web.py` | 0.25d | 2.1.2 | WebSocket 客户端收到事件，状态显示更新 |
| 2.1.4 | 后端集成测试 | 测试：修改 model → 保存 → provider 重建 → 新 model 生效 → 回滚场景 | `tests/unit/test_config_reload.py` | 0.25d | 2.1.3 | 测试通过 |

#### 2.2 Web UI Settings 入口

| ID | 任务名称 | 描述 | 文件路径 | 工作量 | 依赖 | 验收标准 |
|----|---------|------|---------|--------|------|---------|
| 2.2.1 | 在 chat header 添加 Settings 齿轮图标 | 在 `chatHeader` 右侧增加齿轮按钮，点击打开 Settings 模态框 | `metis/app/web_assets/templates/index.html` | 0.25d | - | 齿轮按钮可见，点击打开模态框 |
| 2.2.2 | 实现 Settings 模态框 DOM | 模态框包含字段：Model（文本输入）、Base URL（文本输入）、API Key（password 输入，留空保持当前）、System Prompt（textarea） | `metis/app/web_assets/templates/index.html` | 0.25d | 2.2.1 | 字段与 setup wizard 一致，有 placeholder 提示 |
| 2.2.3 | 实现 Settings 模态框样式 | 与 create agent modal 样式一致，表单字段布局整齐，保存/取消按钮 | `metis/app/web_assets/static/style.css` | 0.25d | 2.2.2 | 视觉与现有模态框一致 |
| 2.2.4 | 实现 Settings 数据加载 | 打开模态框时，调用 `/api/v1/config` 获取当前配置，填充到表单字段 | `metis/app/web_assets/static/app.js` | 0.25d | 2.2.3 | 表单正确显示当前配置值 |
| 2.2.5 | 实现 Settings 保存逻辑 | 点击 Save 调用 PATCH `/api/v1/setup`，显示 loading 状态，成功后关闭模态框并 toast 提示，失败时显示错误 | `metis/app/web_assets/static/app.js` | 0.25d | 2.2.4 | API 调用成功，UI 即时反馈 |
| 2.2.6 | Settings 前端端到端测试 | Playwright 测试：打开 Settings → 修改 model → 保存 → 验证配置已更新 | 测试脚本 | 0.25d | 2.2.5 | 测试通过 |

#### 2.3 TUI Settings 入口

| ID | 任务名称 | 描述 | 文件路径 | 工作量 | 依赖 | 验收标准 |
|----|---------|------|---------|--------|------|---------|
| 2.3.1 | 在 TUI 主界面添加 Settings 快捷键 | 按 `Ctrl+S` 或输入 `/settings` 触发设置向导，重新配置后可选择是否热重载 | `metis/app/tui.py` | 0.25d | - | 快捷键响应正常，设置后 provider 重建成功 |

**功能 2 总计**: 1.5 天

---

### 功能 3: Swarm Coordinator 智能编排（3.5 天）

**目标**: 用结构化 JSON 替代脆弱的字符串前缀匹配，实现智能任务分配和 Agent 间上下文共享。

#### 3.1 结构化任务分解

| ID | 任务名称 | 描述 | 文件路径 | 工作量 | 依赖 | 验收标准 |
|----|---------|------|---------|--------|------|---------|
| 3.1.1 | 定义 TaskDecomposition Pydantic 模型 | `TaskAssignment`（agent_id, agent_name, task, priority）、`TaskDecomposition`（tasks, dependencies） | `metis/swarm/schemas.py` | 0.25d | - | 模型通过 mypy 检查，支持 dependencies DAG |
| 3.1.2 | 改造 Coordinator prompt 要求 JSON 输出 | 修改 coordinator prompt，明确要求输出 JSON 格式的任务分解，包含示例 | `metis/swarm/hub.py` | 0.25d | - | prompt 中包含 JSON schema 示例和字段说明 |
| 3.1.3 | 实现 JSON 解析 + fallback 机制 | 先尝试解析 JSON，失败时回退到原有的字符串前缀匹配，解析器修复（利用现有 parser repair） | `metis/swarm/hub.py` | 0.5d | 3.1.2 | JSON 解析成功率 > 90%，失败时 fallback 正常工作 |
| 3.1.4 | 实现任务依赖图（DAG）构建 | 根据 `dependencies` 构建有向无环图，检测循环依赖并报错 | `metis/swarm/hub.py` | 0.25d | 3.1.1 | DAG 构建正确，循环依赖时返回 400 错误 |
| 3.1.5 | 实现拓扑排序执行 | 按拓扑排序顺序执行任务，无依赖的任务并行执行，有依赖的串行等待 | `metis/swarm/hub.py` | 0.5d | 3.1.4 | 执行顺序符合依赖关系，并行任务用 asyncio.gather |
| 3.1.6 | Coordinator 结构化编排测试 | 测试：正常 JSON 分解、JSON 解析失败 fallback、循环依赖检测、拓扑排序正确性 | `tests/unit/test_swarm_coordinator.py` | 0.5d | 3.1.5 | 所有测试通过 |

#### 3.2 Agent 能力描述匹配

| ID | 任务名称 | 描述 | 文件路径 | 工作量 | 依赖 | 验收标准 |
|----|---------|------|---------|--------|------|---------|
| 3.2.1 | 在 AgentEntry 增加 capabilities 字段 | `capabilities: list[str]`，支持标签如 "code", "writing", "analysis", "search" | `metis/swarm/models.py` | 0.25d | - | 模型变更正确，to_dict/from_dict 同步更新 |
| 3.2.2 | 在创建/编辑 Agent 时支持设置 capabilities | Web UI 的 create/edit modal 增加 capabilities 多选输入（checkbox 或 tag input） | `metis/app/web_assets_swarm/templates/index.html` + `app.js` | 0.25d | 3.2.1 | 可以设置 capabilities，保存到 registry |
| 3.2.3 | 在 Coordinator prompt 中注入 Agent 能力信息 | coordinator prompt 包含每个 worker 的 capabilities，让 coordinator 按能力匹配任务 | `metis/swarm/hub.py` | 0.25d | 3.2.1 | prompt 中包含 capabilities 信息 |
| 3.2.4 | 在 TaskAssignment 中增加 capability_match 分数 | 如果 coordinator 未指定 agent_id，按 task 描述与 agent capabilities 的语义匹配度自动分配 | `metis/swarm/hub.py` | 0.5d | 3.2.3 | 未指定 agent_id 时自动匹配，匹配逻辑合理 |

#### 3.3 Agent 间上下文共享

| ID | 任务名称 | 描述 | 文件路径 | 工作量 | 依赖 | 验收标准 |
|----|---------|------|---------|--------|------|---------|
| 3.3.1 | 实现 SharedContext 类 | 简单的 key-value 存储，支持 worker 写入和 coordinator 读取，线程安全 | `metis/swarm/context.py` | 0.25d | - | 并发读写安全，数据正确传递 |
| 3.3.2 | 在 worker 执行后写入共享上下文 | 每个 worker 执行完毕后，将关键结果写入 SharedContext（key=agent_id） | `metis/swarm/hub.py` | 0.25d | 3.3.1 | worker 结果正确存入共享上下文 |
| 3.3.3 | 在 coordinator synthesis 时注入共享上下文 | coordinator 综合阶段，除了 worker_results 外，还能读取 SharedContext 中的额外信息 | `metis/swarm/hub.py` | 0.25d | 3.3.2 | synthesis prompt 包含共享上下文 |

**功能 3 总计**: 3.5 天

---

### 功能 4: Plugin 示例与文档（1.5 天）

**目标**: 让开发者可以在 5 分钟内写出第一个 Metis 插件。

#### 4.1 官方示例插件

| ID | 任务名称 | 描述 | 文件路径 | 工作量 | 依赖 | 验收标准 |
|----|---------|------|---------|--------|------|---------|
| 4.1.1 | 创建 weather-tool 示例插件 | 插件注册一个 `get_weather(city: str)` 工具，调用公开天气 API，返回温度和天气状况 | `examples/plugins/weather-tool/` | 0.25d | - | 插件可被 `metis plugin inspect` 正确验证 |
| 4.1.2 | 创建 custom-gate 示例插件 | 插件注册一个自定义质量门 `no_hardcoded_paths`，检查产物中是否包含硬编码绝对路径 | `examples/plugins/custom-gate/` | 0.25d | - | 质量门在 eval 中被正确调用 |
| 4.1.3 | 创建 prompt-fragment 示例插件 | 插件注入一个 prompt 片段，要求 agent 在回复中始终使用中文 | `examples/plugins/prompt-fragment/` | 0.25d | - | prompt 片段正确注入到 prompt stack |
| 4.1.4 | 验证所有示例插件可加载 | 使用 `PluginManager.load_dir()` 加载每个示例，验证无错误 | 测试脚本 | 0.25d | 4.1.1~4.1.3 | 所有示例加载成功，register 被调用 |

#### 4.2 插件开发文档

| ID | 任务名称 | 描述 | 文件路径 | 工作量 | 依赖 | 验收标准 |
|----|---------|------|---------|--------|------|---------|
| 4.2.1 | 编写插件开发文档 | `docs/plugin-development.md`，包含：manifest 字段详解、register 函数签名、PluginContext API、调试技巧、打包分发 | `docs/plugin-development.md` | 0.25d | - | 文档覆盖从创建到分发的完整流程 |
| 4.2.2 | 编写插件开发快速开始 | 5 分钟快速开始指南，从 `metis plugin init` 到验证加载 | `docs/plugin-quickstart.md` | 0.25d | 4.2.1 | 完全按文档操作 5 分钟内可跑通 |

#### 4.3 Plugin 初始化 CLI

| ID | 任务名称 | 描述 | 文件路径 | 工作量 | 依赖 | 验收标准 |
|----|---------|------|---------|--------|------|---------|
| 4.3.1 | 实现 `metis plugin init` 命令 | 新增 CLI 子命令，根据模板生成插件目录结构（manifest.json、plugin.py、README.md） | `metis/adapters/cli.py` | 0.25d | - | 命令可用，生成的插件可被 inspect 验证 |

**功能 4 总计**: 1.5 天

---

## Phase 2: 能力扩展（3 周 / 15 个工作日）

### 功能 5: Agent 长期记忆（向量存储）（3.5 天）

**目标**: Agent 可以跨会话语义检索历史记忆，记住用户偏好和项目背景。

#### 5.1 向量存储基础设施

| ID | 任务名称 | 描述 | 文件路径 | 工作量 | 依赖 | 验收标准 |
|----|---------|------|---------|--------|------|---------|
| 5.1.1 | 集成 chromadb 作为可选依赖 | 在 `pyproject.toml` 的 extras 中增加 `[memory]` 组，包含 `chromadb` | `pyproject.toml` | 0.25d | - | `pip install "metis-agent-harness[memory]"` 可安装 |
| 5.1.2 | 实现 MemoryStore 抽象接口 | 定义 `MemoryStore` 基类：`add(text, metadata)`、`query(text, n_results)`、`delete(id)`、`compact()` | `metis/memory/base.py` | 0.25d | - | 接口清晰，适合 mock 测试 |
| 5.1.3 | 实现 ChromaMemoryStore | 基于 chromadb 的实现，每个 agent 独立 collection，持久化到 `~/.metis/memory/{agent_id}/` | `metis/memory/chroma.py` | 0.5d | 5.1.2 | 增删查改正常，数据持久化到磁盘 |
| 5.1.4 | 实现 FileMemoryStore（fallback） | 无 chromadb 时的 fallback，基于文件和简单文本搜索 | `metis/memory/file.py` | 0.25d | 5.1.2 | 无 chromadb 时自动降级，功能正常 |
| 5.1.5 | 实现 MemoryStore 工厂 | `build_memory_store(agent_id)`，优先返回 ChromaMemoryStore，无依赖时返回 FileMemoryStore | `metis/memory/factory.py` | 0.25d | 5.1.3, 5.1.4 | 工厂选择逻辑正确 |
| 5.1.6 | MemoryStore 单元测试 | 测试 add/query/delete/compact 全部操作，验证语义检索效果 | `tests/unit/test_memory_store.py` | 0.5d | 5.1.5 | 测试通过，语义检索召回率 > 80% |

#### 5.2 记忆自动捕获

| ID | 任务名称 | 描述 | 文件路径 | 工作量 | 依赖 | 验收标准 |
|----|---------|------|---------|--------|------|---------|
| 5.2.1 | 实现 MemoryExtractor | 在 AgentLoop finalization 后，调用 LLM 提取关键记忆（用户偏好、重要决策、项目背景），生成记忆摘要 | `metis/memory/extractor.py` | 0.5d | - | 提取的记忆质量合理，不过度冗余 |
| 5.2.2 | 将 MemoryExtractor 集成到 AgentLoop | 在 loop 的 `finalize` 阶段，如果配置了 memory，调用 extractor 并将结果写入 MemoryStore | `metis/runtime/loop.py` | 0.25d | 5.2.1 | 每轮结束后自动提取记忆，不阻塞主流程 |
| 5.2.3 | 支持手动记忆管理 API | 后端 API：`POST /api/v1/memory`（添加记忆）、`GET /api/v1/memory`（查询记忆）、`DELETE /api/v1/memory/{id}` | `metis/app/web.py` | 0.25d | 5.1.5 | API 正常，支持语义检索 |

#### 5.3 记忆检索与注入

| ID | 任务名称 | 描述 | 文件路径 | 工作量 | 依赖 | 验收标准 |
|----|---------|------|---------|--------|------|---------|
| 5.3.1 | 改造 recall_memory 工具为语义检索 | 工具实现改为调用 `MemoryStore.query()`，返回最相关的 N 条记忆 | `metis/memory/tool.py` | 0.25d | 5.1.5 | 语义检索返回相关记忆，按相似度排序 |
| 5.3.2 | 实现自动记忆注入 prompt | 在每轮用户输入后，自动查询 MemoryStore，将相关记忆注入到 system prompt 或 user message 前 | `metis/memory/injector.py` | 0.5d | 5.3.1 | 记忆注入不干扰正常对话，相关性阈值可配置 |
| 5.3.3 | 实现记忆整理（compact）| 定期合并相似记忆、删除低重要性记忆、生成高层次摘要 | `metis/memory/compact.py` | 0.5d | 5.1.5 | 整理后记忆数量减少，质量提升 |
| 5.3.4 | Web UI 记忆管理面板 | 在 Swarm Hub 或 Web UI 中增加 "Memory" 标签页，显示记忆列表，支持搜索、删除、手动添加 | `metis/app/web_assets/` | 0.5d | 5.2.3 | 面板可用，搜索准确 |

**功能 5 总计**: 3.5 天

---

### 功能 6: Token 预算硬截断与成本估算（2.5 天）

**目标**: 防止长会话无限制消耗 token，提供成本预估和告警。

#### 6.1 Token 预算配置与检查

| ID | 任务名称 | 描述 | 文件路径 | 工作量 | 依赖 | 验收标准 |
|----|---------|------|---------|--------|------|---------|
| 6.1.1 | 在 manifest 中增加 token_budget 配置 | `token_budget: {max_per_session, max_per_turn, warn_threshold}` | `metis/app/manifest.py` | 0.25d | - | 配置项可选，不影响向后兼容 |
| 6.1.2 | 在 AgentLoop 中实现 token 用量跟踪 | 每轮结束后累加 `usage.prompt_tokens + usage.completion_tokens`，更新会话累计用量 | `metis/runtime/loop.py` | 0.25d | - | 累计用量准确，存入 SQLite token_usage 表 |
| 6.1.3 | 实现预算警告机制 | 累计用量超过 `warn_threshold` 比例时，在 prompt 中注入预算警告文本 | `metis/runtime/loop.py` | 0.25d | 6.1.2 | 警告文本正确注入，不影响正常回复 |
| 6.1.4 | 实现预算硬截断 | 累计用量超过 `max_per_session` 时，优雅终止 loop，返回总结性回复（"Token 预算已用尽，这是当前进展的总结..."） | `metis/runtime/loop.py` | 0.25d | 6.1.3 | 超预算时不崩溃，返回有意义的总结 |
| 6.1.5 | 实现单轮预算检查 | 单轮用量超过 `max_per_turn` 时，截断输出或减少工具调用 | `metis/runtime/loop.py` | 0.25d | 6.1.4 | 单轮超限有合理降级策略 |
| 6.1.6 | 预算 HookBus 事件 | 发送 `budget.warning` 和 `budget.exceeded` 事件，携带当前用量和预算 | `metis/runtime/loop.py` | 0.25d | 6.1.4 | 事件正确发送，WebSocket 可接收 |

#### 6.2 成本估算

| ID | 任务名称 | 描述 | 文件路径 | 工作量 | 依赖 | 验收标准 |
|----|---------|------|---------|--------|------|---------|
| 6.2.1 | 实现模型定价表 | 内置常见模型的定价（$/1M tokens），支持用户自定义覆盖 | `metis/providers/pricing.py` | 0.25d | - | 覆盖主流模型（GPT-4o、Claude、GLM 等） |
| 6.2.2 | 实现实时成本计算 | 根据用量和定价表实时计算估算成本，显示在 TUI/Web UI | `metis/app/runtime.py` | 0.25d | 6.2.1 | 成本计算准确（与官方定价一致） |
| 6.2.3 | 会话成本报告 | 会话结束时输出实际用量和成本，保存到 SQLite | `metis/runtime/loop.py` | 0.25d | 6.2.2 | 会话结束后可查询成本报告 |
| 6.2.4 | Web UI 预算显示 | 在 chat header 或状态栏显示当前会话用量和预算百分比 | `metis/app/web_assets/static/app.js` | 0.25d | 6.2.2 | 显示实时，超阈值变色警告 |
| 6.2.5 | Token 预算集成测试 | 测试：设置低预算 → 执行多轮 → 验证警告触发 → 验证硬截断 → 验证成本计算 | `tests/unit/test_token_budget.py` | 0.5d | 6.1.6, 6.2.3 | 测试通过 |

**功能 6 总计**: 2.5 天

---

### 功能 7: Artifact 产物生命周期管理（3 天）

**目标**: Agent 生成的产物有版本控制、审核流程、发布状态。

#### 7.1 Artifact 状态机与版本控制

| ID | 任务名称 | 描述 | 文件路径 | 工作量 | 依赖 | 验收标准 |
|----|---------|------|---------|--------|------|---------|
| 7.1.1 | 定义 ArtifactStatus 枚举和 Artifact 模型 | `ArtifactStatus`: draft/review/approved/published/deleted/rejected/deprecated；`Artifact` dataclass | `metis/artifacts/models.py` | 0.25d | - | 模型完整，支持版本号 |
| 7.1.2 | 实现 ArtifactStore | CRUD 操作，版本控制（每次保存创建新版本），diff 对比，持久化到 `~/.metis/artifacts/{agent_id}/` | `metis/artifacts/store.py` | 0.5d | 7.1.1 | 版本递增正确，diff 准确 |
| 7.1.3 | 在 AgentLoop 中集成 Artifact 捕获 | 当工具生成文件时，自动注册为 Artifact（初始状态 draft），记录来源工具调用 ID | `metis/runtime/loop.py` | 0.25d | 7.1.2 | 文件生成后 Artifact 正确注册 |
| 7.1.4 | 实现 Artifact 审批 API | `POST /api/v1/artifacts/{id}/review`（提交审核）、`POST /api/v1/artifacts/{id}/approve`（审批通过）、`POST /api/v1/artifacts/{id}/reject`（拒绝） | `metis/app/web.py` | 0.25d | 7.1.2 | 状态转换正确，拒绝时记录原因 |

#### 7.2 Artifact 依赖图与可视化

| ID | 任务名称 | 描述 | 文件路径 | 工作量 | 依赖 | 验收标准 |
|----|---------|------|---------|--------|------|---------|
| 7.2.1 | 实现 Artifact 依赖追踪 | 记录 artifact 之间的依赖关系（如 report.md 依赖 data.csv 和 chart.png） | `metis/artifacts/models.py` | 0.25d | 7.1.1 | 依赖关系正确存储 |
| 7.2.2 | 实现依赖图生成 | 根据依赖关系生成 Mermaid 图或 JSON 图数据 | `metis/artifacts/graph.py` | 0.25d | 7.2.1 | 图结构正确，无循环依赖时通过 |
| 7.2.3 | Swarm Hub Artifact 面板 | 在 Agent 详情页增加 "Artifacts" 标签，显示产物列表、版本历史、状态、依赖图 | `metis/app/web_assets_swarm/` | 0.5d | 7.1.4, 7.2.2 | 面板可用，依赖图可渲染 |
| 7.2.4 | Artifact 下载与 diff | 支持下载任意版本的 artifact，支持两个版本之间的 diff 对比 | `metis/app/web.py` + 前端 | 0.25d | 7.1.4 | 下载正确，diff 显示准确 |

**功能 7 总计**: 3 天

---

### 功能 8: 计划/目标显式驱动（4 天）

**目标**: Agent 的执行由显式的目标树驱动，而非隐式的多轮对话。

#### 8.1 目标树模型与存储

| ID | 任务名称 | 描述 | 文件路径 | 工作量 | 依赖 | 验收标准 |
|----|---------|------|---------|--------|------|---------|
| 8.1.1 | 定义 Goal/Step 数据模型 | `GoalStatus`: pending/active/completed/failed；`Goal`: id, description, status, parent_id, priority, steps；`Step`: id, description, status, tool_calls, evidence_refs | `metis/planning/goals.py` | 0.25d | - | 支持父子关系，可构建树结构 |
| 8.1.2 | 在 SQLite 中创建 goals/plans/steps 表的操作方法 | `SQLiteStateStore` 中增加 `create_goal`、`update_goal_status`、`get_goal_tree`、`create_step`、`complete_step` | `metis/state/sqlite_store.py` | 0.5d | 8.1.1 | 表操作正确，支持事务 |
| 8.1.3 | 实现 GoalManager | 管理目标树：创建、分解、推进、完成、失败处理；支持子目标自动激活 | `metis/planning/manager.py` | 0.5d | 8.1.2 | 目标树推进逻辑正确 |

#### 8.2 Loop 集成

| ID | 任务名称 | 描述 | 文件路径 | 工作量 | 依赖 | 验收标准 |
|----|---------|------|---------|--------|------|---------|
| 8.2.1 | 在 AgentLoop 启动时生成初始目标树 | 用户输入后，调用 LLM 将任务分解为目标树，或从 manifest 加载预设目标 | `metis/runtime/loop.py` | 0.5d | 8.1.3 | 目标树生成合理，不遗漏关键步骤 |
| 8.2.2 | 每轮选择当前最优先目标 | 根据 priority 和依赖关系选择 active goal，将该 goal 的当前 step 注入 prompt | `metis/runtime/loop.py` | 0.5d | 8.2.1 | 选择逻辑正确，高优先级优先 |
| 8.2.3 | 目标完成检测与自动推进 | 当 step 完成时，标记状态，检查父 goal 是否所有 steps 完成，完成后激活下一个 goal | `metis/runtime/loop.py` | 0.5d | 8.2.2 | 自动推进正确，无遗漏 |
| 8.2.4 | 目标失败处理与重试 | goal 失败后，支持重试（修改策略）、跳过、或报告给用户 | `metis/runtime/loop.py` | 0.25d | 8.2.3 | 失败处理不导致 loop 崩溃 |

#### 8.3 可视化

| ID | 任务名称 | 描述 | 文件路径 | 工作量 | 依赖 | 验收标准 |
|----|---------|------|---------|--------|------|---------|
| 8.3.1 | Web UI Goals 面板 | 显示目标树（可折叠），当前 active goal 高亮，显示每个 step 的状态和进度 | `metis/app/web_assets/` | 0.5d | 8.2.1 | 树形渲染正确，状态颜色区分 |
| 8.3.2 | TUI Goals 面板 | 使用 Rich Tree 渲染目标树，实时更新进度 | `metis/app/tui.py` | 0.25d | 8.2.1 | 渲染正确，不干扰对话区域 |
| 8.3.3 | 支持手动调整目标 | Web/TUI 支持拖拽调整优先级、手动标记完成/失败、添加子目标 | `metis/app/web_assets/` + `tui.py` | 0.25d | 8.3.1, 8.3.2 | 手动调整同步到后端 |

**功能 8 总计**: 4 天

---

### 功能 9: Streaming 前端完整支持（1.5 天）

**目标**: Web UI 和 TUI 都支持逐 token 流式渲染，提升响应感知。

| ID | 任务名称 | 描述 | 文件路径 | 工作量 | 依赖 | 验收标准 |
|----|---------|------|---------|--------|------|---------|
| 9.1.1 | Web UI SSE 流式渲染 | 前端连接 `/api/v1/chat/sse`，逐 token 渲染到 msg-bubble，支持 Markdown 增量解析 | `metis/app/web_assets/static/app.js` | 0.5d | - | 文字逐字出现，流畅无闪烁 |
| 9.1.2 | Web UI 流式中断按钮 | 渲染过程中显示"停止生成"按钮，点击后发送中断请求，终止后端生成 | `metis/app/web_assets/static/app.js` | 0.25d | 9.1.1 | 中断响应及时，UI 状态恢复 |
| 9.1.3 | TUI 流式渲染 | 使用 Rich Live 逐 token 更新输出区域，支持 Markdown 渲染 | `metis/app/tui.py` | 0.5d | - | 逐 token 更新，不闪烁 |
| 9.1.4 | TUI 流式中断快捷键 | 按 `Ctrl+C` 或 `Esc` 中断生成 | `metis/app/tui.py` | 0.25d | 9.1.3 | 中断正常工作 |

**功能 9 总计**: 1.5 天

---

## Phase 3: 生态建设（2 周 / 10 个工作日）

### 功能 10: 多模态输入支持（4 天）

**目标**: Agent 可以接收图像、PDF、音频作为输入。

| ID | 任务名称 | 描述 | 文件路径 | 工作量 | 依赖 | 验收标准 |
|----|---------|------|---------|--------|------|---------|
| 10.1.1 | 扩展 Provider 消息格式支持多模态 | `OpenAICompatibleProvider.complete()` 支持 `image_url`、`audio`、`file` 类型的 message content | `metis/providers/openai_compat.py` | 0.5d | - | 多模态消息正确序列化为 OpenAI 格式 |
| 10.1.2 | 扩展 ProviderCapabilities 多模态标志 | 增加 `vision`、`audio_input`、`audio_output` 能力标志 | `metis/providers/base.py` | 0.25d | - | 能力检测正确 |
| 10.1.3 | 实现 read_image 工具 | 读取本地图像文件，返回 base64 编码，供 agent 分析 | `metis/tools/builtin.py` | 0.25d | - | 工具可用，返回正确 base64 |
| 10.1.4 | 实现 parse_pdf 工具 | 提取 PDF 文本内容，支持页码范围 | `metis/tools/builtin.py` | 0.25d | - | 文本提取准确 |
| 10.1.5 | Web UI 文件上传支持 | composer 区域支持拖拽/选择上传图像/PDF，上传后显示缩略图，发送时附带文件 | `metis/app/web_assets/` | 0.5d | - | 上传正常，缩略图显示正确 |
| 10.1.6 | TUI 文件路径输入支持 | 用户可以在消息中引用文件路径，TUI 自动读取并转换为多模态消息格式 | `metis/app/tui.py` | 0.25d | - | 路径引用正确转换 |
| 10.1.7 | 多模态端到端测试 | 测试：上传图像 → agent 分析图像内容 → 回复包含图像描述 | 测试脚本 | 0.5d | 10.1.5 | 端到端测试通过 |

**功能 10 总计**: 4 天

---

### 功能 11: Swarm Agent 间通信总线（2 天）

**目标**: Agent 之间可以通过消息总线实时共享状态和信息。

| ID | 任务名称 | 描述 | 文件路径 | 工作量 | 依赖 | 验收标准 |
|----|---------|------|---------|--------|------|---------|
| 11.1.1 | 实现 SwarmBus 消息总线 | 基于 asyncio Queue 的 pub/sub 总线，支持 topic 订阅、消息持久化（最近 100 条） | `metis/swarm/bus.py` | 0.5d | - | pub/sub 正常工作，消息不丢失 |
| 11.1.2 | 在 Swarm Hub 中集成 SwarmBus | 每个 Group 创建独立的 SwarmBus 实例，Agent 加入 group 时自动订阅该 bus | `metis/swarm/hub.py` | 0.25d | 11.1.1 | bus 生命周期与 group 绑定 |
| 11.1.3 | 实现 agent 广播工具 | 新增 `broadcast_to_swarm(topic, message)` 工具，Agent 可在执行过程中向总线广播中间结果 | `metis/tools/builtin.py` | 0.25d | 11.1.2 | 广播消息其他 agent 可接收 |
| 11.1.4 | Web UI 实时显示 SwarmBus 消息 | 在 group chat 中显示 agent 间的广播消息（如 "Agent A: 已完成数据分析，发现..."） | `metis/app/web_assets_swarm/` | 0.5d | 11.1.3 | 广播消息实时显示，不干扰用户对话 |
| 11.1.5 | SwarmBus 测试 | 测试：多个 agent 订阅同一 topic → 广播消息 → 所有订阅者收到 | `tests/unit/test_swarm_bus.py` | 0.5d | 11.1.1 | 测试通过 |

**功能 11 总计**: 2 天

---

### 功能 12: 跨端会话同步（1.5 天）

**目标**: TUI 和 Web 可以共享同一个会话，切换界面后继续对话。

| ID | 任务名称 | 描述 | 文件路径 | 工作量 | 依赖 | 验收标准 |
|----|---------|------|---------|--------|------|---------|
| 12.1.1 | 统一会话序列化格式 | 定义 `SessionSnapshot` 模型，包含 messages、goals、token_usage、metadata | `metis/state/session_snapshot.py` | 0.25d | - | 格式版本化，向后兼容 |
| 12.1.2 | 实现会话导入/导出 API | `POST /api/v1/sessions/{id}/export` 导出快照，`POST /api/v1/sessions/import` 导入快照 | `metis/app/web.py` | 0.25d | 12.1.1 | 导入导出正确，数据不丢失 |
| 12.1.3 | TUI 支持指定 session ID 恢复 | `metis tui --session-id xxx --state-db .metis/state.db` 时，如果 session 存在则恢复 | `metis/app/tui.py` | 0.25d | 12.1.2 | TUI 正确恢复 Web 创建的会话 |
| 12.1.4 | Web UI 显示其他端的活动会话 | 在 Web UI 会话列表中标记"来自 TUI"的会话，支持切换继续 | `metis/app/web_assets/static/app.js` | 0.25d | 12.1.3 | 标记正确，切换后消息同步 |
| 12.1.5 | 跨端同步测试 | 测试：Web 创建会话 → TUI 恢复 → TUI 发送消息 → Web 刷新看到新消息 | 测试脚本 | 0.5d | 12.1.4 | 端到端同步正确 |

**功能 12 总计**: 1.5 天

---

### 功能 13: 定时任务调度器（2.5 天）

**目标**: Agent 可以按 cron 表达式定时执行任务。

| ID | 任务名称 | 描述 | 文件路径 | 工作量 | 依赖 | 验收标准 |
|----|---------|------|---------|--------|------|---------|
| 13.1.1 | 实现 TaskScheduler 核心 | 基于 `asyncio` 的调度器，支持 cron 表达式解析（使用 `croniter` 库），任务持久化到 SQLite schedules 表 | `metis/scheduler/core.py` | 0.5d | - | 调度准确，支持秒级精度 |
| 13.1.2 | 实现调度任务执行器 | 到时间后，加载指定 agent 的 manifest，构建 AgentLoop，执行预设任务指令 | `metis/scheduler/executor.py` | 0.5d | 13.1.1 | 执行正确，异常时记录日志 |
| 13.1.3 | CLI 命令 `metis schedule` | `metis schedule add --agent xxx --cron "0 9 * * *" --task "生成日报"`，`metis schedule list`、`metis schedule remove` | `metis/adapters/cli.py` | 0.25d | 13.1.2 | CLI 命令可用，参数正确 |
| 13.1.4 | Swarm Hub 调度管理面板 | 在 Web UI 中显示定时任务列表，支持新增、编辑、暂停、删除 | `metis/app/web_assets_swarm/` | 0.5d | 13.1.3 | 面板可用，cron 表达式有可视化辅助 |
| 13.1.5 | 调度器集成测试 | 测试：创建 1 分钟后执行的任务 → 等待 → 验证执行 → 验证结果记录 | `tests/unit/test_scheduler.py` | 0.5d | 13.1.4 | 测试通过 |
| 13.1.6 | 调度器与主服务集成 | `metis swarm` 启动时自动启动调度器，`metis web` 可选启动 | `metis/swarm/hub.py` | 0.25d | 13.1.1 | 集成正确， graceful shutdown |

**功能 13 总计**: 2.5 天

---

### 功能 14: 更多 Provider 原生支持（3 天）

**目标**: 原生支持 Anthropic、Google Gemini、Ollama 本地模型，无需 OpenAI 兼容代理。

| ID | 任务名称 | 描述 | 文件路径 | 工作量 | 依赖 | 验收标准 |
|----|---------|------|---------|--------|------|---------|
| 14.1.1 | 实现 AnthropicProvider | 基于 `anthropic` SDK，支持 Messages API、tool use、streaming | `metis/providers/anthropic.py` | 0.75d | - | 可正常对话，工具调用正确 |
| 14.1.2 | 实现 GeminiProvider | 基于 `google-generativeai` SDK，支持 Gemini 1.5/2.0 | `metis/providers/gemini.py` | 0.75d | - | 可正常对话，多模态支持 |
| 14.1.3 | 实现 OllamaProvider | 基于 `ollama` Python SDK 或直接 HTTP，支持本地模型加载 | `metis/providers/ollama.py` | 0.5d | - | 可连接本地 Ollama 服务 |
| 14.1.4 | 注册新 Provider 到工厂 | 在 `factory.py` 中注册 `anthropic`、`gemini`、`ollama` | `metis/providers/factory.py` | 0.25d | 14.1.1~14.1.3 | 工厂选择逻辑正确 |
| 14.1.5 | 更新 ProviderCapabilities 检测 | 各 provider 正确报告自身能力（tool calling、streaming、context size 等） | `metis/providers/*.py` | 0.25d | 14.1.1~14.1.3 | 能力报告准确 |
| 14.1.6 | Provider 集成测试 | 为每个新 provider 编写 mock 测试（不依赖真实 API key） | `tests/unit/test_providers_*.py` | 0.5d | 14.1.4 | 所有测试通过 |

**功能 14 总计**: 3 天

---

## Phase 4: 远期战略（按需启动）

| 功能 | 任务数 | 预估工作量 | 说明 |
|------|--------|-----------|------|
| OpenTelemetry 分布式追踪 | 4 | 2-3 天 | 集成 OTel SDK，自动 instrumentation |
| 用户系统与 RBAC | 6 | 3-4 天 | 用户表、角色、权限矩阵、API key 绑定 |
| Agent 自动优化（Auto-Eval） | 8 | 5-7 天 | 基于 eval 结果自动 A/B 测试 prompt、profile |
| 联邦学习/模型微调 | 10 | 7-10 天 | 轨迹数据收集、LoRA 微调 pipeline |

---

## 汇总统计

### 按 Phase 统计

| Phase | 功能数 | 任务数 | 总工作量 | 周期 |
|-------|--------|--------|---------|------|
| Phase 1: 可用性加固 | 4 | 44 | 10 天 | 2 周 |
| Phase 2: 能力扩展 | 5 | 52 | 14.5 天 | 3 周 |
| Phase 3: 生态建设 | 5 | 33 | 13 天 | 2 周 |
| Phase 4: 远期战略 | 4 | 28 | 17-24 天 | 按需 |
| **合计** | **18** | **157** | **37.5 天** | **7 周（不含 Phase 4）** |

### 按优先级统计

| 优先级 | 任务数 | 工作量 | 占比 |
|--------|--------|--------|------|
| P0 | 16 | 8.5 天 | 23% |
| P1 | 48 | 16.5 天 | 44% |
| P2 | 33 | 13 天 | 35% |

### 最关键的前 10 个任务（建议立即启动）

1. **1.1.3** GET /hitl/pending — HITL 审批基础 API
2. **1.1.4** POST /hitl/{id}/approve — HITL 审批操作
3. **1.2.2** HITLApprover 阻塞等待改造 — Loop 集成核心
4. **1.3.4** 前端 pending 列表渲染 — 用户可见的审批面板
5. **2.1.1** Provider 热重建函数 — 配置热重载核心
6. **2.2.4** Settings 数据加载与保存 — 用户修改配置的入口
7. **3.1.3** JSON 解析 + fallback — Coordinator 智能编排核心
8. **3.1.5** 拓扑排序执行 — 任务依赖正确执行
9. **3.2.3** Coordinator 能力匹配 prompt — 智能任务分配
10. **4.1.1** weather-tool 示例插件 — 降低扩展门槛

---

*本清单由源码审计结果直接推导，每个任务都有明确的文件路径和验收标准，可直接分配给开发执行。*
