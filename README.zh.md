# Aurora

> [English](README.md) | [中文](README.zh.md)

<p align="center">
  <strong>智能 AI 数据平台</strong>
</p>

<p align="center">
  <a href="https://github.com/wangyiyi2056/Aurora-Design">
    <img src="https://img.shields.io/badge/visibility-public-green?style=flat-square" alt="public repo">
  </a>
</p>

---

**Aurora** 是一个智能 AI 数据平台，让你能够通过统一的 API 和现代化的 Web 界面与数据对话、构建知识库、编排工作流，并在安全沙箱中执行代码。

## 架构

```
packages/
├── aurora-core/      # 核心框架：配置、模型抽象、组件注册中心
├── aurora-serve/     # FastAPI 服务层：对话、数据源、Agent、知识库、AWEL API
├── aurora-ext/       # 扩展层：RAG Pipeline、向量存储、AWEL 算子
├── aurora-sandbox/   # 沙箱执行环境（Docker 隔离）
└── aurora-app/       # 应用入口：Uvicorn 启动脚本
frontend/             # Vite + React 18 + TypeScript 5 前端界面
```

## 快速开始

### 1. 安装依赖

```bash
uv sync
```

### 2. 配置模型

编辑 `configs/aurora.toml`：

```toml
app_name = "Aurora"
debug = true
port = 8888
default_llm = "gpt-4o-mini"

[[llm_configs]]
model_name = "gpt-4o-mini"
model_type = "openai"
api_base = "https://api.openai.com/v1"
# api_key 推荐通过环境变量 AURORA_API_KEY 传入
temperature = 0.7
max_tokens = 2048
```

### 3. 启动服务

```bash
uv run uvicorn aurora_app.main:app --reload
```

或：

```bash
uv run aurora
```

### 4. 测试对话接口

非流式：

```bash
curl -X POST http://localhost:8888/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "Hello"}]}'
```

流式（SSE）：

```bash
curl -X POST http://localhost:8888/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "Hello"}], "stream": true}'
```

### 5. 数据源管理

创建 SQLite 数据源：

```bash
curl -X POST http://localhost:8888/api/v1/datasource \
  -H "Content-Type: application/json" \
  -d '{"config": {"name": "demo", "db_type": "sqlite", "database": ":memory:"}}'
```

执行 SQL：

```bash
curl -X POST http://localhost:8888/api/v1/datasource/demo/query \
  -H "Content-Type: application/json" \
  -d '{"sql": "SELECT * FROM sqlite_master WHERE type=\'table\'"}'
```

自然语言转 SQL（通过 Chat API，自动识别 SQL 意图）：

```bash
curl -X POST http://localhost:8888/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "查询 demo 数据源的所有表"}]}'
```

### 6. 知识库与 RAG

上传文件建立知识库：

```bash
curl -X POST "http://localhost:8888/api/v1/knowledge/upload?name=docs" \
  -F "file=@README.md"
```

知识库问答：

```bash
curl -X POST "http://localhost:8888/api/v1/knowledge/docs/query?query=What%20is%20Aurora"
```

### 7. Agent / Skill

列出可用 Skills：

```bash
curl http://localhost:8888/api/v1/agent/skills
```

### 8. AWEL 工作流编排

列出算子：

```bash
curl http://localhost:8888/api/v1/awel/operators
```

运行示例工作流：

```bash
curl -X POST http://localhost:8888/api/v1/awel/run \
  -H "Content-Type: application/json" \
  -d '{"initial_input": "hello"}'
```

### 9. Sandbox 沙箱执行

启动沙箱服务（可选，独立进程）：

```bash
uv run uvicorn sandbox.api.server:app --port 9000
```

执行代码：

```bash
curl -X POST http://localhost:9000/execute \
  -H "Content-Type: application/json" \
  -d '{"code": "print(1+1)", "language": "python"}'
```

## 前端界面

项目包含一个基于 **Vite + React 18 + TypeScript 5** 的现代化前端，目录位于 `frontend/`。

```bash
cd frontend
npm install
npm run dev
```

前端默认运行在 `http://localhost:3000`，通过 Vite proxy 自动转发 `/api` 请求到后端 `http://localhost:8888`。

### 页面

- **Explore** — 入口导航页
- **Chat** — 桌面端对话界面（支持流式输出、Markdown 渲染、虚拟滚动）
- **Share** — 分享对话只读页
- **Construct** — 构建中心
  - **App** — 应用构建器（向导式表单）
  - **Database** — 数据源管理与 SQL 执行
  - **Knowledge** — 文件上传、RAG 问答、文档分块策略、知识图谱占位
  - **Skills** — 已注册技能列表
  - **Models** — 模型管理（启动/停止/新增）
  - **Flow** — AWEL 工作流（可视化画布占位 + 算子 + 运行）
  - **Prompt** — Prompt 编辑器（变量提取 + 实时预览）
  - **Dbgpts** — 插件管理（Hub + My Plugins）
- **Evaluation** — 模型评测任务与数据集管理

### 前端测试

```bash
cd frontend
npm test        # Vitest 单元测试
npm run e2e     # Playwright E2E 测试
```

详见 [`frontend/README.md`](frontend/README.md)。

## 后端测试

```bash
uv run pytest tests/ -v
```

## 实现阶段

- [x] Phase 1：基础骨架 — 模型抽象 + 对话服务
- [x] Phase 2：数据连接 — 数据源抽象 + SQL 生成与执行
- [x] Phase 3：RAG 与 Agent 框架 — 知识库 + 多 Agent 协作
- [x] Phase 4：工作流编排与沙箱安全 — AWEL + Sandbox
