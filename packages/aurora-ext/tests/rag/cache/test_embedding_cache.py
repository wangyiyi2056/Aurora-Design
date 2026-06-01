"""Tests for embedding similarity cache.

Covers exact match, similarity search, LLM verification, and eviction.
"""

import asyncio
import pytest

from aurora_ext.rag.cache.embedding_cache import (
    EmbeddingResult,
    EmbeddingSimilarityCache,
    _cosine_similarity,
    _normalize_vector,
)
from aurora_ext.rag.cache.config import EmbeddingCacheConfig


@pytest.fixture
def config():
    """Default test configuration."""
    return EmbeddingCacheConfig(
        enabled=True,
        similarity_threshold=0.90,  # Lower threshold for testing
        use_llm_verify=False,
        max_size=5,
    )


@pytest.fixture
def cache(config):
    """Create a test cache instance."""
    return EmbeddingSimilarityCache(config=config)


@pytest.fixture
def sample_embedding():
    """Sample embedding result."""
    return EmbeddingResult(
        vector=[0.1, 0.2, 0.3, 0.4, 0.5],
        query_text="What is the capital of France?",
        model_used="text-embedding-ada-002",
        dimensions=5,
    )


class TestVectorOperations:
    """Test suite for vector utility functions."""

    def test_cosine_similarity_identical(self):
        """Test similarity of identical vectors."""
        v = [1.0, 2.0, 3.0]
        similarity = _cosine_similarity(v, v)
        assert abs(similarity - 1.0) < 1e-6

    def test_cosine_similarity_orthogonal(self):
        """Test similarity of orthogonal vectors."""
        v1 = [1.0, 0.0]
        v2 = [0.0, 1.0]
        similarity = _cosine_similarity(v1, v2)
        assert abs(similarity) < 1e-6

    def test_cosine_similarity_opposite(self):
        """Test similarity of opposite vectors."""
        v1 = [1.0, 0.0]
        v2 = [-1.0, 0.0]
        similarity = _cosine_similarity(v1, v2)
        assert abs(similarity - (-1.0)) < 1e-6

    def test_cosine_similarity_empty(self):
        """Test similarity of empty vectors."""
        similarity = _cosine_similarity([], [])
        assert similarity == 0.0

    def test_cosine_similarity_different_lengths(self):
        """Test similarity of vectors with different lengths."""
        v1 = [1.0, 2.0]
        v2 = [1.0, 2.0, 3.0]
        similarity = _cosine_similarity(v1, v2)
        assert similarity == 0.0

    def test_normalize_vector(self):
        """Test vector normalization."""
        v = [3.0, 4.0]
        normalized = _normalize_vector(v)
        # Should be unit vector: [0.6, 0.8]
        assert abs(normalized[0] - 0.6) < 1e-6
        assert abs(normalized[1] - 0.8) < 1e-6

    def test_normalize_zero_vector(self):
        """Test normalizing a zero vector."""
        v = [0.0, 0.0, 0.0]
        normalized = _normalize_vector(v)
        assert normalized == [0.0, 0.0, 0.0]


class TestEmbeddingSimilarityCache:
    """Test suite for EmbeddingSimilarityCache."""

    @pytest.mark.asyncio
    async def test_put_and_get_exact(self, cache, sample_embedding):
        """Test exact match put and get."""
        text = sample_embedding.query_text
        text_hash = cache.hash_text(text)

        await cache.put(text_hash, sample_embedding)
        result = await cache.get(text_hash)

        assert result is not None
        assert result.vector == sample_embedding.vector

    @pytest.mark.asyncio
    async def test_hash_text_deterministic(self, cache):
        """Test that text hashing is deterministic."""
        text = "Test query"
        hash1 = cache.hash_text(text)
        hash2 = cache.hash_text(text)
        assert hash1 == hash2

    @pytest.mark.asyncio
    async def test_hash_text_normalizes_whitespace(self, cache):
        """Test that hashing normalizes whitespace."""
        text1 = "What is  the capital?"
        text2 = "What is the capital?"
        hash1 = cache.hash_text(text1)
        hash2 = cache.hash_text(text2)
        assert hash1 == hash2

    @pytest.mark.asyncio
    async def test_get_similar_exact_match(self, cache, sample_embedding):
        """Test similarity search with exact match."""
        text = sample_embedding.query_text
        text_hash = cache.hash_text(text)

        await cache.put(text_hash, sample_embedding)

        # Search with same text
        result = await cache.get_similar(text)

        assert result is not None
        cached_result, similarity = result
        assert similarity == 1.0
        assert cached_result.vector == sample_embedding.vector

    @pytest.mark.asyncio
    async def test_get_similar_approximate_match(self, cache, sample_embedding):
        """Test similarity search with approximate match."""
        text = sample_embedding.query_text
        text_hash = cache.hash_text(text)

        await cache.put(text_hash, sample_embedding)

        # Create a very similar embedding (small perturbation)
        similar_embedding = [v + 0.01 for v in sample_embedding.vector]

        # Search with similar embedding
        result = await cache.get_similar(
            "Different but similar query",
            query_embedding=similar_embedding,
        )

        assert result is not None
        cached_result, similarity = result
        assert similarity >= 0.90  # Should be above threshold
        assert cached_result.vector == sample_embedding.vector

    @pytest.mark.asyncio
    async def test_get_similar_below_threshold(self, cache, sample_embedding):
        """Test similarity search when below threshold."""
        text = sample_embedding.query_text
        text_hash = cache.hash_text(text)

        await cache.put(text_hash, sample_embedding)

        # Create a very different embedding
        different_embedding = [1.0, 0.0, 0.0, 0.0, 0.0]

        result = await cache.get_similar(
            "Completely different query",
            query_embedding=different_embedding,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_get_similar_no_embedding(self, cache, sample_embedding):
        """Test similarity search without query embedding."""
        text = sample_embedding.query_text
        text_hash = cache.hash_text(text)

        await cache.put(text_hash, sample_embedding)

        # Search with different text and no embedding
        result = await cache.get_similar("Different query")

        assert result is None

    @pytest.mark.asyncio
    async def test_lru_eviction(self, config, sample_embedding):
        """Test LRU eviction when cache is full."""
        cache = EmbeddingSimilarityCache(config=config)

        # Fill cache to capacity (max_size=5)
        for i in range(5):
            result = EmbeddingResult(
                vector=[float(i)] * 5,
                query_text=f"Query {i}",
            )
            await cache.put(f"hash_{i}", result)

        # Add one more to trigger eviction
        result = EmbeddingResult(
            vector=[5.0] * 5,
            query_text="Query 5",
        )
        await cache.put("hash_5", result)

        # First entry should be evicted
        cached = await cache.get("hash_0")
        assert cached is None

    @pytest.mark.asyncio
    async def test_stats(self, cache, sample_embedding):
        """Test statistics tracking."""
        # Add entries
        for i in range(3):
            result = EmbeddingResult(
                vector=[float(i)] * 5,
                query_text=f"Query {i}",
            )
            await cache.put(f"hash_{i}", result)

        # Generate hits and misses
        await cache.get("hash_0")  # hit
        await cache.get("hash_1")  # hit
        await cache.get("nonexistent")  # miss

        stats = await cache.stats()

        assert stats.hits == 2
        assert stats.misses == 1
        assert stats.size == 3

    @pytest.mark.asyncio
    async def test_clear(self, cache, sample_embedding):
        """Test clearing all entries."""
        for i in range(3):
            await cache.put(f"hash_{i}", sample_embedding)

        cleared = await cache.clear()
        assert cleared == 3

        stats = await cache.stats()
        assert stats.size == 0
        assert stats.hits == 0
        assert stats.misses == 0

    @pytest.mark.asyncio
    async def test_delete(self, cache, sample_embedding):
        """Test delete operation."""
        text_hash = "test_hash"
        await cache.put(text_hash, sample_embedding)

        deleted = await cache.delete(text_hash)
        assert deleted is True

        result = await cache.get(text_hash)
        assert result is None

    @pytest.mark.asyncio
    async def test_contains(self, cache, sample_embedding):
        """Test contains check."""
        text_hash = "test_hash"

        assert not await cache.contains(text_hash)

        await cache.put(text_hash, sample_embedding)

        assert await cache.contains(text_hash)

    @pytest.mark.asyncio
    async def test_disabled_cache(self, sample_embedding):
        """Test that disabled cache doesn't store anything."""
        config = EmbeddingCacheConfig(enabled=False)
        cache = EmbeddingSimilarityCache(config=config)

        await cache.put("hash", sample_embedding)
        result = await cache.get("hash")

        assert result is None

    @pytest.mark.asyncio
    async def test_similarity_stats(self, cache, sample_embedding):
        """Test similarity-specific statistics."""
        text = sample_embedding.query_text
        text_hash = cache.hash_text(text)
        await cache.put(text_hash, sample_embedding)

        # Trigger a similarity hit
        similar_embedding = [v + 0.01 for v in sample_embedding.vector]
        await cache.get_similar("Different query", query_embedding=similar_embedding)

        sim_stats = cache.get_similarity_stats()
        assert sim_stats["similarity_hits"] == 1
        assert sim_stats["similarity_threshold"] == 0.90

    @pytest.mark.asyncio
    async def test_llm_verification_enabled(self, sample_embedding):
        """Test LLM verification for similar matches."""

        # Mock LLM verifier that returns "yes"
        async def mock_llm(prompt):
            return "yes, they are equivalent"

        config = EmbeddingCacheConfig(
            enabled=True,
            similarity_threshold=0.90,
            use_llm_verify=True,
        )
        cache = EmbeddingSimilarityCache(config=config, llm_verifier=mock_llm)

        text = sample_embedding.query_text
        text_hash = cache.hash_text(text)
        await cache.put(text_hash, sample_embedding)

        # Should pass LLM verification
        similar_embedding = [v + 0.01 for v in sample_embedding.vector]
        result = await cache.get_similar(
            "Similar query",
            query_embedding=similar_embedding,
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_llm_verification_rejected(self, sample_embedding):
        """Test LLM verification rejection."""

        # Mock LLM verifier that returns "no"
        async def mock_llm(prompt):
            return "no, they are different"

        config = EmbeddingCacheConfig(
            enabled=True,
            similarity_threshold=0.90,
            use_llm_verify=True,
        )
        cache = EmbeddingSimilarityCache(config=config, llm_verifier=mock_llm)

        text = sample_embedding.query_text
        text_hash = cache.hash_text(text)
        await cache.put(text_hash, sample_embedding)

        # Should be rejected by LLM verification
        similar_embedding = [v + 0.01 for v in sample_embedding.vector]
        result = await cache.get_similar(
            "Similar query",
            query_embedding=similar_embedding,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_embedding_result_dataclass(self):
        """Test EmbeddingResult dataclass."""
        result = EmbeddingResult(
            vector=[1.0, 2.0, 3.0],
            query_text="test query",
            model_used="test-model",
            dimensions=3,
        )

        assert result.vector == [1.0, 2.0, 3.0]
        assert result.query_text == "test query"
        assert result.model_used == "test-model"
        assert result.dimensions == 3
