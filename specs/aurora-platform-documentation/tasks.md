# Aurora Platform -- Implementation Status & Tasks

> Version: 0.2.0 | Last Updated: 2026-05-20 | Status: Based on Actual Codebase Audit

## Legend

| Status | Meaning |
|--------|---------|
| DONE | Fully implemented and working |
| PARTIAL | Core functionality exists, gaps remain |
| STUB | API/UI exists but implementation is minimal |
| TODO | Not yet implemented |

---

## Phase 1: Core Framework (aurora-core)

### Configuration System
- [x] TOML config loader (`config/loader.py`)
- [x] Pydantic Settings with env override (`config/settings.py`)
- [x] BaseParameters dataclass (`config/base.py`)
- [ ] **TODO**: Config validation with detailed error reporting
- [ ] **TODO**: Hot-reload config without restart

### Model Abstraction
- [x] BaseLLM abstract interface (`model/base.py`)
- [x] BaseEmbeddings abstract interface
- [x] OpenAI adapter with streaming (`model/adapter/openai_adapter.py`)
- [x] Anthropic adapter with streaming (`model/adapter/anthropic_adapter.py`)
- [x] Google adapter (`model/adapter/google_adapter.py`)
- [x] CLI daemon adapter (`model/adapter/cli_adapter.py`)
- [x] OpenAI embeddings adapter
- [x] Model registry with dict-based storage (`model/registry.py`)
- [x] Retry decorator with exponential backoff (`utils/retry.py`)

### Component System
- [x] SystemApp IoC container (`component/app.py`)
- [x] Lifecycle hooks (on_init, after_init, before_stop)
- [x] BaseComponent and BaseService base classes
- [x] ComponentRegistry (`component/registry.py`)

### Session Management
- [x] SessionMessage with JSONL serialization (`session/schema.py`)
- [x] Session with checkpoint/rollback support
- [x] SessionManager with full CRUD (`session/manager.py`)
- [x] Auto-title derivation from first user message
- [x] Session forking
- [x] Old session cleanup

### Memory System
- [x] MemoryType enum (USER, FEEDBACK, PROJECT, REFERENCE) (`memory/schema.py`)
- [x] MemoryEntry with Markdown frontmatter serialization
- [x] MemoryManager with CRUD (`memory/manager.py`)
- [x] MEMORY.md index file maintenance
- [x] Size limits (200 lines / 25KB)

### Hooks System
- [x] HookType enum (6 types) (`hooks/schema.py`)
- [x] HookMatcher with regex matching
- [x] HookManager with shell + Python hooks (`hooks/manager.py`)
- [x] Load from ~/.aurora/settings.json and .aurora/settings.json

### Context Management
- [x] ContextCompactor with 200K token limit (`context/compaction.py`)
- [x] Thrashing detection
- [x] ContextMonitor with token tracking (`context/monitor.py`)
- [x] ToolSearchManager for on-demand tool loading (`context/tool_search.py`)

### Tool System
- [x] Tool ABC with full metadata (`tool/base.py`)
- [x] ToolResult, ToolUseContext, ToolPermissionContext
- [x] 21 built-in tools (`tool/tools/`)
- [x] ToolRegistry (`tool/registry.py`)
- [x] Tool executor with lifecycle (`tool/executor.py`)
- [x] Concurrency-aware orchestrator (`tool/orchestrator.py`)

### Agent System
- [x] BaseAgent ABC (`agent/base.py`)
- [x] BaseSkill ABC with SkillRegistry (`agent/skill/base.py`)
- [x] Team manager (`agent/team/manager.py`)
- [x] Resource abstraction (`agent/resource/base.py`)

### Subagent System
- [x] SubagentDefinition with Markdown serialization (`subagents/definition.py`)
- [x] SubagentManager with execute + execute_parallel (`subagents/manager.py`)
- [x] Load from .aurora/agents/*.md

### Permissions System
- [x] PermissionMode enum (`permissions/mode.py`)
- [x] PermissionManager with hierarchical config (`permissions/manager.py`)
- [x] Sensitive file detection

### Plan Mode
- [x] PlanEnforcer restricting to read-only tools (`plan/enforcer.py`)

### Operational Modes
- [x] ChatMode enum (BI/CODE) (`mode.py`)
- [x] Tool filtering per mode

### AWEL Engine
- [x] BaseOperator with >> wiring (`awel.py`)
- [x] MapOperator, BranchOperator
- [x] DAG with cycle detection
- [x] DAGBuilder fluent API
- [x] DAGExecutor with topological order
- [x] TaskScheduler for parallel execution

### Prompt System
- [x] PromptBuilder with multi-section assembly (`prompt/builder.py`)
- [x] Cache boundary (DYNAMIC_BOUNDARY)
- [x] BI and CODE mode sections
- [x] ContextProvider for runtime context (`prompt/context.py`)

### Status / Cost Tracking
- [x] StatusData models (`status/models.py`)
- [x] CostTracker with per-model accounting (`status/tracker.py`)
- [x] MODEL_PRICING for 6 models

### MCP Integration
- [x] MCPServerConfig and MCPConfig (`mcp/config.py`)
- [x] MCPClient with JSON-RPC over stdin/stdout (`mcp/client.py`)
- [x] Multi-connection management

### Other Core Modules
- [x] LSP handler (`lsp/handler.py`)
- [x] QueryEngine (`query/engine.py`)
- [x] Skill loader (`skills/loader.py`)

---

## Phase 2: Service Layer (aurora-serve)

### Server & Router
- [x] FastAPI factory with lifespan (`server.py`)
- [x] CORS middleware
- [x] 17 sub-router aggregation (`router.py`)
- [x] Component initialization on startup

### Metadata / Database
- [x] SQLAlchemy ORM with SQLite (`metadata.py`)
- [x] 15 entity classes (ModelConfig, Datasource, KnowledgeBase, etc.)
- [x] Auto table creation on startup

### Chat Service
- [x] POST /chat/completions (streaming + non-streaming) (`chat/api.py`)
- [x] POST /chat/react-agent (DB-GPT compatible)
- [x] Session CRUD endpoints
- [x] Multi-round tool calling (up to 5 rounds) (`chat/service.py`)
- [x] Context compaction between rounds
- [x] Excel/CSV analysis pipeline
- [x] SQL agent integration
- [x] Knowledge RAG context injection
- [x] Memory context injection
- [x] System prompt building
- [x] SSE streaming with typed events
- [x] Session persistence
- [x] Cost tracking
- [x] Plan mode enforcement

### Datasource Service
- [x] CRUD endpoints (`datasource/api.py`)
- [x] Connection testing
- [x] Table listing and schema retrieval
- [x] SQL query execution
- [x] SQLite, DuckDB, PostgreSQL, MySQL connectors (`datasource/service.py`)

### Knowledge Service
- [x] Upload endpoint with chunk config (`knowledge/api.py`)
- [x] CRUD for knowledge bases and documents
- [x] RAG query endpoint
- [x] RAG pipeline integration (`knowledge/service.py`)

### Agent Service
- [x] GET /agent/skills endpoint (`agent/api.py`)
- [x] SQLAgent with NL→SQL generation (`agent/sql_agent.py`)

### Skills Service
- [x] 16 built-in skills registered (`skills/service.py`)
- [x] GET /skills endpoint (`skills/api.py`)
- [x] Individual skill implementations (data, chart, analysis, other)

### AWEL Service
- [x] Flow CRUD endpoints (`awel/api.py`)
- [x] Flow execution with run tracking
- [x] Run history endpoints
- [x] FlowService implementation (`awel/service.py`)

### Models Service
- [x] CRUD for model configs (`models/api.py`)
- [x] Connection testing for all provider types

### Other Services
- [x] Files: upload, list, download, delete (`files/api.py`)
- [x] Prompts: CRUD + render (`prompt/api.py`)
- [x] Plugins: CRUD + enable/disable (`plugins/api.py`)
- [x] Apps: CRUD + publish + run (`apps/api.py`)
- [x] Evaluation: datasets + tasks CRUD (`evaluation/api.py`)
- [x] Feedback: CRUD (`feedback/api.py`)
- [x] Traces: CRUD (`traces/api.py`)
- [x] Users: CRUD (`users/api.py`)
- [x] Providers: agent detection, CLI runs, BYOK proxy (`providers/api.py`)
- [x] Health: GET /health (`health/api.py`)

---

## Phase 3: Extension Layer (aurora-ext)

### RAG Pipeline
- [x] Document dataclass (`rag/knowledge/base.py`)
- [x] KnowledgeFactory (`rag/knowledge/factory.py`)
- [x] ChunkManager with fixed-size splitting (`rag/transformer/chunk.py`)
- [x] EmbeddingAssembler (`rag/assembler/embedding_assembler.py`)
- [x] EmbeddingRetriever (`rag/retriever/embedding_retriever.py`)
- [x] BM25Retriever (`rag/retriever/bm25_retriever.py`)

### Vector Store
- [x] VectorStoreBase ABC (`storage/base.py`)
- [x] ChromaVectorStore (`storage/chroma_store.py`)

### AWEL Operators
- [x] Base operator (`rag/operators/base.py`)
- [x] Load operator (`rag/operators/load_operator.py`)
- [x] Storage operator (`rag/operators/storage_operator.py`)

---

## Phase 4: Sandbox

- [x] Standalone FastAPI server (`sandbox/api/server.py`)
- [x] DockerCodeExecutor (`sandbox/executor/docker.py`)
- [x] POST /execute endpoint
- [x] Security: --network none, --memory 128m, read-only
- [x] 30s timeout
- [x] ExecutionResult with stdout/stderr/exit_code/files

---

## Phase 5: Frontend -- Infrastructure

### Project Setup
- [x] Vite + React 18 + TypeScript 5
- [x] TailwindCSS with shadcn/ui
- [x] Radix UI primitives (8 components)
- [x] Path alias (@/ → src/)
- [x] Manual chunk splitting (vendor-react, vendor-query, vendor-markdown)

### State Management
- [x] Global store (theme, language, sidebar) (`stores/global-store.ts`)
- [x] Chat store (messages, sessions, streaming) (`stores/chat-store.ts`)
- [x] Provider store (daemon/API mode, BYOK config) (`stores/provider-store.ts`)
- [x] TanStack React Query for server state

### API Client
- [x] Axios client with interceptors (`lib/api-client.ts`)
- [x] Vite proxy /api → localhost:8888
- [x] 12 service modules (`services/`)

### Theme System
- [x] Dark/light themes via CSS variables (`styles/tokens.css`)
- [x] Flash prevention inline script
- [x] useTheme hook
- [x] data-theme + dark class dual maintenance

### i18n
- [x] 16 locales supported
- [x] Legacy i18next system
- [x] Custom React Context system
- [x] RTL support for Arabic/Farsi

### Streaming
- [x] ChatSSEState SSE parser (`features/chat/utils/sse-parser.ts`)
- [x] Provider registry for BYOK streaming (`providers/registry.ts`)
- [x] SSE frame parsing (`providers/sse.ts`)
- [x] API proxy client (`providers/api-proxy.ts`)

---

## Phase 6: Frontend -- Pages

### Explore Page
- [x] Landing page with shortcut cards (`features/chat/pages/explore-page.tsx`)
- [x] Navigation to Chat, Datasource, Knowledge, Skills

### Chat Page
- [x] Full streaming chat interface (`features/chat/pages/chat-page.tsx`)
- [x] ChatPane with message list and composer
- [x] AssistantMessage with tool cards, reasoning, status
- [x] MessageRenderer with Markdown + code highlighting
- [x] ChartRenderer with ECharts
- [x] HtmlPreview with sandboxed iframe
- [x] Conversation list sidebar
- [x] Session management (create, load, delete, rename)
- [x] File attachments
- [x] Abort/cancel streaming
- [x] Debug pipeline panel
- [x] React Agent Workspace

### Share Page
- [x] Read-only shared workspace view (`features/chat/pages/share-page.tsx`)

### Construct Pages (8 tabs)
- [x] ConstructShell with tab navigation (`features/construct/components/construct-shell.tsx`)
- [x] App Builder: 3-step wizard (`features/construct/app/`)
- [x] Database: datasource CRUD + SQL runner (`features/construct/database/`)
- [x] Knowledge: upload, docs, chunking config, query (`features/construct/knowledge/`)
- [x] Flow: AWEL workflow management (`features/construct/flow/`)
- [x] Plugins: CRUD + enable/disable (`features/construct/plugins/`)
- [x] Prompts: template management + render (`features/construct/prompt/`)
- [x] Skills: categorized browser + detail dialog (`features/construct/skills/`)
- [x] Models: dual-mode provider config (`features/construct/models/`)

### Evaluation Page
- [x] Dataset and task CRUD (`features/evaluation/pages/evaluation-list-page.tsx`)
- [x] Status tracking

### Mobile Support
- [x] MobileNav component (`features/mobile/components/mobile-nav.tsx`)
- [x] useIsMobile hook (767px breakpoint)
- [x] Responsive sidebar
- [x] Responsive chat CSS

---

## Phase 7: Desktop (Electron)

- [x] Main process with Python backend auto-start (`electron/main.ts`)
- [x] Health check polling
- [x] IPC for backend URL (`electron/preload.ts`)
- [x] Window configuration (1400x900, frameless)
- [x] electron-builder config (dmg/nsis/AppImage)

---

## Phase 8: Testing

### Backend Tests
- [x] pytest + pytest-asyncio setup
- [ ] **TODO**: Comprehensive unit tests for core services
- [ ] **TODO**: Integration tests for API endpoints
- [ ] **TODO**: Tool system tests

### Frontend Unit Tests (Vitest)
- [x] assistant-message.test.tsx
- [x] chart-renderer.test.tsx
- [x] react-agent-workspace.test.tsx
- [x] react-agent-workspace.test.ts (utils)
- [x] sse-parser.test.ts
- [x] chat-store.test.ts
- [x] global-store.test.ts
- [x] i18n.test.ts
- [x] cn.test.ts

### E2E Tests (Playwright)
- [x] chat.spec.ts
- [x] construct.spec.ts
- [x] explore.spec.ts
- [x] 17 reference screenshots

---

## Known Gaps & Improvement Areas

### Backend
1. **Test Coverage**: Backend lacks comprehensive unit/integration tests
2. **Config Validation**: No detailed error reporting for invalid TOML configs
3. **API Rate Limiting**: Not implemented
4. **Authentication**: No API key auth or user auth on endpoints
5. **Error Standardization**: Error response format not consistently enforced
6. **AWEL Operators**: Only identity/uppercase operators implemented
7. **Sandbox Integration**: Not fully wired into Chat/Agent services

### Frontend
1. **Accessibility**: No systematic a11y audit
2. **Error Boundaries**: No React error boundaries
3. **Offline Support**: No service worker or offline fallback
4. **Performance**: No Lighthouse audit or CWV tracking
5. **Test Coverage**: Only 9 test files, many components untested
6. **i18n Completeness**: Some hardcoded strings may remain

### Architecture
1. **No Authentication Layer**: All endpoints are open
2. **No API Versioning**: Single /api/v1 prefix, no version migration strategy
3. **No WebSocket**: Only SSE for streaming, no bidirectional communication
4. **No Caching Layer**: No Redis or in-memory cache for hot data
5. **No Background Jobs**: No task queue for long-running operations
6. **No Monitoring**: No APM, metrics, or structured logging

---

## Priority Tasks (Recommended Next Steps)

### P0 -- Critical
1. Add backend test coverage for ChatService, DatasourceService, KnowledgeService
2. Implement API authentication (API key or JWT)
3. Add input validation and sanitization across all endpoints

### P1 -- High
4. Add React error boundaries for graceful failure
5. Implement API rate limiting
6. Complete accessibility audit (keyboard nav, screen reader, contrast)
7. Add Lighthouse performance baseline

### P2 -- Medium
8. Expand AWEL operator library beyond identity/uppercase
9. Wire sandbox into Chat/Agent services
10. Add WebSocket support for bidirectional communication
11. Implement structured logging with trace IDs

### P3 -- Low
12. Add service worker for offline support
13. Implement API versioning strategy
14. Add background job queue (Celery/RQ)
15. Set up APM monitoring
