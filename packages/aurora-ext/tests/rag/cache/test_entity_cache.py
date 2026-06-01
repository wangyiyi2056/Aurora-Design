"""Tests for entity extraction cache.

Covers content hashing, document ID tracking, and selective clearing.
"""

import asyncio
import pytest

from aurora_ext.rag.cache.entity_cache import (
    EntityExtractionCache,
    EntityExtractionResult,
)
from aurora_ext.rag.cache.config import EntityCacheConfig


@pytest.fixture
def config():
    """Default test configuration."""
    return EntityCacheConfig(
        enabled=True,
        ttl=60,
        max_size=5,
    )


@pytest.fixture
def cache(config):
    """Create a test cache instance."""
    return EntityExtractionCache(config=config)


@pytest.fixture
def sample_result():
    """Sample entity extraction result."""
    return EntityExtractionResult(
        entities=[
            {"name": "Paris", "type": "city"},
            {"name": "France", "type": "country"},
        ],
        relationships=[
            {"source": "Paris", "target": "France", "type": "capital_of"},
        ],
        raw_response="Extracted Paris and France",
        model_used="gpt-4",
    )


class TestEntityExtractionCache:
    """Test suite for EntityExtractionCache."""

    @pytest.mark.asyncio
    async def test_put_and_get(self, cache, sample_result):
        """Test basic put and get operations."""
        content = "Paris is the capital of France."
        content_hash = cache.hash_content(content)

        await cache.put(content_hash, sample_result)
        result = await cache.get(content_hash)

        assert result is not None
        assert result.entities == sample_result.entities
        assert result.relationships == sample_result.relationships

    @pytest.mark.asyncio
    async def test_hash_content_deterministic(self, cache):
        """Test that content hashing is deterministic."""
        content = "Test content"
        hash1 = cache.hash_content(content)
        hash2 = cache.hash_content(content)
        assert hash1 == hash2

    @pytest.mark.asyncio
    async def test_hash_content_different_inputs(self, cache):
        """Test that different content produces different hashes."""
        hash1 = cache.hash_content("Content A")
        hash2 = cache.hash_content("Content B")
        assert hash1 != hash2

    @pytest.mark.asyncio
    async def test_document_id_tracking(self, cache, sample_result):
        """Test tracking entries by document ID."""
        content_hash = "test_hash_123"
        document_id = "doc_001"

        await cache.put(
            content_hash,
            sample_result,
            document_id=document_id,
        )

        # Delete by document ID
        deleted = await cache.delete_by_document_id(document_id)
        assert deleted is True

        # Entry should be gone
        result = await cache.get(content_hash)
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_by_document_id_nonexistent(self, cache):
        """Test deleting by nonexistent document ID."""
        deleted = await cache.delete_by_document_id("nonexistent")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_clear_by_document_ids(self, cache, sample_result):
        """Test clearing multiple document IDs."""
        # Add entries with different document IDs
        for i in range(3):
            await cache.put(
                f"hash_{i}",
                sample_result,
                document_id=f"doc_{i}",
            )

        # Clear specific documents
        cleared = await cache.clear_by_document_ids(["doc_0", "doc_1"])
        assert cleared == 2

        # doc_2 should still exist
        result = await cache.get("hash_2")
        assert result is not None

    @pytest.mark.asyncio
    async def test_ttl_expiration(self, cache, sample_result):
        """Test that entries expire after TTL."""
        content_hash = "test_hash"
        await cache.put(content_hash, sample_result, ttl=1)

        # Should exist immediately
        result = await cache.get(content_hash)
        assert result is not None

        # Wait for expiration
        await asyncio.sleep(1.5)

        # Should be expired
        result = await cache.get(content_hash)
        assert result is None

    @pytest.mark.asyncio
    async def test_lru_eviction(self, config, sample_result):
        """Test LRU eviction when cache is full."""
        cache = EntityExtractionCache(config=config)

        # Fill cache to capacity (max_size=5)
        for i in range(5):
            await cache.put(f"hash_{i}", sample_result, document_id=f"doc_{i}")

        # Add one more to trigger eviction
        await cache.put("hash_5", sample_result, document_id="doc_5")

        # First entry should be evicted
        result = await cache.get("hash_0")
        assert result is None

        # Document mapping should also be cleaned
        deleted = await cache.delete_by_document_id("doc_0")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_stats(self, cache, sample_result):
        """Test statistics tracking."""
        # Add entries
        for i in range(3):
            await cache.put(f"hash_{i}", sample_result)

        # Generate hits and misses
        await cache.get("hash_0")  # hit
        await cache.get("hash_1")  # hit
        await cache.get("nonexistent")  # miss

        stats = await cache.stats()

        assert stats.hits == 2
        assert stats.misses == 1
        assert stats.size == 3

    @pytest.mark.asyncio
    async def test_clear(self, cache, sample_result):
        """Test clearing all entries."""
        for i in range(3):
            await cache.put(
                f"hash_{i}",
                sample_result,
                document_id=f"doc_{i}",
            )

        cleared = await cache.clear()
        assert cleared == 3

        # Document mappings should also be cleared
        for i in range(3):
            deleted = await cache.delete_by_document_id(f"doc_{i}")
            assert deleted is False

    @pytest.mark.asyncio
    async def test_contains(self, cache, sample_result):
        """Test contains check."""
        content_hash = "test_hash"

        assert not await cache.contains(content_hash)

        await cache.put(content_hash, sample_result)

        assert await cache.contains(content_hash)

    @pytest.mark.asyncio
    async def test_cleanup_expired(self, cache, sample_result):
        """Test cleaning up expired entries."""
        await cache.put("short_ttl", sample_result, ttl=1)
        await cache.put("long_ttl", sample_result, ttl=60)

        await asyncio.sleep(1.5)

        cleaned = await cache.cleanup_expired()
        assert cleaned == 1

        # Long TTL entry should still exist
        result = await cache.get("long_ttl")
        assert result is not None

    @pytest.mark.asyncio
    async def test_disabled_cache(self, sample_result):
        """Test that disabled cache doesn't store anything."""
        config = EntityCacheConfig(enabled=False)
        cache = EntityExtractionCache(config=config)

        await cache.put("hash", sample_result)
        result = await cache.get("hash")

        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self, cache, sample_result):
        """Test delete operation."""
        content_hash = "test_hash"
        await cache.put(content_hash, sample_result, document_id="doc_1")

        deleted = await cache.delete(content_hash)
        assert deleted is True

        # Document mapping should also be cleaned
        deleted_by_doc = await cache.delete_by_document_id("doc_1")
        assert deleted_by_doc is False

    @pytest.mark.asyncio
    async def test_entity_extraction_result_dataclass(self):
        """Test EntityExtractionResult dataclass."""
        result = EntityExtractionResult(
            entities=[{"name": "Test"}],
            relationships=[],
            raw_response="test response",
            model_used="test-model",
        )

        assert result.entities == [{"name": "Test"}]
        assert result.relationships == []
        assert result.raw_response == "test response"
        assert result.model_used == "test-model"

    @pytest.mark.asyncio
    async def test_entity_extraction_result_defaults(self):
        """Test EntityExtractionResult default values."""
        result = EntityExtractionResult()

        assert result.entities == []
        assert result.relationships == []
        assert result.raw_response == ""
        assert result.model_used == ""
