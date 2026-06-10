# Reranker Integration Guide

Comprehensive reranking support for RAG pipelines with multiple provider backends.

## Overview

The reranker module provides pluggable reranking services to improve retrieval quality by re-scoring and reordering retrieved documents based on relevance to the query.

### Supported Providers

| Provider | Model | Status | Notes |
|----------|-------|--------|-------|
| **Cohere** | `rerank-v3.5`, `rerank-multilingual-v3.0` | ✅ Production | Best-in-class multilingual reranking |
| **Jina AI** | `jina-reranker-v2-base-multilingual` | ✅ Production | Fast and accurate |
| **Aliyun DashScope** | `gte-rerank-v2` | ✅ Production | Chinese-optimized with chunking support |
| **vLLM** | `BAAI/bge-reranker-v2-m3` (self-hosted) | ✅ Production | Cohere-compatible API |

## Quick Start

### Basic Usage

```python
from aurora_ext.rag.retrieval import CohereReranker

# Initialize reranker
reranker = CohereReranker(
    api_key="your-api-key",
    model="rerank-multilingual-v3.0"
)

# Rerank documents
results = await reranker.rerank(
    query="What is machine learning?",
    documents=[
        "Machine learning is a subset of AI.",
        "Python is a programming language.",
        "Deep learning uses neural networks.",
    ],
    top_n=2
)

# Results are sorted by relevance score
for result in results:
    print(f"Score: {result.score:.3f} - {result.content}")
```

### Configuration-Based Setup

```python
from aurora_ext.rag.retrieval import RerankerConfig, create_reranker

# Load from TOML config
config = RerankerConfig.from_toml({
    "reranker": {
        "enabled": True,
        "type": "cohere",
        "api_key": "your-api-key",
        "model": "rerank-multilingual-v3.0",
        "top_k": 10,
        "timeout": 30
    }
})

# Create reranker via factory
reranker = create_reranker(config)

# Use in query engine
from aurora_ext.rag.retrieval import QueryEngine, QueryParam, QueryMode

engine = QueryEngine(
    llm=llm,
    embedding_func=embedding_func,
    kv_storage=kv_storage,
    vector_storage=vector_storage,
    graph_storage=graph_storage,
    reranker=reranker
)

# Mix mode enables reranker by default
param = QueryParam(
    query="What is machine learning?",
    mode=QueryMode.MIX
)
result = await engine.query(param)
```

## Configuration

### TOML Configuration

```toml
[reranker]
enabled = true
type = "cohere"  # cohere, jina, aliyun, vllm
api_key = "your-api-key"
api_base = "https://api.cohere.ai/v1"
model = "rerank-multilingual-v3.0"
top_k = 10
timeout = 30
max_retries = 3

# Long document chunking
enable_chunking = false
max_tokens_per_doc = 4096
score_aggregation = "max"  # max, mean, first
min_score = 0.0
```

### Environment Variables

```bash
export RERANKER_ENABLED=true
export RERANKER_TYPE=cohere
export RERANKER_API_KEY=your-api-key
export RERANKER_API_BASE=https://api.cohere.ai/v1
export RERANKER_MODEL=rerank-multilingual-v3.0
export RERANKER_TOP_K=10
export RERANKER_TIMEOUT=30
export RERANKER_MAX_RETRIES=3
```

### Provider-Specific Configuration

#### Cohere

```python
from aurora_ext.rag.retrieval import CohereReranker

reranker = CohereReranker(
    api_key="your-cohere-key",
    model="rerank-multilingual-v3.0",
    endpoint="https://api.cohere.com/v2/rerank",
    max_tokens_per_doc=4096,
    timeout=30.0
)
```

#### Jina AI

```python
from aurora_ext.rag.retrieval import JinaReranker

reranker = JinaReranker(
    api_key="your-jina-key",
    model="jina-reranker-v2-base-multilingual",
    endpoint="https://api.jina.ai/v1/rerank",
    timeout=30.0
)
```

#### Aliyun DashScope

```python
from aurora_ext.rag.retrieval import AliyunReranker, RerankOptions

options = RerankOptions(
    enable_chunking=True,
    max_tokens_per_doc=4096,
    score_aggregation="max",
    min_score=0.5,
    timeout=30,
    max_retries=3
)

reranker = AliyunReranker(
    api_key="your-dashscope-key",
    model="gte-rerank-v2",
    endpoint="https://dashscope.aliyuncs.com/api/v1/services/rerank",
    options=options
)
```

#### vLLM (Self-Hosted)

```python
from aurora_ext.rag.retrieval import VLLMReranker

reranker = VLLMReranker(
    api_key="",  # Usually empty for local deployments
    model="BAAI/bge-reranker-v2-m3",
    endpoint="http://localhost:8000/v1/rerank",
    max_tokens_per_doc=4096,
    timeout=30.0
)
```

## Advanced Features

### Robust Error Handling

Wrap any reranker with `RobustReranker` for automatic error handling, fallback, and circuit breaker:

```python
from aurora_ext.rag.retrieval import RobustReranker, CohereReranker

base_reranker = CohereReranker(api_key="your-key")
reranker = RobustReranker(
    base_reranker,
    fallback_to_original=True,  # Return original order on failure
    circuit_breaker_threshold=5,  # Open circuit after 5 failures
    circuit_breaker_timeout=60.0  # Retry after 60 seconds
)

# Now failures won't crash your query pipeline
results = await reranker.rerank(query, documents, top_n=10)
```

### Long Document Chunking

For documents exceeding token limits, enable automatic chunking with score aggregation:

```python
from aurora_ext.rag.retrieval import AliyunReranker, RerankOptions

options = RerankOptions(
    enable_chunking=True,
    max_tokens_per_doc=2048,  # Split documents > 2048 tokens
    score_aggregation="max",  # max, mean, or first
)

reranker = AliyunReranker(options=options)

# Long documents are automatically split and scores aggregated
results = await reranker.rerank(query, long_documents, top_n=10)
```

### Score Aggregation Strategies

When chunking is enabled, multiple chunk scores must be combined:

- **`max`** (default): Use the highest chunk score. Best for finding the most relevant passage.
- **`mean`**: Average all chunk scores. Good for overall document relevance.
- **`first`**: Use the first chunk's score. Useful when documents have consistent structure.

### Circuit Breaker Pattern

The `RobustReranker` includes a circuit breaker to prevent cascading failures:

```python
reranker = RobustReranker(
    base_reranker,
    circuit_breaker_threshold=5,  # Failures before circuit opens
    circuit_breaker_timeout=60.0  # Seconds before retry
)

# After 5 consecutive failures:
# - Circuit opens for 60 seconds
# - All requests use fallback immediately
# - After timeout, circuit resets and retries
```

## Query Engine Integration

### Automatic Reranking in Mix Mode

The query engine automatically applies reranking in `MIX` mode when a reranker is configured:

```python
from aurora_ext.rag.retrieval import QueryEngine, QueryParam, QueryMode

# Mix mode: KG + vector search + reranking
param = QueryParam(
    query="What is machine learning?",
    mode=QueryMode.MIX  # Reranker enabled by default
)
result = await engine.query(param)
```

### Manual Reranker Control

Explicitly enable or disable reranking:

```python
# Force enable reranking in any mode
param = QueryParam(
    query="What is machine learning?",
    mode=QueryMode.NAIVE,
    enable_rerank=True  # Override default
)

# Disable reranking in mix mode
param = QueryParam(
    query="What is machine learning?",
    mode=QueryMode.MIX,
    enable_rerank=False  # Override default
)
```

## Error Handling

### Graceful Degradation

All reranker implementations catch exceptions and return empty lists on failure:

```python
try:
    results = await reranker.rerank(query, documents, top_n=10)
except Exception as e:
    logger.error(f"Reranker failed: {e}")
    results = []  # Graceful degradation
```

### Retry with Exponential Backoff

The Aliyun reranker includes automatic retry logic:

```python
# Automatically retries with exponential backoff:
# Attempt 1: immediate
# Attempt 2: 4 second delay
# Attempt 3: 8 second delay
# Attempt 4: 16 second delay (up to max_delay)
```

### Rate Limiting

HTTP 429 responses are handled via exponential backoff. For production workloads, consider:

1. Using `RobustReranker` with circuit breaker
2. Implementing request queuing
3. Monitoring rate limit headers
4. Using multiple API keys with load balancing

## Testing

### Running Tests

```bash
cd packages/aurora-ext
pytest tests/rag/retrieval/test_reranker.py -v
```

### Mock API Responses

Tests use mocked API responses to avoid real API calls:

```python
@pytest.mark.asyncio
async def test_cohere_reranker():
    mock_response = {
        "results": [
            {"index": 0, "relevance_score": 0.95},
            {"index": 1, "relevance_score": 0.87},
        ]
    }

    with patch("aiohttp.ClientSession") as mock_session:
        # Setup mock
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_response)
        # ... configure mock

        reranker = CohereReranker(api_key="test-key")
        results = await reranker.rerank(query, documents, top_n=2)

        assert len(results) == 2
```

## Performance Considerations

### Latency

- **Cohere**: ~200-400ms for 10 documents
- **Jina**: ~150-300ms for 10 documents
- **Aliyun**: ~300-500ms for 10 documents
- **vLLM**: ~100-200ms (local, depends on hardware)

### Optimization Tips

1. **Limit `top_k`**: Only rerank the top 20-40 candidates
2. **Enable chunking**: For documents > 4K tokens
3. **Use `min_score`**: Filter low-relevance results early
4. **Batch queries**: Rerank multiple queries in one call when possible
5. **Cache results**: Cache reranker results for repeated queries

### Cost

- **Cohere**: $0.001 per 1K documents (rerank-v3.5)
- **Jina**: $0.0005 per 1K documents
- **Aliyun**: ¥0.002 per 1K documents
- **vLLM**: Free (self-hosted, hardware cost only)

## Troubleshooting

### Common Issues

**Issue**: Empty results returned

**Solution**: Check logs for API errors. Verify API key and endpoint.

**Issue**: Timeout errors

**Solution**: Increase `timeout` parameter. Check network connectivity.

**Issue**: Rate limit errors (HTTP 429)

**Solution**: Implement request queuing. Use `RobustReranker` with circuit breaker.

**Issue**: Inconsistent scores

**Solution**: Ensure consistent document preprocessing. Check for encoding issues.

### Debugging

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger("aurora_ext.rag.retrieval.reranker")
logger.setLevel(logging.DEBUG)
```

## API Reference

### RerankerBase

Abstract base class for all rerankers.

```python
class RerankerBase(ABC):
    @abstractmethod
    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_n: int,
        min_score: float = 0.0,
    ) -> list[RerankResult]:
        """Rerank documents by relevance to query."""
```

### RerankResult

Immutable result dataclass.

```python
@dataclass(frozen=True)
class RerankResult:
    index: int      # Original document index
    score: float    # Relevance score (higher = better)
    content: str    # Document text

    @property
    def text(self) -> str:
        """Alias for backward compatibility."""
```

### RerankerConfig

Configuration dataclass with factory methods.

```python
@dataclass(frozen=True)
class RerankerConfig:
    enabled: bool = True
    type: str = "cohere"
    api_key: str = ""
    api_base: str = ""
    model: str = ""
    top_k: int = 10
    timeout: int = 30
    max_retries: int = 3
    enable_chunking: bool = False
    max_tokens_per_doc: int = 4096
    score_aggregation: str = "max"
    min_score: float = 0.0

    @classmethod
    def from_toml(cls, config: dict) -> RerankerConfig:
        """Load from TOML dictionary."""

    @classmethod
    def from_env(cls) -> RerankerConfig:
        """Load from environment variables."""
```

### create_reranker

Factory function to instantiate reranker from config.

```python
def create_reranker(config: RerankerConfig) -> Optional[RerankerBase]:
    """Create reranker from configuration.

    Returns None if disabled or invalid type.
    """
```

### RobustReranker

Wrapper with error handling and circuit breaker.

```python
class RobustReranker(RerankerBase):
    def __init__(
        self,
        reranker: RerankerBase,
        fallback_to_original: bool = True,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_timeout: float = 60.0,
    ):
        """Initialize robust wrapper."""
```

## Migration Guide

### From LightRAG

```python
# LightRAG (old)
from lightrag.rerank import cohere_rerank
results = cohere_rerank(query, documents, api_key="key")

# Aurora (new)
from aurora_ext.rag.retrieval import CohereReranker
reranker = CohereReranker(api_key="key")
results = await reranker.rerank(query, documents, top_n=10)
```

## License

Part of the Aurora-Design project. See LICENSE for details.
