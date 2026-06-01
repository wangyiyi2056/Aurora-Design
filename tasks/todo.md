# RAG Enhancement Tasks

## Task 1: Extraction Tuning Parameters (P1-5)
- [x] Add new params to `EntityRelationExtractor.__init__()`
- [x] Add source ID trimming + file_paths limit in `merge_entities()` / `merge_relationships()`
- [x] Wire `force_llm_summary_on_merge` into merger

## Task 2: Query Tuning Parameters (P1-6)
- [x] Add `related_chunk_number`, `kg_chunk_pick_method`, `max_graph_nodes` to `QueryParam`
- [x] Implement WEIGHT-based chunk selection in query engine
- [x] Wire `related_chunk_number` limit and configurable `max_graph_nodes`

## Task 3: Reranking Enhancement (P1-4)
- [x] Add `RerankOptions` frozen dataclass
- [x] Add `AliyunReranker` class with DashScope API
- [x] Add score aggregation (max/mean/first)
- [x] Add exponential backoff retry
- [x] Add long-document chunking

## Task 4: Skip KG Extraction (P1-7)
- [x] Add skip_kg branch in `_process_worker()`
- [x] Verify parser routing `!` hint -> `skip_kg=True`

## Task 5: Filename Dedup + Audit (P1-8)
- [x] Add fields to `DocStatusInfo` in base.py
- [x] Add abstract methods to `BaseDocStatusStorage`
- [x] Implement in `JsonDocStatusStorage`
- [x] Add filename dedup in `upload_file()`
