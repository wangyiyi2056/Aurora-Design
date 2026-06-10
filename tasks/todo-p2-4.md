# P2-4: Custom Knowledge Graph Batch Injection

## Status: ✅ Complete

## Plan

- [x] 1. Create `CustomKGInjector` class (`custom_kg_injector.py`)
  - Define `MergeStrategy` enum (overwrite/merge/skip)
  - Define `ImportEntity` and `ImportRelationship` dataclasses
  - Define `InjectionStats` dataclass
  - Implement `inject()` method with batch upsert logic
  - Implement `_generate_entity_embeddings()` for auto embedding
  - Implement merge logic per strategy

- [x] 2. Add Pydantic schemas to `schemas.py`
  - `GraphImportEntity`, `GraphImportRelationship` (with alternate key validators)
  - `GraphImportRequest` (entities + relationships + merge_strategy)
  - `GraphImportResponse` + `GraphImportStats` (stats: created/updated/skipped)

- [x] 3. Add `import_graph()` method to `KnowledgeV2Service`
  - Wire `CustomKGInjector` with storage backends
  - Delegate injection to the injector class

- [x] 4. Add `POST /knowledge/{name}/graph/import` endpoint to `graph_routes.py`
  - Accept JSON body with entities, relationships, merge_strategy
  - Support YAML via Content-Type header parsing
  - Return injection statistics

- [x] 5. Create `__init__.py` for injection package

- [x] 6. Verify with compile check, ruff lint, and comprehensive tests

## Verification Results

- ✅ `py_compile` passes on all 5 modified/new files
- ✅ `ruff check` passes on all new files
- ✅ Unit tests: parsing, enum, stats, YAML parsing
- ✅ Integration tests: fresh injection, merge/overwrite/skip strategies,
  auto-create endpoints, no-embedding-func, relationship merge
- ✅ End-to-end tests: JSON flow, YAML flow, re-import merge, empty import
- ✅ Endpoint registered: `POST /graph/import`

## Files Changed

- **New:** `packages/aurora-ext/src/aurora_ext/rag/injection/__init__.py` (17 lines)
- **New:** `packages/aurora-ext/src/aurora_ext/rag/injection/custom_kg_injector.py` (579 lines)
- **Modified:** `packages/aurora-serve/src/aurora_serve/knowledge/v2/schemas.py` (+~120 lines)
- **Modified:** `packages/aurora-serve/src/aurora_serve/knowledge/v2/service.py` (+~100 lines for `import_graph`)
- **Modified:** `packages/aurora-serve/src/aurora_serve/knowledge/v2/graph_routes.py` (+~83 lines)
- **Modified:** `packages/aurora-serve/src/aurora_serve/knowledge/v2/__init__.py` (+6 exports)
