# Token Budget Control System - Implementation Plan

## Objective
Implement a fine-grained token budget control system in `aurora-ext/src/aurora_ext/rag/utils/token_tracker.py` to track and enforce token limits across LLM calls, embeddings, and context building.

## Architecture

```
TokenBudget (frozen dataclass)
├── max_entity_tokens: int = 5000
├── max_relation_tokens: int = 5000
├── max_total_tokens: int = 12000
└── max_chunk_tokens: int = 8000

TokenTracker
├── track_llm_call(prompt_tokens, completion_tokens)
├── track_embedding_call(tokens)
├── truncate_to_budget(entities, relations, chunks) -> Tuple
├── get_stats() -> dict
└── reset_stats()
```

## Integration Points

1. **QueryEngine** (`aurora-ext/src/aurora_ext/rag/retrieval/query_engine.py`)
   - Add `token_tracker: Optional[TokenTracker]` to `QueryParam`
   - Use tracker in `_finalize_context()` for budget enforcement
   - Track LLM calls in `_generate()` and `_stream_generate()`

2. **KnowledgeV2Service** (`aurora-serve/src/aurora_serve/knowledge/v2/service.py`)
   - Initialize `TokenTracker` in `__init__`
   - Pass to `QueryEngine` or store per-KB stats
   - Expose via `get_token_stats(kb_name)` method

3. **API Routes** (`aurora-serve/src/aurora_serve/knowledge/v2/query_routes.py`)
   - Add `GET /knowledge/{name}/token-stats` endpoint
   - Add `POST /knowledge/{name}/token-stats/reset` endpoint

4. **QueryParam** (`query_engine.py`)
   - Add `max_chunk_tokens: int = 8000` field
   - Add `track_usage: bool = False` field

## Implementation Tasks

- [x] **T1**: Create `rag/utils/` directory and `__init__.py`
- [x] **T2**: Implement `TokenBudget` frozen dataclass with all 4 budget fields
- [x] **T3**: Implement `TokenTracker` class with tracking methods
- [x] **T4**: Implement priority-based truncation logic (entities → relations → chunks)
- [x] **T5**: Write unit tests for `TokenBudget` (truncation, edge cases)
- [x] **T6**: Write unit tests for `TokenTracker` (tracking, stats, reset)
- [x] **T7**: Write unit tests for truncation priority logic
- [x] **T8**: Update existing `TokenBudget` in `retrieval/token_budget.py` (add `max_chunk_tokens`)
- [x] **T9**: Integrate `TokenTracker` into `QueryParam`
- [x] **T10**: Integrate tracking into `QueryEngine._finalize_context()`
- [x] **T11**: Add `get_token_stats()` and `reset_token_stats()` to `KnowledgeV2Service`
- [x] **T12**: Add API routes for token stats
- [x] **T13**: Update `__init__.py` exports
- [x] **T14**: Run tests and verify 80%+ coverage
- [x] **T15**: Commit all changes

## Design Decisions

### Priority Ordering
When truncating, preserve high-score content in this order:
1. **Entities** (highest priority) - critical for KG context
2. **Relations** - connect entities
3. **Chunks** (lowest priority) - raw text, can be trimmed aggressively

### Score-Based Sorting
- Each item sorted by `score` or `weight` field (descending)
- Items without score treated as score=0.0
- Truncation preserves complete items (no mid-sentence cuts within a single item)

### Budget Enforcement
- Total budget is a hard cap: entity + relation + chunk tokens ≤ max_total_tokens
- Per-category budgets are soft caps within the total
- If entities alone exceed max_total_tokens, truncate entities first

### Thread Safety
- `TokenTracker` is NOT thread-safe by design (one per request)
- Per-KB cumulative stats stored separately in service layer

## Configuration

```toml
[token_budget]
max_entity_tokens = 5000
max_relation_tokens = 5000
max_total_tokens = 12000
max_chunk_tokens = 8000
track_usage = true
```

## Test Coverage Targets

- TokenBudget: truncation by field, edge cases (empty, oversized)
- TokenTracker: LLM/embedding tracking, stats accuracy, reset
- Priority truncation: ordering, overflow handling
- Integration: QueryParam wiring, API endpoint responses

## Risk Assessment

- **Low Risk**: Pure utility class, no external dependencies
- **Medium Risk**: Integration with existing `token_budget.py` (avoid breaking changes)
- **Mitigation**: Keep existing `TokenBudget` in `retrieval/token_budget.py`, create new one in `utils/token_tracker.py` that extends functionality
