# ChatBI

<p align="center">
  <strong>Agentic AI Data Platform</strong>
</p>

<p align="center">
  <a href="https://github.com/wangyiyi2056/chatBI">
    <img src="https://img.shields.io/badge/visibility-private-black?style=flat-square" alt="private repo">
  </a>
</p>

> **Visibility**: This repository is currently **private** and visible only to the owner. Open-sourcing may be considered in the future.

---

<!-- English (default open) -->
<details open>
<summary><strong>English</strong> (click to collapse)</summary>

<br>

**ChatBI** is an agentic AI data platform that lets you chat with your data, build knowledge bases, orchestrate workflows, and run sandboxed code — all through a unified API and modern web interface.

### Architecture

```
packages/
├── chatbi-core/      # Core framework: config, model abstraction, component registry
├── chatbi-serve/     # FastAPI service layer: chat, datasource, agent, knowledge, AWEL APIs
├── chatbi-ext/       # Extensions: RAG pipeline, vector store, AWEL operators
├── chatbi-sandbox/   # Sandboxed execution environment (Docker-isolated)
└── chatbi-app/       # Application entrypoint: Uvicorn bootstrap scripts
frontend/             # Vite + React 18 + TypeScript 5 web interface
```

### Quick Start

#### 1. Install dependencies

```bash
uv sync --all-packages
```

#### 2. Configure the model

Edit `configs/chatbi.toml`:

```toml
app_name = "ChatBI"
debug = true
port = 8000
default_llm = "gpt-4o-mini"

[[llm_configs]]
model_name = "gpt-4o-mini"
model_type = "openai"
api_base = "https://api.openai.com/v1"
# api_key is recommended via env var CHATBI_API_KEY
temperature = 0.7
max_tokens = 2048
```

#### 3. Start the server

```bash
uv run uvicorn chatbi_app.main:app --reload
```

Or:

```bash
uv run chatbi
```

#### 4. Test the chat API

Non-streaming:

```bash
curl -X POST http://localhost:8000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "Hello"}]}'
```

Streaming (SSE):

```bash
curl -X POST http://localhost:8000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "Hello"}], "stream": true}'
```

#### 5. Datasource management

Create a SQLite datasource:

```bash
curl -X POST http://localhost:8000/api/v1/datasource \
  -H "Content-Type: application/json" \
  -d '{"config": {"name": "demo", "db_type": "sqlite", "database": ":memory:"}}'
```

Execute SQL:

```bash
curl -X POST http://localhost:8000/api/v1/datasource/demo/query \
  -H "Content-Type: application/json" \
  -d '{"sql": "SELECT * FROM sqlite_master WHERE type=\'table\'"}'
```

Natural language to SQL (via Chat API, auto-detect SQL intent):

```bash
curl -X POST http://localhost:8000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "List all tables in the demo datasource"}]}'
```

#### 6. Knowledge base & RAG

Upload a file to build a knowledge base:

```bash
curl -X POST "http://localhost:8000/api/v1/knowledge/upload?name=docs" \
  -F "file=@README.md"
```

Query the knowledge base:

```bash
curl -X POST "http://localhost:8000/api/v1/knowledge/docs/query?query=What%20is%20ChatBI"
```

#### 7. Agent / Skill

List available skills:

```bash
curl http://localhost:8000/api/v1/agent/skills
```

#### 8. AWEL workflow orchestration

List operators:

```bash
curl http://localhost:8000/api/v1/awel/operators
```

Run a sample workflow:

```bash
curl -X POST http://localhost:8000/api/v1/awel/run \
  -H "Content-Type: application/json" \
  -d '{"initial_input": "hello"}'
```

#### 9. Sandbox execution

Start the sandbox service (optional, separate process):

```bash
uv run uvicorn sandbox.api.server:app --port 9000
```

Execute code:

```bash
curl -X POST http://localhost:9000/execute \
  -H "Content-Type: application/json" \
  -d '{"code": "print(1+1)", "language": "python"}'
```

### Frontend

The project includes a modern frontend built with **Vite + React 18 + TypeScript 5**, located in `frontend/`.

```bash
cd frontend
npm install
npm run dev
```

The frontend runs at `http://localhost:3000` by default, proxying `/api` requests to the backend at `http://localhost:8000`.

#### Pages

- **Explore** — Entry navigation page
- **Chat** — Desktop chat interface (streaming, Markdown, virtual scrolling)
- **Mobile Chat** — Mobile-optimized chat (`/mobile/chat`)
- **Share** — Read-only shared conversation page
- **Construct** — Builder hub
  - **App** — App builder (wizard form)
  - **Database** — Datasource management & SQL execution
  - **Knowledge** — File upload, RAG Q&A, chunking strategies
  - **Skills** — Registered skills list
  - **Models** — Model management (start/stop/add)
  - **Flow** — AWEL workflow (visual canvas + operators)
  - **Prompt** — Prompt editor (variables + live preview)
  - **Dbgpts** — Plugin management (Hub + My Plugins)
- **Evaluation** — Model evaluation tasks & dataset management

#### Frontend tests

```bash
cd frontend
npm test        # Vitest unit tests
npm run e2e     # Playwright E2E tests
```

See [`frontend/README.md`](frontend/README.md) for more details.

### Backend tests

```bash
uv run pytest tests/ -v
```

### Implementation Phases

- [x] Phase 1: Skeleton — model abstraction + chat service
- [x] Phase 2: Data connection — datasource abstraction + SQL generation & execution
- [x] Phase 3: RAG & Agent framework — knowledge base + multi-agent collaboration
- [x] Phase 4: Workflow orchestration & sandbox safety — AWEL + Sandbox

</details>

---

<!-- Chinese (default closed) -->
<details>
<summary><strong>中文</strong>（点击展开）</summary>

<br>

**ChatBI** 是一个智能 AI 数据平台，让你能够通过统一的 API 和现代化的 Web 界面与数据对话、构建知识库、编排工作流，并在安全沙箱中执行代码。

### 架构

```
packages/
├── chatbi-core/      # 核心框架：配置、模型抽象、组件注册中心
├── chatbi-serve/     # FastAPI 服务层：对话、数据源、Agent、知识库、AWEL API
├── chatbi-ext/       # 扩展层：RAG Pipeline、向量存储、AWEL 算子
├── chatbi-sandbox/   # 沙箱执行环境（Docker 隔离）
└── chatbi-app/       # 应用入口：Uvicorn 启动脚本
frontend/             # Vite + React 18 + TypeScript 5 前端界面
```

### 快速开始

#### 1. 安装依赖

```bash
uv sync --all-packages
```

#### 2. 配置模型

编辑 `configs/chatbi.toml`：

```toml
app_name = "ChatBI"
debug = true
port = 8000
default_llm = "gpt-4o-mini"

[[llm_configs]]
model_name = "gpt-4o-mini"
model_type = "openai"
api_base = "https://api.openai.com/v1"
# api_key 推荐通过环境变量 CHATBI_API_KEY 传入
temperature = 0.7
max_tokens = 2048
```

#### 3. 启动服务

```bash
uv run uvicorn chatbi_app.main:app --reload
```

或：

```bash
uv run chatbi
```

#### 4. 测试对话接口

非流式：

```bash
curl -X POST http://localhost:8000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "Hello"}]}'
```

流式（SSE）：

```bash
curl -X POST http://localhost:8000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "Hello"}], "stream": true}'
```

#### 5. 数据源管理

创建 SQLite 数据源：

```bash
curl -X POST http://localhost:8000/api/v1/datasource \
  -H "Content-Type: application/json" \
  -d '{"config": {"name": "demo", "db_type": "sqlite", "database": ":memory:"}}'
```

执行 SQL：

```bash
curl -X POST http://localhost:8000/api/v1/datasource/demo/query \
  -H "Content-Type: application/json" \
  -d '{"sql": "SELECT * FROM sqlite_master WHERE type=\'table\'"}'
```

自然语言转 SQL（通过 Chat API，自动识别 SQL 意图）：

```bash
curl -X POST http://localhost:8000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "查询 demo 数据源的所有表"}]}'
```

#### 6. 知识库与 RAG

上传文件建立知识库：

```bash
curl -X POST "http://localhost:8000/api/v1/knowledge/upload?name=docs" \
  -F "file=@README.md"
```

知识库问答：

```bash
curl -X POST "http://localhost:8000/api/v1/knowledge/docs/query?query=What%20is%20ChatBI"
```

#### 7. Agent / Skill

列出可用 Skills：

```bash
curl http://localhost:8000/api/v1/agent/skills
```

#### 8. AWEL 工作流编排

列出算子：

```bash
curl http://localhost:8000/api/v1/awel/operators
```

运行示例工作流：

```bash
curl -X POST http://localhost:8000/api/v1/awel/run \
  -H "Content-Type: application/json" \
  -d '{"initial_input": "hello"}'
```

#### 9. Sandbox 沙箱执行

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

### 前端界面

项目包含一个基于 **Vite + React 18 + TypeScript 5** 的现代化前端，目录位于 `frontend/`。

```bash
cd frontend
npm install
npm run dev
```

前端默认运行在 `http://localhost:3000`，通过 Vite proxy 自动转发 `/api` 请求到后端 `http://localhost:8000`。

#### 页面

- **Explore** — 入口导航页
- **Chat** — 桌面端对话界面（支持流式输出、Markdown 渲染、虚拟滚动）
- **Mobile Chat** — 移动端专属聊天界面（`/mobile/chat`）
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

#### 前端测试

```bash
cd frontend
npm test        # Vitest 单元测试
npm run e2e     # Playwright E2E 测试
```

详见 [`frontend/README.md`](frontend/README.md)。

### 后端测试

```bash
uv run pytest tests/ -v
```

### 实现阶段

- [x] Phase 1：基础骨架 — 模型抽象 + 对话服务
- [x] Phase 2：数据连接 — 数据源抽象 + SQL 生成与执行
- [x] Phase 3：RAG 与 Agent 框架 — 知识库 + 多 Agent 协作
- [x] Phase 4：工作流编排与沙箱安全 — AWEL + Sandbox

</details>
