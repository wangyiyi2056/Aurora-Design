# Reranker Integration Enhancement

## Current Status
- ✅ Base interface (RerankerBase)
- ✅ CohereReranker implemented
- ✅ JinaReranker implemented
- ✅ AliyunReranker implemented (DashScope gte-rerank-v2)
- ✅ RerankOptions with chunking support
- ✅ Score aggregation (max/mean/first)
- ✅ Exponential backoff retry
- ✅ Integrated into query_engine._apply_rerank

## Tasks

### Phase 1: vLLM Support
- [ ] 1.1 Create VLLMReranker class (extends CohereReranker API compatibility)
- [ ] 1.2 Add vLLM-specific endpoint configuration
- [ ] 1.3 Test with mock vLLM server responses

### Phase 2: Configuration Management
- [ ] 2.1 Create RerankerConfig dataclass
- [ ] 2.2 Implement TOML config loader
- [ ] 2.3 Create reranker factory function
- [ ] 2.4 Add environment variable support
- [ ] 2.5 Document configuration options

### Phase 3: Enhanced Error Handling
- [ ] 3.1 Add graceful degradation on API failure
- [ ] 3.2 Implement rate limit detection and handling
- [ ] 3.3 Add circuit breaker pattern
- [ ] 3.4 Timeout improvements
- [ ] 3.5 Fallback to no-rerank on persistent failures

### Phase 4: Query Integration
- [ ] 4.1 Enable reranker by default in mix mode
- [ ] 4.2 Add reranker configuration to QueryEngine
- [ ] 4.3 Apply reranker after context building
- [ ] 4.4 Preserve original chunk order metadata

### Phase 5: Testing
- [ ] 5.1 Create test_reranker.py
- [ ] 5.2 Mock API responses for all reranker types
- [ ] 5.3 Test error scenarios (timeout, rate limit, API failure)
- [ ] 5.4 Test chunking and aggregation
- [ ] 5.5 Test factory function
- [ ] 5.6 Test query integration

### Phase 6: Documentation
- [ ] 6.1 Add docstrings to all classes
- [ ] 6.2 Create usage examples
- [ ] 6.3 Update README
- [ ] 6.4 Add configuration examples

## Implementation Notes
- vLLM reranker should be API-compatible with Cohere
- Configuration should support both TOML and environment variables
- Factory should auto-detect reranker type from config
- Error handling should never crash the query - fallback gracefully
- Tests should use pytest with async support
