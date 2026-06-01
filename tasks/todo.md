# RAG Model Layer Implementation

## Completed Tasks

### Task 1: LLM Role Registry (P1-1) ✅
**File**: `packages/aurora-core/src/aurora_core/model/roles.py`

- Created `LLMRole` enum with EXTRACT, KEYWORD, QUERY, VLM roles
- Created `RoleLLMConfig` frozen dataclass for role-specific configuration
- Created `LLMRoleRegistry` with:
  - Per-role LLM bindings with fallback to default
  - Independent `asyncio.Semaphore` per role for concurrency isolation
  - Thread-safe hot-swap via `asyncio.Lock`
  - `get_queue_status()` returning model_name, max_async, current_available

### Task 2: Azure OpenAI Adapter (P1-3) ✅
**Files**:
- `packages/aurora-core/src/aurora_core/model/adapter/azure_adapter.py`
- `packages/aurora-core/src/aurora_core/model/adapter/azure_embeddings.py`

**AzureOpenAILLM**:
- Uses `openai.AsyncAzureOpenAI` client
- Reads `api_version` and `deployment_name` from `LLMConfig.extra`
- Supports `AZURE_OPENAI_API_KEY` and `AZURE_OPENAI_ENDPOINT` env vars
- Full streaming support via `achat_stream()`
- Follows the same pattern as OpenAILLM

**AzureOpenAIEmbeddings**:
- Uses `openai.AsyncAzureOpenAI` client for embedding generation
- Same Azure configuration as the LLM adapter

### Task 3: Ollama Adapter (P1-3) ✅
**Files**:
- `packages/aurora-core/src/aurora_core/model/adapter/ollama_adapter.py`
- `packages/aurora-core/src/aurora_core/model/adapter/ollama_embeddings.py`

**OllamaLLM**:
- Uses raw HTTP API via `httpx.AsyncClient` (no SDK dependency)
- Base URL from `config.api_base` or `OLLAMA_BASE_URL` env var
- Non-streaming (`achat`) and streaming (`achat_stream`) support
- Supports `temperature` and `num_predict` (max_tokens)
- Graceful connection error handling

**OllamaEmbeddings**:
- POST `/api/embed` endpoint
- Returns `List[List[float]]`

### Task 4: Register New Adapters in server.py ✅
**File**: `packages/aurora-serve/src/aurora_serve/server.py`

- Added imports for `AzureOpenAILLM`, `OllamaLLM`, `OllamaEmbeddings`
- Added `model_type == "azure_openai"` branch
- Added `model_type == "ollama"` branch (registers both LLM and embeddings)

### Task 5: Embedding Cache (P1-2) ✅
**Files**:
- `packages/aurora-core/src/aurora_core/rag/utils/embedding_cache.py`
- `packages/aurora-core/src/aurora_core/rag/utils/embedding.py` (modified)

**EmbeddingCache**:
- Three-tier cache: exact → approximate → compute
- Exact match via SHA256 hash lookup
- Approximate match via cosine similarity (threshold configurable)
- LRU eviction when `max_cache_size` exceeded
- Thread-safe with `asyncio.Lock`
- Stats tracking: hits, misses, approximate_hits, evictions

**EmbeddingFunc Integration**:
- Added optional `cache: EmbeddingCache | None` parameter
- Checks cache before computing embeddings
- Stores computed embeddings in cache
- Added `cache` property for easy access

## Testing

All implementations tested:
- Syntax validation: All files compile successfully
- Unit tests: Cosine similarity, cache put/get, LRU eviction
- Integration tests: EmbeddingFunc with cache, role registry fallback
- Existing tests: `tests/core/test_model_registry.py` still passes

## Files Created

1. `packages/aurora-core/src/aurora_core/model/roles.py`
2. `packages/aurora-core/src/aurora_core/model/adapter/azure_adapter.py`
3. `packages/aurora-core/src/aurora_core/model/adapter/azure_embeddings.py`
4. `packages/aurora-core/src/aurora_core/model/adapter/ollama_adapter.py`
5. `packages/aurora-core/src/aurora_core/model/adapter/ollama_embeddings.py`
6. `packages/aurora-core/src/aurora_core/rag/utils/embedding_cache.py`

## Files Modified

1. `packages/aurora-serve/src/aurora_serve/server.py`
2. `packages/aurora-core/src/aurora_core/rag/utils/embedding.py`
