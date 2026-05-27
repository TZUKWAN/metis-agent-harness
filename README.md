# Metis Agent Harness

Metis 是一个领域无关的智能体运行时框架，旨在通过外部化任务状态、控制工具使用、保留证据链、验证产出物和支持小模型执行，使 AI Agent 更加可靠、可控、可观测。

---

## 核心特性

| 特性 | 说明 |
|------|------|
| **Token 级流式输出** | 后端 SSE 解析 + WebSocket/SSE 转发 + 前端打字机渲染，达到 Kimi Code 级 WebUI 体验 |
| **Textual 全屏 TUI** | 基于 Textual 的全屏终端应用，支持流式输出、工具状态卡片、全键盘快捷键，达到 Claude Code / Codex CLI 水平 |
| **Swarm Hub** | 多智能体协作中心，支持 WebSocket 流式对话、群组管理、智能体编排 |
| **MCP 协议支持** | 内置 MCP 客户端与服务器，支持与外部工具生态无缝对接 |
| **HITL 人机协同** |  Humans-in-the-Loop API，支持审批、干预、规则引擎 |
| **行为规则引擎** | 可插拔的行为门控与钩子系统，精细控制 Agent 行为 |
| **智能路由** | 基于健康检查的策略路由，支持多模型负载均衡与故障转移 |
| **上下文压缩** | 自适应上下文压缩与 Token 预算管理，支持长对话 |
| **插件系统** | 声明式插件 manifest，支持工具、提示片段、评估套件动态加载 |
| **证据与校验** | 工具调用证据链、结果校验、持久化与复盘 |

---

## 架构概览

```
┌─────────────────────────────────────────────────────────────────────┐
│                        User Interfaces                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │   CLI    │  │  TUI     │  │  WebUI   │  │   Swarm Hub      │   │
│  │ (metis)  │  │(textual) │  │(vanilla) │  │   (WebSocket)    │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────┬─────────┘   │
└───────┼─────────────┼─────────────┼─────────────────┼─────────────┘
        │             │             │                 │
        └─────────────┴──────┬──────┴─────────────────┘
                             │
                    ┌────────┴────────┐
                    │   AgentLoop     │
                    │  (turn-based)   │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
   ┌────┴────┐        ┌─────┴─────┐       ┌──────┴──────┐
   │ HookBus │        │ ToolRegistry      │ ProviderAbstraction │
   │ (events)│        │ (dispatch)│       │ (OpenAI/SSE)  │
   └────┬────┘        └─────┬─────┘       └──────┬──────┘
        │                   │                    │
   ┌────┴────┐        ┌─────┴─────┐       ┌──────┴──────┐
   │  HITL   │        │  MCP      │       │  Streaming  │
   │ Behavior│        │  Client   │       │  SSE Parser │
   └─────────┘        └───────────┘       └─────────────┘
```

---

## 安装

```bash
# 克隆仓库
git clone https://github.com/TZUKWAN/metis-agent-harness.git
cd metis-agent-harness

# 安装依赖
pip install -e ".[dev]"
```

---

## 快速配置

```powershell
# Windows PowerShell
$env:METIS_BASE_URL="https://open.bigmodel.cn/api/paas/v4"
$env:METIS_API_KEY="<your-api-key>"
$env:METIS_MODEL="glm-4.7-flash"

# 或 Linux/macOS bash
export METIS_BASE_URL="https://open.bigmodel.cn/api/paas/v4"
export METIS_API_KEY="<your-api-key>"
export METIS_MODEL="glm-4.7-flash"
```

支持的模型自动识别流式能力：
- `glm-4.9` / `glm-4.7` / `glm-4.5` / `glm-4`
- `gpt-4o` / `gpt-4o-mini` / `gpt-4`
- `claude-3-5-sonnet` / `claude-3-5-haiku`

---

## 使用指南

### 1. CLI 模式

```bash
# 单次任务
metis run "分析这个目录的代码结构"

# 带 manifest 和持久化
metis run "总结工作空间" --manifest metis-agent.json --state-db .metis/state.db --session-id demo
```

### 2. TUI 全屏终端（推荐）

```bash
metis tui --manifest metis-agent.json --state-db .metis/state.db
```

**快捷键：**

| 快捷键 | 动作 |
|--------|------|
| `Ctrl+C` / `Q` | 退出 |
| `Ctrl+N` | 新建会话 |
| `Enter` | 发送消息 |
| `Shift+Enter` | 输入区换行 |
| `Ctrl+R` | 重新生成最后一条回复 |
| `Esc` | 取消当前生成 |
| `Tab` | 切换焦点区域 |

### 3. Web UI

```bash
metis web --manifest metis-agent.json --state-db .metis/state.db --port 8080
```

打开浏览器访问 `http://localhost:8080`。

**WebUI 特性：**
- Token 级流式输出，逐字显示
- Markdown 实时渲染 + 代码高亮
- 代码块悬浮操作栏：复制、插入输入框、下载为新文件
- 工具调用状态卡片（运行中 / 成功 / 错误）
- 移动端响应式布局
- 侧边栏会话管理

### 4. Swarm Hub（多智能体协作）

```bash
metis swarm hub --port 8081
```

支持：
- 多智能体群组管理
- WebSocket 实时流式对话
- 智能体间编排与上下文共享

---

## 开发工作流

### 创建定制化 Agent

```bash
metis develop --request "构建一个学术写作助手" --name "Academic Writer"
```

该命令会：
1. 分析需求并生成适配方案
2. 创建实现契约与任务拆解
3. 生成品牌配置、manifest、提示词
4. 输出运行脚本与 Claude Code / Codex 命令

### 插件开发

```bash
# 检查插件 manifest
metis plugin inspect --path ./plugins/example --json
```

插件可以贡献：工具、提示片段、评估套件、证据规则。详见 `docs/plugin-development.md`。

---

## 高级功能

### 模型能力检查

```bash
metis provider capabilities --model glm-4.7-flash --json
```

输出包含：原生工具调用、JSON Schema、Thinking、流式支持、上下文/输出 Token 限制。

### 会话检查点

```bash
# 列检查点
metis checkpoint list --state-db .metis/state.db --session-id <id> --json

# 最新检查点
metis checkpoint latest --state-db .metis/state.db --session-id <id> --json

# 从检查点恢复
metis resume --state-db .metis/state.db --session-id <id> --message "继续之前的任务"
```

### 打包与分发

```bash
metis package build --source ./metis-development --output ./dist/my-agent
metis package verify --path ./dist/my-agent --profile dev
metis package install --path ./dist/my-agent --install-dir ./agents/my-agent
metis package export --path ./dist/my-agent --output ./dist/my-agent.zip
```

---

## 测试

```bash
# 全部测试
python -m pytest -q

# 带覆盖率
python -m pytest --cov=metis --cov-report=html

# 网络测试（需要配置 API 密钥）
python -m pytest -q -m network

# 流式相关测试
python -m pytest tests/unit/test_provider_streaming.py tests/unit/test_loop_streaming.py -v
```

当前测试状态：**1261 测试全部通过**

---

## 模块说明

| 模块 | 路径 | 说明 |
|------|------|------|
| 运行时核心 | `metis/runtime/` | AgentLoop、响应模型、任务状态 |
| 事件总线 | `metis/events/` | HookBus、事件类型定义 |
| Provider | `metis/providers/` | OpenAI 兼容 Provider、SSE 流式解析、工厂 |
| 工具系统 | `metis/tools/` | 注册表、调度器、策略、校验 |
| 上下文 | `metis/context/` | 压缩、裁剪、Token 计算、引擎 |
| TUI | `metis/app/tui.py` | Textual 全屏应用 |
| WebUI | `metis/app/web.py` | FastAPI + WebSocket/SSE |
| Swarm | `metis/swarm/` | 多智能体编排、Hub、注册表 |
| MCP | `metis/mcp/` | MCP 客户端/服务器/协议 |
| HITL | `metis/hitl/` | 人机协同核心、规则、存储 |
| 行为规则 | `metis/behavior/` | 门控、钩子、注册表、内置规则 |
| 路由 | `metis/routing/` | 健康检查、策略路由、运行时集成 |
| 可视化 | `metis/viz/` | 报告、工具流、Trace 渲染 |

---

## 环境变量参考

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `METIS_BASE_URL` | Provider API 基础地址 | - |
| `METIS_API_KEY` | Provider API 密钥 | - |
| `METIS_MODEL` | 默认模型 | `glm-4.7-flash` |
| `METIS_PROVIDER_STREAMING_SUPPORTED` | 强制开启流式 | `false` |
| `METIS_PROVIDER_MAX_TOKENS` | 最大输出 Token | 模型能力值 |
| `METIS_STATE_DB` | 状态数据库路径 | - |
| `METIS_MAX_TURNS` | 最大轮数 | `10` |

---

## 许可

MIT License

---

## 相关文档

- `docs/plugin-development.md` - 插件开发指南
- `docs/plugin-quickstart.md` - 插件快速开始
- `docs/behavior-rules.md` - 行为规则说明
- `CHANGELOG.md` - 变更日志
