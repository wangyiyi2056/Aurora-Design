# Aurora Platform -- Product Requirements Specification

> Version: 0.2.0 | Last Updated: 2026-05-20 | Status: Based on Actual Implementation

## 1. Product Overview

Aurora is an **Agentic AI Data Platform** that provides a unified interface for data analysis, knowledge management, workflow orchestration, and intelligent agent execution. It combines a Python backend (FastAPI + uv workspace monorepo) with a React 18 + TypeScript frontend (Vite + Electron desktop app).

### 1.1 Core Value Proposition

- **Data Dialogue**: Chat with databases using natural language, auto-generate SQL, visualize results
- **Knowledge RAG**: Upload documents, build vector-indexed knowledge bases, query with retrieval-augmented generation
- **Agent Orchestration**: 16+ built-in skills (SQL, chart, anomaly detection, report generation), multi-round tool calling, subagent spawning
- **Workflow Engine**: AWEL DAG-based workflow with visual node-edge editor
- **Dual Mode**: BI mode (web, read-only data analysis) and CODE mode (desktop, full engineering tools)

### 1.2 Glossary

| Term | Definition |
|------|-----------|
| `SystemApp` | Lightweight IoC container managing component lifecycle |
| `BaseLLM` | Abstract interface for LLM providers (achat, achat_stream) |
| `BaseConnector` | Abstract interface for database connectors |
| `BaseSkill` | Abstract interface for agent skills |
| `SessionManager` | JSONL-based session persistence with checkpoint/rollback |
| `MemoryManager` | Markdown-file-based persistent memory system |
| `HookManager` | Pre/Post tool use hook system (shell + Python) |
| `ContextCompactor` | Token-aware context window management |
| `PromptBuilder` | Multi-section system prompt assembler with cache boundaries |
| `ToolOrchestrator` | Concurrency-aware tool execution (parallel reads, serial writes) |
| `CostTracker` | Per-model token accounting and cost tracking |
| `ChatSSEState` | Frontend SSE streaming parser |
| `ProviderStore` | Zustand store for LLM provider config (daemon/API modes) |
| `SSE` | Server-Sent Events for streaming responses |
| `BYOK` | Bring Your Own Key -- user provides their own LLM API keys |
| `AWEL` | Aurora Workflow Expression Language -- DAG workflow engine |
| `MCP` | Model Context Protocol -- external tool server integration |

---

## 2. System Architecture

### 2.1 Package Structure

```
aurora-app (entry point)
  └── aurora-serve (FastAPI service layer)
        ├── aurora-core (framework: models, tools, sessions, memory, hooks, prompts)
        └── aurora-ext (RAG pipeline, ChromaDB vector store, AWEL operators)
sandbox (standalone Docker code executor, port 9000)
frontend (React 18 + TypeScript + Vite + Electron)
```

### 2.2 Backend Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    FastAPI Gateway (:8888)                │
│  CORS | Swagger/OpenAPI | 17 Sub-routers                │
├─────────────────────────────────────────────────────────┤
│                    Service Layer (aurora-serve)           │
│  ChatService │ DatasourceService │ KnowledgeService      │
│  SkillService │ FlowService │ AppService │ ModelService  │
│  FileService │ PromptService │ PluginService │ EvalService│
│  ProviderService │ FeedbackService │ TraceService        │
├─────────────────────────────────────────────────────────┤
│                    Core Framework (aurora-core)           │
│  ModelRegistry │ ToolSystem │ SessionManager             │
│  MemoryManager │ HookManager │ ContextCompactor          │
│  PromptBuilder │ PermissionManager │ PlanEnforcer        │
│  SubagentManager │ CostTracker │ MCPClient               │
├─────────────────────────────────────────────────────────┤
│                    Extension Layer (aurora-ext)           │
│  RAG Pipeline │ ChromaVectorStore │ AWEL Operators       │
├─────────────────────────────────────────────────────────┤
│                    Storage                                 │
│  SQLite (metadata) │ JSONL (sessions) │ ChromaDB (vectors)│
│  Markdown (memory) │ File system (uploads)                │
└─────────────────────────────────────────────────────────┘
```

### 2.3 Frontend Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    React 18 + TypeScript SPA              │
│  BrowserRouter │ AppProviders (Query, I18n, Toaster)     │
├─────────────────────────────────────────────────────────┤
│  Shell Layout (Sidebar + Content Area)                   │
│  ├── Sidebar: BrandLogo, Nav (Explore/Chat/Construct),   │
│  │   ConversationList, Theme/Language toggles            │
│  └── Pages: Explore │ Chat │ Construct (8 tabs) │ Eval   │
├─────────────────────────────────────────────────────────┤
│  State: Zustand (global, chat, provider) + TanStack Query│
│  API: Axios client → Vite proxy → FastAPI backend        │
│  Streaming: SSE parser (daemon) + provider registry (BYOK)│
├─────────────────────────────────────────────────────────┤
│  UI: shadcn/ui + Radix UI + TailwindCSS + Lucide Icons  │
│  i18n: 16 locales, dual system (i18next + custom context)│
│  Desktop: Electron 35 (auto-start Python backend)        │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Functional Requirements

### 3.1 Configuration Management

**TOML-based configuration** loaded at startup from `configs/aurora.toml` or `~/.aurora/config.toml`.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `app_name` | string | "Aurora" | Application name |
| `debug` | bool | true | Debug mode |
| `host` | string | "0.0.0.0" | Server bind address |
| `port` | int | 8888 | Server port |
| `default_llm` | string | "gpt-4o-mini" | Default model name |
| `llm_configs` | array | - | Model configurations |
| `embedding_configs` | array | - | Embedding model configs |
| `datasource_configs` | array | - | Default datasource configs |

Environment variables override via `AURORA_` prefix (Pydantic BaseSettings).

### 3.2 Multi-Provider LLM Support

The platform supports 5 LLM provider types via adapter pattern:

| Provider | Adapter Class | Transport | Streaming |
|----------|--------------|-----------|-----------|
| OpenAI | `OpenAILLM` | openai SDK (AsyncOpenAI) | SSE line parsing |
| Anthropic | `AnthropicLLM` | raw httpx | Messages API streaming |
| Google | `GoogleLLM` | raw httpx | Gemini API |
| Azure | `OpenAILLM` | AsyncAzureOpenAI | SSE line parsing |
| CLI Daemon | `LocalCliLLM` | subprocess | SSE via /providers/runs |

All adapters implement `BaseLLM` with `achat()` (non-streaming) and `achat_stream()` (async iterator). Retry with exponential backoff via `@retry_on_transient` decorator.

### 3.3 Chat Service

**Endpoint**: `POST /api/v1/chat/completions`

**Capabilities**:
- OpenAI-compatible request/response format
- Streaming (SSE) and non-streaming modes
- Multi-round tool calling (up to 5 rounds per request)
- Context compaction between rounds (200K token limit, 80% warning, 90% compact)
- Intent routing: SQL queries, knowledge RAG, agent tasks, Excel/CSV analysis, general chat
- System prompt assembly via `PromptBuilder` (mode-aware: BI vs CODE)
- Session persistence via `SessionManager` (JSONL files)
- Cost tracking per model per request

**SSE Event Types**:
- `text_start`, `text_delta`, `text_end`
- `reasoning_start`, `reasoning_delta`, `reasoning_end`
- `tool_call_start`, `tool_call_result`
- `pipeline_step`

**ReAct Agent**: `POST /api/v1/chat/react-agent` -- DB-GPT compatible streaming agent for tabular report analysis.

### 3.4 Session Management

**Storage**: JSONL files under `~/.aurora/sessions/` with `.meta.json` metadata.

| Operation | Endpoint | Description |
|-----------|----------|-------------|
| Create | `POST /chat/sessions` | Create new session |
| List | `GET /chat/sessions` | List all sessions |
| Load | `GET /chat/sessions/{id}` | Load session with full message history |
| Delete | `DELETE /chat/sessions/{id}` | Delete session |
| Rename | `PATCH /chat/sessions/{id}/title` | Update session title |

Features: checkpoint/rollback, session forking, auto-title derivation from first user message, cleanup of old sessions.

### 3.5 Memory System

**Storage**: Markdown files under `~/.aurora/memory/` and `.aurora/memory/` with `MEMORY.md` index.

| Memory Type | Purpose |
|-------------|---------|
| `USER` | User role, preferences, expertise |
| `FEEDBACK` | Behavioral corrections and confirmations |
| `PROJECT` | Ongoing work context, decisions |
| `REFERENCE` | Pointers to external resources |

Limits: 200 lines / 25KB per memory. Frontmatter-based metadata (name, description, type).

### 3.6 Tool System

**21 built-in tools** ported from Claude Code architecture:

| Category | Tools |
|----------|-------|
| File I/O | Read, Write, Edit, Glob, Grep |
| Execution | Bash, NotebookEdit |
| Web | WebFetch, WebSearch |
| Agent | Agent (subagent spawn), TaskOutput, SendMessage |
| Planning | EnterPlanMode, ExitPlanMode |
| User | AskUserQuestion |
| System | Skill, TodoWrite, TaskCreate/Get/Update/List/Stop, LSP |

**Execution Model**:
- Read-only tools run in parallel (`asyncio.gather`)
- Write tools run serially
- Full lifecycle: find tool → validate input → check permissions → execute → yield results
- Permission modes: DEFAULT, ACCEPT_EDITS, PLAN, AUTO

### 3.7 Hooks System

Loaded from `~/.aurora/settings.json` and `.aurora/settings.json`.

| Hook Type | Trigger |
|-----------|---------|
| `PRE_TOOL_USE` | Before tool execution |
| `POST_TOOL_USE` | After tool execution |
| `STOP` | Session end |
| `SESSION_START` | Session begin |
| `SESSION_END` | Session close |
| `USER_PROMPT_SUBMIT` | User sends message |

Supports shell command hooks and Python function hooks with regex matcher patterns.

### 3.8 Subagent System

Definitions loaded from `.aurora/agents/*.md` files. Each subagent has:
- Name, description, system prompt
- Limited tool set
- Optional model override
- Max context tokens (default 50K)
- Timeout (default 300s)

Supports parallel execution via `execute_parallel()`.

### 3.9 Datasource Management

**Supported Databases**: SQLite, DuckDB, PostgreSQL, MySQL

| Operation | Endpoint |
|-----------|----------|
| Create | `POST /api/v1/datasource` |
| List | `GET /api/v1/datasource` |
| Get | `GET /api/v1/datasource/{name}` |
| Update | `PUT /api/v1/datasource/{name}` |
| Delete | `DELETE /api/v1/datasource/{name}` |
| Test | `POST /api/v1/datasource/{name}/test` |
| Tables | `GET /api/v1/datasource/{name}/tables` |
| Schema | `GET /api/v1/datasource/{name}/schema/{table}` |
| Query | `POST /api/v1/datasource/{name}/query` |

**SQL Agent**: Natural language → SQL generation with keyword detection, LLM-based generation, and retry (up to 2 retries).

### 3.10 Knowledge Base & RAG

**Pipeline**: Document → Chunk → Embed → Store (ChromaDB) → Retrieve → Inject into context

| Operation | Endpoint |
|-----------|----------|
| Upload | `POST /api/v1/knowledge/upload` |
| List | `GET /api/v1/knowledge` |
| Get | `GET /api/v1/knowledge/{name}` |
| Documents | `GET /api/v1/knowledge/{name}/documents` |
| Delete Doc | `DELETE /api/v1/knowledge/{name}/documents/{id}` |
| Delete KB | `DELETE /api/v1/knowledge/{name}` |
| Query | `POST /api/v1/knowledge/{name}/query` |

**Chunking**: Configurable strategy, chunk_size (default 500), chunk_overlap (default 50). Fixed-size chunking with overlap.

**Vector Store**: ChromaDB (persistent or in-memory) with distance-scored search.

### 3.11 Skills System

**16 built-in skills** registered via `SkillService`:

| Skill | Category | Description |
|-------|----------|-------------|
| SQLExecuteSkill | Data | Execute SQL queries |
| DatabaseSchemaSkill | Data | Get database schema |
| PythonAnalysisSkill | Data | Python code analysis |
| CSVAnalysisSkill | Data | CSV file analysis |
| Excel2TableSkill | Data | Excel to table conversion |
| ExcelAnalysisSkill | Data | Excel file analysis |
| SQLChartSkill | Chart | Generate charts from SQL |
| SQLDashboardSkill | Chart | Generate dashboards |
| AnomalyDetectionSkill | Analysis | Detect data anomalies |
| IndicatorSkill | Analysis | Calculate indicators |
| MetricInfoSkill | Analysis | Metric information |
| VolatilityAnalysisSkill | Analysis | Volatility analysis |
| ReportSkill | Other | Generate reports |
| WebSearchSkill | Other | Web search |
| DatabaseSummarySkill | Other | Database summary |
| DataAnalysisSkill | Other | General data analysis |

### 3.12 AWEL Workflow Engine

**Core Primitives**: `BaseOperator`, `MapOperator`, `BranchOperator`, `DAG`, `DAGBuilder`, `DAGExecutor`, `TaskScheduler`

| Operation | Endpoint |
|-----------|----------|
| List operators | `GET /api/v1/awel/operators` |
| Create flow | `POST /api/v1/awel/flows` |
| List flows | `GET /api/v1/awel/flows` |
| Get flow | `GET /api/v1/awel/flows/{id}` |
| Update flow | `PUT /api/v1/awel/flows/{id}` |
| Delete flow | `DELETE /api/v1/awel/flows/{id}` |
| Run flow | `POST /api/v1/awel/flows/{id}/run` |
| Run history | `GET /api/v1/awel/flows/{id}/runs` |
| Get run | `GET /api/v1/awel/runs/{id}` |

Features: cycle detection, topological-order execution, parallel coroutine scheduling, inter-operator data passing.

### 3.13 MCP Integration

**Configuration**: `~/.aurora/mcp.json` with server definitions (name, command, args, env).

`MCPClient` manages connections via JSON-RPC over stdin/stdout. Tools from MCP servers are merged into the tool pool alongside built-in tools.

### 3.14 Provider System (BYOK + Daemon)

**Two modes**:

1. **Daemon Mode**: Uses local CLI agents (Claude Code, Codex) discovered via `GET /providers/agents`. Runs via subprocess with SSE event streaming.

2. **API (BYOK) Mode**: User provides API keys for OpenAI, Anthropic, Azure, or Google. Streaming goes through backend proxy endpoints:
   - `POST /providers/proxy/openai/stream`
   - `POST /providers/proxy/anthropic/stream`
   - `POST /providers/proxy/azure/stream`
   - `POST /providers/proxy/google/stream`

### 3.15 Sandbox Code Execution

**Standalone service** on port 9000. Docker-based isolation.

| Spec | Value |
|------|-------|
| Image | `python:3.11-slim` |
| Network | `--network none` |
| Memory | `--memory 128m` |
| Timeout | 30 seconds |
| Workspace | Read-only mount |

Returns: stdout, stderr, exit_code, generated files (base64).

### 3.16 Additional Services

| Service | Endpoint Prefix | Purpose |
|---------|----------------|---------|
| Apps | `/apps` | App builder (chat/agent/RAG types with knowledge/datasource/skill bindings) |
| Files | `/files` | File upload/download management |
| Prompts | `/prompts` | Prompt template CRUD with variable rendering |
| Plugins | `/plugins` | Plugin registry with enable/disable |
| Evaluation | `/evaluation` | Evaluation datasets and tasks with status tracking |
| Feedback | `/feedback` | User feedback collection |
| Traces | `/traces` | Observability trace events |
| Users | `/users` | User account management |
| Models | `/models` | Model config CRUD with connection testing |
| Skills | `/skills` | Skill listing with metadata |
| Health | `/health` | Health check endpoint |

---

## 4. Frontend Requirements

### 4.1 Pages & Routes

| Route | Page | Key Features |
|-------|------|-------------|
| `/` | Explore | Landing page with shortcut cards to Chat, Datasource, Knowledge, Skills |
| `/chat` | Chat | Full streaming chat, session management, conversation sidebar, file attachments |
| `/share/:id` | Share | Read-only shared React Agent workspace view |
| `/construct/app` | App Builder | CRUD for AI apps with 3-step wizard |
| `/construct/database` | Database | Datasource management + SQL query runner |
| `/construct/knowledge` | Knowledge | KB upload, document management, chunking config, vector query |
| `/construct/flow` | Flow | AWEL workflow node-edge editor with run execution |
| `/construct/plugins` | Plugins | Plugin CRUD with enable/disable |
| `/construct/prompt` | Prompts | Template management with variable rendering |
| `/construct/skills` | Skills | Categorized skill browser (data/SQL/analysis/other) |
| `/construct/models` | Models | Dual-mode provider config (daemon/API) |
| `/models_evaluation` | Evaluation | Dataset and task CRUD with status tracking |

### 4.2 Chat System Architecture

**Message Parts**: `TextPart`, `ToolPart`, `ReasoningPart`, `StatusPart`

**Streaming Flow**:
1. Frontend sends `POST /api/v1/chat/completions` with `stream: true`
2. Daemon mode: Direct SSE from backend, parsed by `ChatSSEState`
3. BYOK mode: Frontend calls provider registry → backend proxy → provider API → SSE relay

**Components**: ChatPane, ChatComposer, ChatMessageList, AssistantMessage, MessageRenderer, ToolCard, ReasoningDisplay, ChartRenderer, CodeRenderers, HtmlPreview, DebugPipelinePanel

### 4.3 State Management

| Store | Key | Purpose |
|-------|-----|---------|
| `global-store` | theme, language, sidebarCollapsed | Global UI preferences |
| `chat-store` | messages, sessions, streamingParts, loading | Chat state |
| `provider-store` | mode, byok, apiProtocolConfigs | LLM provider config |

Server state via TanStack React Query (staleTime: 5min, retry: 1).

### 4.4 Theme System

- Dual theme: dark (default) and light
- CSS variables in `tokens.css` with shadcn-compatible aliases
- Flash prevention via inline script in `index.html` reading from localStorage
- Both `data-theme` attribute and Tailwind `dark` class maintained simultaneously
- Chat-specific gradient avatars, bubble styles, glass-morphism composer

### 4.5 i18n

**16 locales**: en, de, zh-CN, zh-TW, pt-BR, es-ES, ru, fa, ar, ja, ko, pl, hu, fr, uk, tr

Dual system: legacy i18next + custom React Context (`useI18n()` hook). RTL support for Arabic and Farsi.

### 4.6 Desktop (Electron)

- Auto-starts Python backend on random port
- Health check polling with 30 retries
- Window: 1400x900, minWidth 900, minHeight 600
- macOS frameless title bar (`hiddenInset`)
- IPC: `window.electronAPI.getBackendUrl()`
- Build targets: macOS (dmg), Windows (nsis), Linux (AppImage)

---

## 5. Non-Functional Requirements

### 5.1 Performance

| Concern | Approach |
|---------|----------|
| Streaming | SSE for real-time chat responses |
| Context Management | Token-aware compaction (200K limit, auto-compact at 90%) |
| Tool Execution | Parallel read-only tools, serial writes |
| Vector Search | ChromaDB with distance-scored retrieval |
| Frontend | Virtual scrolling (TanStack Virtual), manual chunk splitting |
| Retry | Exponential backoff for transient HTTP errors |

### 5.2 Security

| Concern | Approach |
|---------|----------|
| Sandbox | Docker isolation (--network none, --memory 128m, read-only) |
| Permissions | Hierarchical config (global → user → project), sensitive file detection |
| API Keys | Environment variable or TOML config (never hardcoded in source) |
| CORS | Allow-all middleware (development mode) |
| HTML Sanitization | DOMPurify for rendered content |

### 5.3 Testing

| Layer | Framework | Coverage |
|-------|-----------|----------|
| Backend Unit | pytest + pytest-asyncio | Core services, models, tools |
| Frontend Unit | Vitest + Testing Library | Components, stores, utils, SSE parser |
| E2E | Playwright (chromium + mobile) | Chat, Construct, Explore pages |
| Visual | Playwright screenshots | 17 reference screenshots |

### 5.4 Storage

| Data | Storage | Location |
|------|---------|----------|
| Metadata | SQLite (SQLAlchemy ORM) | `data/aurora.db` |
| Sessions | JSONL files | `~/.aurora/sessions/` |
| Memory | Markdown files | `~/.aurora/memory/` + `.aurora/memory/` |
| Vectors | ChromaDB | `data/chroma/` |
| Uploads | File system | `data/uploads/` |
| Config | TOML + JSON | `configs/aurora.toml`, `~/.aurora/settings.json`, `~/.aurora/mcp.json` |
| Subagents | Markdown files | `.aurora/agents/*.md` |

---

## 6. Complete API Endpoint Map

All endpoints prefixed with `/api/v1`.

### Chat & Sessions
```
POST   /chat/completions              # Main chat (streaming/non-streaming)
POST   /chat/react-agent              # ReAct agent stream
POST   /chat/sessions                 # Create session
GET    /chat/sessions                 # List sessions
GET    /chat/sessions/{id}            # Load session
DELETE /chat/sessions/{id}            # Delete session
PATCH  /chat/sessions/{id}/title      # Update title
```

### Datasource
```
POST   /datasource                    # Create datasource
GET    /datasource                    # List all
GET    /datasource/{name}             # Get details
PUT    /datasource/{name}             # Update
DELETE /datasource/{name}             # Delete
POST   /datasource/{name}/test        # Test connection
GET    /datasource/{name}/tables      # List tables
GET    /datasource/{name}/schema/{t}  # Get DDL
POST   /datasource/{name}/query       # Execute SQL
POST   /datasource/test-connection    # Test raw config
```

### Knowledge
```
POST   /knowledge/upload              # Upload file
GET    /knowledge                     # List KBs
GET    /knowledge/{name}              # Get KB detail
GET    /knowledge/{name}/documents    # List documents
DELETE /knowledge/{name}/documents/{id} # Delete document
DELETE /knowledge/{name}              # Delete KB
POST   /knowledge/{name}/query        # RAG query
```

### AWEL Workflows
```
GET    /awel/operators                # List operators
POST   /awel/run                      # Legacy run
GET    /awel/flows                    # List flows
POST   /awel/flows                    # Create flow
GET    /awel/flows/{id}               # Get flow
PUT    /awel/flows/{id}               # Update flow
DELETE /awel/flows/{id}               # Delete flow
POST   /awel/flows/{id}/run           # Execute flow
GET    /awel/flows/{id}/runs          # List runs
GET    /awel/runs/{id}                # Get run
```

### Providers
```
GET    /providers/agents              # Detect local CLI agents
POST   /providers/runs                # Create CLI agent run
GET    /providers/runs/{id}/events    # SSE stream for run events
POST   /providers/runs/{id}/cancel    # Cancel run
POST   /providers/proxy/openai/stream
POST   /providers/proxy/anthropic/stream
POST   /providers/proxy/azure/stream
POST   /providers/proxy/google/stream
```

### CRUD Services
```
/models      GET, POST, PUT /{id}, DELETE /{id}, POST /test, POST /{id}/test
/files       POST /upload, GET, GET /raw, GET /{id}, GET /{id}/download, DELETE /{id}
/prompts     GET, POST, GET /{id}, PUT /{id}, DELETE /{id}, POST /{id}/render
/plugins     GET, POST, GET /{id}, PUT /{id}, POST /{id}/enable, POST /{id}/disable, DELETE /{id}
/apps        GET, POST, PUT /{id}, DELETE /{id}, POST /{id}/publish, POST /{id}/run
/evaluation  POST|GET /datasets, GET|PUT|DELETE /datasets/{id}, POST|GET /tasks, GET|PUT|DELETE /tasks/{id}
/feedback    POST, GET, GET /{id}, PUT /{id}, DELETE /{id}
/traces      POST, GET, GET /{id}, PUT /{id}, DELETE /{id}
/users       POST, GET, GET /{id}, PUT /{id}, DELETE /{id}
/skills      GET
/agent       GET /skills
/health      GET
```

---

## 7. Technology Stack

### Backend
| Component | Technology |
|-----------|-----------|
| Language | Python 3.10+ |
| Framework | FastAPI |
| Server | Uvicorn |
| ORM | SQLAlchemy |
| Database | SQLite |
| Vector Store | ChromaDB |
| LLM SDK | openai, httpx (for Anthropic/Google) |
| Validation | Pydantic v2 |
| Config | TOML (tomllib/tomli) |
| Package Manager | uv (workspace monorepo) |

### Frontend
| Component | Technology |
|-----------|-----------|
| Language | TypeScript 5 |
| Framework | React 18.2 |
| Build Tool | Vite 7.3 |
| State | Zustand 5.0 + TanStack React Query 5.99 |
| Routing | React Router DOM 6.22 |
| UI Library | shadcn/ui + Radix UI (8 primitives) |
| Styling | TailwindCSS 3.4 |
| Icons | Lucide React |
| Charts | ECharts 6.0 |
| Markdown | react-markdown + remark-gfm |
| Forms | React Hook Form 7.72 + Zod 4.3 |
| i18n | i18next 26.0 + react-i18next 17.0 |
| Desktop | Electron 35.0 |
| Testing | Vitest 4.1 + Playwright 1.59 |
