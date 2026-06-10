"""Tests for reranker implementations.

This module tests all reranker types with mocked API responses.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aurora_ext.rag.retrieval.reranker import (
    AliyunReranker,
    CohereReranker,
    JinaReranker,
    RerankerConfig,
    RerankOptions,
    RerankResult,
    RobustReranker,
    VLLMReranker,
    _aggregate_scores,
    _split_into_chunks,
    create_reranker,
)


# ── Test Data ────────────────────────────────────────────────────


@pytest.fixture
def sample_query():
    return "What is machine learning?"


@pytest.fixture
def sample_documents():
    return [
        "Machine learning is a subset of artificial intelligence.",
        "Deep learning uses neural networks with many layers.",
        "Python is a popular programming language.",
        "Natural language processing deals with text understanding.",
        "Supervised learning requires labeled training data.",
    ]


# ── RerankResult Tests ───────────────────────────────────────────


def test_rerank_result_creation():
    """Test RerankResult dataclass creation."""
    result = RerankResult(index=0, score=0.95, content="Test document")

    assert result.index == 0
    assert result.score == 0.95
    assert result.content == "Test document"
    assert result.text == "Test document"  # backward compatibility


def test_rerank_result_immutable():
    """Test that RerankResult is frozen (immutable)."""
    result = RerankResult(index=0, score=0.95, content="Test")

    with pytest.raises(Exception):  # FrozenInstanceError
        result.score = 0.5


# ── RerankOptions Tests ──────────────────────────────────────────


def test_rerank_options_defaults():
    """Test RerankOptions default values."""
    options = RerankOptions()

    assert options.enable_chunking is False
    assert options.max_tokens_per_doc == 4096
    assert options.score_aggregation == "max"
    assert options.min_score == 0.0
    assert options.timeout == 30
    assert options.max_retries == 3


def test_rerank_options_custom():
    """Test RerankOptions with custom values."""
    options = RerankOptions(
        enable_chunking=True,
        max_tokens_per_doc=2048,
        score_aggregation="mean",
        min_score=0.5,
    )

    assert options.enable_chunking is True
    assert options.max_tokens_per_doc == 2048
    assert options.score_aggregation == "mean"
    assert options.min_score == 0.5


# ── Score Aggregation Tests ──────────────────────────────────────


def test_aggregate_scores_max():
    """Test max aggregation strategy."""
    scores = [0.5, 0.8, 0.3, 0.9]
    assert _aggregate_scores(scores, "max") == 0.9


def test_aggregate_scores_mean():
    """Test mean aggregation strategy."""
    scores = [0.4, 0.6, 0.8]
    assert _aggregate_scores(scores, "mean") == pytest.approx(0.6)


def test_aggregate_scores_first():
    """Test first aggregation strategy."""
    scores = [0.7, 0.5, 0.3]
    assert _aggregate_scores(scores, "first") == 0.7


def test_aggregate_scores_empty():
    """Test aggregation with empty list."""
    assert _aggregate_scores([], "max") == 0.0


# ── Chunk Splitting Tests ────────────────────────────────────────


def test_split_into_chunks_short_text():
    """Test chunking with text under limit."""
    text = "Short text"
    chunks = _split_into_chunks(text, max_chars=100)

    assert len(chunks) == 1
    assert chunks[0] == text


def test_split_into_chunks_long_text():
    """Test chunking with long text."""
    text = " ".join(["word"] * 100)
    chunks = _split_into_chunks(text, max_chars=50)

    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 60  # Allow some slack for word boundaries


def test_split_into_chunks_empty():
    """Test chunking with empty text."""
    chunks = _split_into_chunks("", max_chars=100)
    assert len(chunks) == 1
    assert chunks[0] == ""


# ── Cohere Reranker Tests ────────────────────────────────────────


@pytest.mark.asyncio
async def test_cohere_reranker_success(sample_query, sample_documents):
    """Test Cohere reranker with successful API response."""
    mock_response = {
        "results": [
            {"index": 0, "relevance_score": 0.95},
            {"index": 1, "relevance_score": 0.87},
            {"index": 4, "relevance_score": 0.72},
        ]
    }

    with patch("aiohttp.ClientSession") as mock_session_class:
        # Create mock response
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_response)

        # Create async context manager for post()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_resp
        mock_ctx.__aexit__.return_value = None

        # Create mock session instance
        mock_session_instance = AsyncMock()
        mock_session_instance.post = MagicMock(return_value=mock_ctx)

        # Make ClientSession() return our mock session
        mock_session_class.return_value.__aenter__.return_value = mock_session_instance

        reranker = CohereReranker(api_key="test-key")
        results = await reranker.rerank(sample_query, sample_documents, top_n=3)

        assert len(results) == 3
        assert results[0].index == 0
        assert results[0].score == 0.95
        assert results[0].content == sample_documents[0]


@pytest.mark.asyncio
async def test_cohere_reranker_with_min_score(sample_query, sample_documents):
    """Test Cohere reranker with min_score filter."""
    mock_response = {
        "results": [
            {"index": 0, "relevance_score": 0.95},
            {"index": 1, "relevance_score": 0.30},  # Below threshold
        ]
    }

    with patch("aiohttp.ClientSession") as mock_session_class:
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_response)

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_resp
        mock_ctx.__aexit__.return_value = None

        mock_session_instance = AsyncMock()
        mock_session_instance.post = MagicMock(return_value=mock_ctx)

        mock_session_class.return_value.__aenter__.return_value = mock_session_instance

        reranker = CohereReranker(api_key="test-key")
        results = await reranker.rerank(
            sample_query, sample_documents, top_n=10, min_score=0.5
        )

        assert len(results) == 1
        assert results[0].score == 0.95


@pytest.mark.asyncio
async def test_cohere_reranker_api_error(sample_query, sample_documents):
    """Test Cohere reranker with API error."""
    with patch("aiohttp.ClientSession") as mock_session_class:
        mock_resp = AsyncMock()
        mock_resp.status = 500

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_resp
        mock_ctx.__aexit__.return_value = None

        mock_session_instance = AsyncMock()
        mock_session_instance.post = MagicMock(return_value=mock_ctx)

        mock_session_class.return_value.__aenter__.return_value = mock_session_instance

        reranker = CohereReranker(api_key="test-key")
        results = await reranker.rerank(sample_query, sample_documents, top_n=3)

        assert results == []


# ── Jina Reranker Tests ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_jina_reranker_success(sample_query, sample_documents):
    """Test Jina reranker with successful API response."""
    mock_response = {
        "results": [
            {"index": 0, "relevance_score": 0.92},
            {"index": 3, "relevance_score": 0.85},
        ]
    }

    with patch("aiohttp.ClientSession") as mock_session_class:
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_response)

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_resp
        mock_ctx.__aexit__.return_value = None

        mock_session_instance = AsyncMock()
        mock_session_instance.post = MagicMock(return_value=mock_ctx)

        mock_session_class.return_value.__aenter__.return_value = mock_session_instance

        reranker = JinaReranker(api_key="test-key")
        results = await reranker.rerank(sample_query, sample_documents, top_n=2)

        assert len(results) == 2
        assert results[0].index == 0
        assert results[0].score == 0.92


# ── Aliyun Reranker Tests ────────────────────────────────────────


@pytest.mark.asyncio
async def test_aliyun_reranker_success(sample_query, sample_documents):
    """Test Aliyun DashScope reranker with successful response."""
    mock_response = {
        "output": {
            "results": [
                {"index": 0, "relevance_score": 0.93},
                {"index": 2, "relevance_score": 0.78},
            ]
        }
    }

    with patch("aiohttp.ClientSession") as mock_session_class:
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_response)

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_resp
        mock_ctx.__aexit__.return_value = None

        mock_session_instance = AsyncMock()
        mock_session_instance.post = MagicMock(return_value=mock_ctx)

        mock_session_class.return_value.__aenter__.return_value = mock_session_instance

        reranker = AliyunReranker(api_key="test-key")
        results = await reranker.rerank(sample_query, sample_documents, top_n=2)

        assert len(results) == 2
        assert results[0].index == 0
        assert results[0].score == 0.93


@pytest.mark.asyncio
async def test_aliyun_reranker_with_chunking(sample_query):
    """Test Aliyun reranker with document chunking enabled."""
    # Create a long document
    long_doc = " ".join(["machine learning concept"] * 500)
    documents = [long_doc, "Short doc"]

    mock_response = {
        "output": {
            "results": [
                {"index": 0, "relevance_score": 0.90},
                {"index": 1, "relevance_score": 0.85},
                {"index": 2, "relevance_score": 0.80},
            ]
        }
    }

    with patch("aiohttp.ClientSession") as mock_session_class:
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_response)

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_resp
        mock_ctx.__aexit__.return_value = None

        mock_session_instance = AsyncMock()
        mock_session_instance.post = MagicMock(return_value=mock_ctx)

        mock_session_class.return_value.__aenter__.return_value = mock_session_instance

        options = RerankOptions(enable_chunking=True, max_tokens_per_doc=100)
        reranker = AliyunReranker(api_key="test-key", options=options)
        results = await reranker.rerank(sample_query, documents, top_n=2)

        assert len(results) > 0


# ── vLLM Reranker Tests ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_vllm_reranker_success(sample_query, sample_documents):
    """Test vLLM reranker (Cohere-compatible API)."""
    mock_response = {
        "results": [
            {"index": 0, "relevance_score": 0.94},
            {"index": 1, "relevance_score": 0.88},
        ]
    }

    with patch("aiohttp.ClientSession") as mock_session_class:
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_response)

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_resp
        mock_ctx.__aexit__.return_value = None

        mock_session_instance = AsyncMock()
        mock_session_instance.post = MagicMock(return_value=mock_ctx)

        mock_session_class.return_value.__aenter__.return_value = mock_session_instance

        reranker = VLLMReranker(
            api_key="",
            endpoint="http://localhost:8000/v1/rerank",
        )
        results = await reranker.rerank(sample_query, sample_documents, top_n=2)

        assert len(results) == 2
        assert results[0].score == 0.94


# ── Configuration Tests ──────────────────────────────────────────


def test_reranker_config_from_toml():
    """Test loading configuration from TOML dict."""
    config_dict = {
        "reranker": {
            "enabled": True,
            "type": "cohere",
            "api_key": "test-key",
            "api_base": "https://api.cohere.ai/v1",
            "model": "rerank-multilingual-v3.0",
            "top_k": 10,
            "timeout": 30,
        }
    }

    config = RerankerConfig.from_toml(config_dict)

    assert config.enabled is True
    assert config.type == "cohere"
    assert config.api_key == "test-key"
    assert config.model == "rerank-multilingual-v3.0"


def test_reranker_config_env_override():
    """Test environment variable override."""
    import os

    os.environ["RERANKER_API_KEY"] = "env-key"

    try:
        config_dict = {
            "reranker": {
                "type": "jina",
                "api_key": "",  # Empty in config
            }
        }

        config = RerankerConfig.from_toml(config_dict)
        assert config.api_key == "env-key"
    finally:
        del os.environ["RERANKER_API_KEY"]


def test_reranker_config_from_env():
    """Test loading configuration purely from environment."""
    import os

    os.environ["RERANKER_TYPE"] = "aliyun"
    os.environ["RERANKER_API_KEY"] = "env-key"
    os.environ["RERANKER_TOP_K"] = "15"

    try:
        config = RerankerConfig.from_env()

        assert config.type == "aliyun"
        assert config.api_key == "env-key"
        assert config.top_k == 15
    finally:
        del os.environ["RERANKER_TYPE"]
        del os.environ["RERANKER_API_KEY"]
        del os.environ["RERANKER_TOP_K"]


# ── Factory Tests ────────────────────────────────────────────────


def test_create_reranker_cohere():
    """Test factory creates Cohere reranker."""
    config = RerankerConfig(
        enabled=True,
        type="cohere",
        api_key="test-key",
        model="rerank-v3.5",
    )

    reranker = create_reranker(config)

    assert isinstance(reranker, CohereReranker)


def test_create_reranker_jina():
    """Test factory creates Jina reranker."""
    config = RerankerConfig(
        enabled=True,
        type="jina",
        api_key="test-key",
    )

    reranker = create_reranker(config)

    assert isinstance(reranker, JinaReranker)


def test_create_reranker_aliyun():
    """Test factory creates Aliyun reranker."""
    config = RerankerConfig(
        enabled=True,
        type="aliyun",
        api_key="test-key",
    )

    reranker = create_reranker(config)

    assert isinstance(reranker, AliyunReranker)


def test_create_reranker_vllm():
    """Test factory creates vLLM reranker."""
    config = RerankerConfig(
        enabled=True,
        type="vllm",
        api_key="",
        api_base="http://localhost:8000/v1/rerank",
    )

    reranker = create_reranker(config)

    assert isinstance(reranker, VLLMReranker)


def test_create_reranker_disabled():
    """Test factory returns None when disabled."""
    config = RerankerConfig(enabled=False, type="cohere")

    reranker = create_reranker(config)

    assert reranker is None


def test_create_reranker_invalid_type():
    """Test factory returns None for invalid type."""
    config = RerankerConfig(enabled=True, type="invalid")

    reranker = create_reranker(config)

    assert reranker is None


# ── Robust Reranker Tests ────────────────────────────────────────


@pytest.mark.asyncio
async def test_robust_reranker_success(sample_query, sample_documents):
    """Test robust wrapper with successful reranker."""
    mock_reranker = AsyncMock()
    mock_reranker.rerank = AsyncMock(
        return_value=[
            RerankResult(index=0, score=0.95, content=sample_documents[0])
        ]
    )

    robust = RobustReranker(mock_reranker)
    results = await robust.rerank(sample_query, sample_documents, top_n=1)

    assert len(results) == 1
    assert results[0].score == 0.95


@pytest.mark.asyncio
async def test_robust_reranker_fallback_on_error(sample_query, sample_documents):
    """Test robust wrapper falls back on error."""
    mock_reranker = AsyncMock()
    mock_reranker.rerank = AsyncMock(side_effect=Exception("API Error"))

    robust = RobustReranker(mock_reranker, fallback_to_original=True)
    results = await robust.rerank(sample_query, sample_documents, top_n=3)

    # Should return original order with score=1.0
    assert len(results) == 3
    assert results[0].index == 0
    assert results[0].score == 1.0


@pytest.mark.asyncio
async def test_robust_reranker_no_fallback(sample_query, sample_documents):
    """Test robust wrapper returns empty when fallback disabled."""
    mock_reranker = AsyncMock()
    mock_reranker.rerank = AsyncMock(side_effect=Exception("API Error"))

    robust = RobustReranker(mock_reranker, fallback_to_original=False)
    results = await robust.rerank(sample_query, sample_documents, top_n=3)

    assert results == []


@pytest.mark.asyncio
async def test_robust_reranker_circuit_breaker(sample_query, sample_documents):
    """Test circuit breaker opens after multiple failures."""
    mock_reranker = AsyncMock()
    mock_reranker.rerank = AsyncMock(side_effect=Exception("API Error"))

    robust = RobustReranker(
        mock_reranker,
        circuit_breaker_threshold=3,
        circuit_breaker_timeout=10.0,
    )

    # Trigger 3 failures
    for _ in range(3):
        await robust.rerank(sample_query, sample_documents, top_n=1)

    # Circuit should now be open
    assert robust._failure_count == 3

    # Next call should use fallback immediately
    results = await robust.rerank(sample_query, sample_documents, top_n=2)
    assert len(results) == 2


# ── Integration Tests ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_end_to_end_cohere_flow(sample_query, sample_documents):
    """Test complete flow with Cohere reranker."""
    mock_response = {
        "results": [
            {"index": 0, "relevance_score": 0.95},
            {"index": 1, "relevance_score": 0.87},
        ]
    }

    with patch("aiohttp.ClientSession") as mock_session_class:
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_response)

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_resp
        mock_ctx.__aexit__.return_value = None

        mock_session_instance = AsyncMock()
        mock_session_instance.post = MagicMock(return_value=mock_ctx)

        mock_session_class.return_value.__aenter__.return_value = mock_session_instance

        # Create config
        config = RerankerConfig(
            enabled=True,
            type="cohere",
            api_key="test-key",
            model="rerank-v3.5",
        )

        # Create reranker via factory
        reranker = create_reranker(config)
        assert reranker is not None

        # Wrap in robust handler
        robust_reranker = RobustReranker(reranker)

        # Execute
        results = await robust_reranker.rerank(
            sample_query, sample_documents, top_n=2
        )

        assert len(results) == 2
        assert results[0].score == 0.95
