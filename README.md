# Aurora

> [English](README.md) | [中文](README.zh.md)

<p align="center">
  <strong>Agentic AI Data Platform</strong>
</p>

<p align="center">
  <a href="https://github.com/wangyiyi2056/Aurora-Design">
    <img src="https://img.shields.io/badge/visibility-public-green?style=flat-square" alt="public repo">
  </a>
</p>

---

**Aurora** is an agentic AI data platform that lets you chat with your data, build knowledge bases, orchestrate workflows, and run sandboxed code — all through a unified API and modern web interface.

## Architecture

```
packages/
├── aurora-core/      # Core framework: config, model abstraction, component registry
├── aurora-serve/     # FastAPI service layer: chat, datasource, agent, knowledge, AWEL APIs
├── aurora-ext/       # Extensions: RAG pipeline, vector store, AWEL operators
├── aurora-sandbox/   # Sandboxed execution environment (Docker-isolated)
└── aurora-app/       # Application entrypoint: Uvicorn bootstrap scripts
frontend/             # Vite + React 18 + TypeScript 5 web interface
```

## Quick Start

### 1. Install dependencies

```bash
uv sync
```

### 2. Configure the model

Edit `configs/aurora.toml`:

```toml
app_name = "Aurora"
debug = true
port = 8888
default_llm = "gpt-4o-mini"

[[llm_configs]]
model_name = "gpt-4o-mini"
model_type = "openai"
api_base = "https://api.openai.com/v1"
# api_key is recommended via env var AURORA_API_KEY
temperature = 0.7
max_tokens = 2048
```

### 3. Start the server

```bash
uv run uvicorn aurora_app.main:app --reload
```

Or:

```bash
uv run aurora
```

### 4. Test the chat API

Non-streaming:

```bash
curl -X POST http://localhost:8888/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "Hello"}]}'
```

Streaming (SSE):

```bash
curl -X POST http://localhost:8888/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "Hello"}], "stream": true}'
```

### 5. Datasource management

Create a SQLite datasource:

```bash
curl -X POST http://localhost:8888/api/v1/datasource \
  -H "Content-Type: application/json" \
  -d '{"config": {"name": "demo", "db_type": "sqlite", "database": ":memory:"}}'
```

Execute SQL:

```bash
curl -X POST http://localhost:8888/api/v1/datasource/demo/query \
  -H "Content-Type: application/json" \
  -d '{"sql": "SELECT * FROM sqlite_master WHERE type=\'table\'"}'
```

Natural language to SQL (via Chat API, auto-detect SQL intent):

```bash
curl -X POST http://localhost:8888/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "List all tables in the demo datasource"}]}'
```

### 6. Knowledge base & RAG

Upload a file to build a knowledge base:

```bash
curl -X POST "http://localhost:8888/api/v1/knowledge/upload?name=docs" \
  -F "file=@README.md"
```

Query the knowledge base:

```bash
curl -X POST "http://localhost:8888/api/v1/knowledge/docs/query?query=What%20is%20Aurora"
```

### 7. Agent / Skill

List available skills:

```bash
curl http://localhost:8888/api/v1/agent/skills
```

### 8. AWEL workflow orchestration

List operators:

```bash
curl http://localhost:8888/api/v1/awel/operators
```

Run a sample workflow:

```bash
curl -X POST http://localhost:8888/api/v1/awel/run \
  -H "Content-Type: application/json" \
  -d '{"initial_input": "hello"}'
```

### 9. Sandbox execution

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

## Frontend

The project includes a modern frontend built with **Vite + React 18 + TypeScript 5**, located in `frontend/`.

```bash
cd frontend
npm install
npm run dev
```

The frontend runs at `http://localhost:3000` by default, proxying `/api` requests to the backend at `http://localhost:8888`.

### Pages

- **Explore** — Entry navigation page
- **Chat** — Desktop chat interface (streaming, Markdown, virtual scrolling)
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

### Frontend tests

```bash
cd frontend
npm test        # Vitest unit tests
npm run e2e     # Playwright E2E tests
```

See [`frontend/README.md`](frontend/README.md) for more details.

## Backend tests

```bash
uv run pytest tests/ -v
```

## Implementation Phases

- [x] Phase 1: Skeleton — model abstraction + chat service
- [x] Phase 2: Data connection — datasource abstraction + SQL generation & execution
- [x] Phase 3: RAG & Agent framework — knowledge base + multi-agent collaboration
- [x] Phase 4: Workflow orchestration & sandbox safety — AWEL + Sandbox
