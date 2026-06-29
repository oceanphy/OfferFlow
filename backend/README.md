# OfferFlow Backend

面试诊断引擎 — FastAPI + 自研 Harness 10 层架构。

## 环境要求

- Python >= 3.12
- [uv](https://docs.astral.sh/uv/)（Python 包管理器）

## 快速开始

```bash
# 1. 安装依赖
uv sync

# 2. 配置 API key
cp .env.example .env
# 编辑 .env，填入实际的 API key 和模型配置

# 3. 启动服务
uv run uvicorn offerflow.api.main:app --reload --port 8000
```

启动后访问 http://localhost:8000/health 返回 `{"status":"ok"}`。

### 停止服务

按 `Ctrl+C` 终止进程。如果进程异常退出导致端口被占用（Windows 常见：`WinError 10013`）：

```powershell
# PowerShell — 查找占用 8000 端口的进程
netstat -ano | findstr :8000 | findstr LISTENING

# 杀掉对应 PID（替换为实际 PID）
taskkill /F /PID <PID>
```

```bash
# Git Bash / WSL
netstat -ano | grep LISTENING | grep :8000
taskkill //F //PID <PID>
```

## PyCharm 配置

1. 用 PyCharm 打开 `backend/` 目录
2. Settings → Project → Python Interpreter → 选择已有解释器 → 指向 `.venv/Scripts/python.exe`
3. 创建 Run Configuration：
   - Module name: `uvicorn`
   - Parameters: `offerflow.api.main:app --reload --port 8000`
   - Working directory: `backend/`
   - Environment variables: 确保 `.env` 文件在 `backend/` 目录下（会自动加载）

也可以直接 Run Configuration 中配置 Script path：
   - Script: `-m uvicorn offerflow.api.main:app --reload --port 8000`

## 模型配置

### 支持三种 provider

| Provider | 协议 | 需要额外安装？ | 配置方式 |
|---|---|---|---|
| **OpenAI** | OpenAI 原生 | 否 | `OFFERFLOW_PROVIDER=openai` |
| **DeepSeek** | OpenAI 兼容 | 否 | `OFFERFLOW_PROVIDER=deepseek`（或默认 `openai`） |
| **Anthropic** | Anthropic Messages API | `uv add anthropic` | `OFFERFLOW_PROVIDER=anthropic` |

OpenAI 和 DeepSeek 共用同一套 SDK，因为 DeepSeek 提供 OpenAI 兼容的 API 端点。只需改环境变量即可切换，不需要改代码。

### DeepSeek 配置（.env）

```ini
OFFERFLOW_PROVIDER=deepseek
OPENAI_API_KEY=sk-your-deepseek-key
OPENAI_BASE_URL=https://api.deepseek.com
OFFERFLOW_MODEL=deepseek-chat
OFFERFLOW_FALLBACK_MODEL=deepseek-chat
```

### Anthropic 配置（.env）

```bash
# 先安装 SDK
uv add anthropic

# .env 配置
OFFERFLOW_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-your-key
OFFERFLOW_MODEL=claude-sonnet-4-20250514
```

### 无 API key 模式

不配置 `OPENAI_API_KEY` 时，系统工作在**启发式模式**——基于规则匹配打分，无需联网。适合快速测试。

## 环境变量参考

| 变量 | 说明 | 默认值 |
|---|---|---|
| `OFFERFLOW_PROVIDER` | 模型提供商：`openai` / `deepseek` / `anthropic` | `openai` |
| `OPENAI_API_KEY` | OpenAI/DeepSeek 的 API key | — |
| `OPENAI_BASE_URL` | OpenAI 兼容 API 地址 | `https://api.openai.com/v1` |
| `OFFERFLOW_MODEL` | 主模型 | `gpt-4o-mini` |
| `OFFERFLOW_FALLBACK_MODEL` | 降级模型 | `gpt-3.5-turbo` |
| `ANTHROPIC_API_KEY` | Anthropic API key（仅 anthropic provider 需要） | — |
| `OFFERFLOW_PORT` | 服务端口 | `8000` |

## 运行测试

```bash
uv run pytest tests/ -v
```

## API 端点

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/health` | 健康检查 |
| `POST` | `/api/diagnose` | 上传文字稿，SSE 流式返回诊断进度 |
| `GET` | `/api/report/{id}` | 获取历史报告 |
| `DELETE` | `/api/user/data` | 删除所有用户数据 |
| `CRUD` | `/api/knowledge/entries` | 知识库管理 |

## 项目结构

```
backend/
├── .env.example          # 环境变量模板
├── pyproject.toml
└── src/offerflow/
    ├── api/              # FastAPI 路由
    ├── harness/
    │   ├── tools/        # L1: 原子工具
    │   ├── skills/       # L2: 诊断流程编排
    │   ├── engine/       # L3: LLM 调用 + 缓存 + token 预算
    │   ├── context/      # L4: 分层上下文管理
    │   ├── memory/       # L5: 用户画像 + 诊断历史
    │   ├── permission/   # L6: 隐私脱敏
    │   ├── sessions/     # L7: 会话持久化
    │   ├── commands/     # L8: CLI 入口
    │   ├── hooks/        # L9: 生命周期钩子
    │   └── agents/       # L10: 并行 Sub-agent
    └── knowledge/        # 知识库
```
