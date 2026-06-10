"""Tests for LLM response cache.

Covers TTL expiration, LRU eviction, disk persistence, and statistics.
"""

import asyncio
import os
import tempfile
import time

import pytest

from aurora_ext.rag.cache.llm_cache import LLMResponseCache
from aurora_ext.rag.cache.config import LLMCacheConfig


@pytest.fixture
def config():
    """Default test configuration."""
    return LLMCacheConfig(
        enabled=True,
        ttl=10,  # Short TTL for testing
        max_size=5,  # Small size for testing eviction
        persist_to_disk=False,
    )


@pytest.fixture
def cache(config):
    """Create a test cache instance."""
    return LLMResponseCache(config=config, working_dir=tempfile.mkdtemp())


@pytest.fixture
def disk_cache():
    """Create a cache with disk persistence."""
    config = LLMCacheConfig(
        enabled=True,
        ttl=60,
        max_size=10,
        persist_to_disk=True,
        disk_path="cache/llm_test",
    )
    working_dir = tempfile.mkdtemp()
    return LLMResponseCache(config=config, working_dir=working_dir)


class TestLLMResponseCache:
    """Test suite for LLMResponseCache."""

    @pytest.mark.asyncio
    async def test_put_and_get(self, cache):
        """Test basic put and get operations."""
        prompt = "What is the capital of France?"
        response = "The capital of France is Paris."
        key = cache.hash_prompt(prompt)

        await cache.put(key, response)
        result = await cache.get(key)

        assert result == response

    @pytest.mark.asyncio
    async def test_get_miss(self, cache):
        """Test get returns None for missing key."""
        result = await cache.get("nonexistent_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_hash_prompt_deterministic(self, cache):
        """Test that hashing is deterministic."""
        prompt = "Test prompt"
        hash1 = cache.hash_prompt(prompt)
        hash2 = cache.hash_prompt(prompt)
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex digest

    @pytest.mark.asyncio
    async def test_hash_prompt_different_inputs(self, cache):
        """Test that different prompts produce different hashes."""
        hash1 = cache.hash_prompt("Prompt A")
        hash2 = cache.hash_prompt("Prompt B")
        assert hash1 != hash2

    @pytest.mark.asyncio
    async def test_ttl_expiration(self, cache):
        """Test that entries expire after TTL."""
        # Use very short TTL
        key = "test_key"
        await cache.put(key, "value", ttl=1)

        # Should exist immediately
        result = await cache.get(key)
        assert result == "value"

        # Wait for expiration
        await asyncio.sleep(1.5)

        # Should be expired
        result = await cache.get(key)
        assert result is None

    @pytest.mark.asyncio
    async def test_lru_eviction(self, config):
        """Test LRU eviction when cache is full."""
        cache = LLMResponseCache(config=config, working_dir=tempfile.mkdtemp())

        # Fill cache to capacity (max_size=5)
        for i in range(5):
            await cache.put(f"key_{i}", f"value_{i}")

        # Add one more to trigger eviction
        await cache.put("key_5", "value_5")

        # First entry should be evicted (LRU)
        result = await cache.get("key_0")
        assert result is None

        # Last entry should exist
        result = await cache.get("key_5")
        assert result == "value_5"

    @pytest.mark.asyncio
    async def test_lru_access_updates_order(self, config):
        """Test that accessing an entry moves it to MRU position."""
        cache = LLMResponseCache(config=config, working_dir=tempfile.mkdtemp())

        # Fill cache
        for i in range(5):
            await cache.put(f"key_{i}", f"value_{i}")

        # Access key_0 to move it to MRU
        await cache.get("key_0")

        # Add new entry to trigger eviction
        await cache.put("key_5", "value_5")

        # key_1 should be evicted (it's now the LRU)
        result = await cache.get("key_1")
        assert result is None

        # key_0 should still exist
        result = await cache.get("key_0")
        assert result == "value_0"

    @pytest.mark.asyncio
    async def test_delete(self, cache):
        """Test delete operation."""
        key = "test_key"
        await cache.put(key, "value")

        # Should exist
        assert await cache.contains(key)

        # Delete
        deleted = await cache.delete(key)
        assert deleted is True

        # Should not exist
        assert not await cache.contains(key)

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, cache):
        """Test deleting a nonexistent key."""
        deleted = await cache.delete("nonexistent")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_clear(self, cache):
        """Test clearing all entries."""
        for i in range(3):
            await cache.put(f"key_{i}", f"value_{i}")

        cleared = await cache.clear()
        assert cleared == 3

        # All entries should be gone
        for i in range(3):
            result = await cache.get(f"key_{i}")
            assert result is None

    @pytest.mark.asyncio
    async def test_contains(self, cache):
        """Test contains check."""
        key = "test_key"

        # Should not contain initially
        assert not await cache.contains(key)

        # Add entry
        await cache.put(key, "value")

        # Should contain now
        assert await cache.contains(key)

    @pytest.mark.asyncio
    async def test_stats(self, cache):
        """Test statistics tracking."""
        # Add some entries
        for i in range(3):
            await cache.put(f"key_{i}", f"value_{i}")

        # Generate hits and misses
        await cache.get("key_0")  # hit
        await cache.get("key_1")  # hit
        await cache.get("nonexistent")  # miss

        stats = await cache.stats()

        assert stats.hits == 2
        assert stats.misses == 1
        assert stats.size == 3
        assert stats.hit_rate == 2 / 3

    @pytest.mark.asyncio
    async def test_stats_hit_rate_zero_requests(self, cache):
        """Test hit rate with no requests."""
        stats = await cache.stats()
        assert stats.hit_rate == 0.0

    @pytest.mark.asyncio
    async def test_cleanup_expired(self, cache):
        """Test cleaning up expired entries."""
        # Add entries with different TTLs
        await cache.put("short_ttl", "value1", ttl=1)
        await cache.put("long_ttl", "value2", ttl=60)

        # Wait for short TTL to expire
        await asyncio.sleep(1.5)

        # Cleanup expired
        cleaned = await cache.cleanup_expired()
        assert cleaned == 1

        # Long TTL entry should still exist
        result = await cache.get("long_ttl")
        assert result == "value2"

    @pytest.mark.asyncio
    async def test_disabled_cache(self):
        """Test that disabled cache doesn't store anything."""
        config = LLMCacheConfig(enabled=False)
        cache = LLMResponseCache(config=config, working_dir=tempfile.mkdtemp())

        await cache.put("key", "value")
        result = await cache.get("key")

        assert result is None

    @pytest.mark.asyncio
    async def test_disk_persistence(self, disk_cache):
        """Test disk persistence of cache."""
        key = "persist_key"
        value = "persisted_value"

        await disk_cache.put(key, value)

        # Create new cache instance with same path
        new_cache = LLMResponseCache(
            config=disk_cache._config,
            working_dir=disk_cache._working_dir,
        )

        # Load from disk
        loaded = await new_cache.load_from_disk()
        assert loaded == 1

        # Should find the value
        result = await new_cache.get(key)
        assert result == value

    @pytest.mark.asyncio
    async def test_get_or_set(self, cache):
        """Test get_or_set operation."""
        key = "test_key"

        # First call should compute and cache
        result1 = await cache.get_or_set(key, lambda: "computed_value")
        assert result1 == "computed_value"

        # Second call should return cached value
        call_count = 0

        def factory():
            nonlocal call_count
            call_count += 1
            return "new_value"

        result2 = await cache.get_or_set(key, factory)
        assert result2 == "computed_value"
        assert call_count == 0  # Factory should not be called

    @pytest.mark.asyncio
    async def test_get_or_set_async_factory(self, cache):
        """Test get_or_set with async factory."""
        key = "async_key"

        async def async_factory():
            return "async_computed"

        result = await cache.get_or_set(key, async_factory)
        assert result == "async_computed"

    @pytest.mark.asyncio
    async def test_stats_to_dict(self, cache):
        """Test statistics serialization to dict."""
        await cache.put("key", "value")
        await cache.get("key")

        stats = await cache.stats()
        stats_dict = stats.to_dict()

        assert "hits" in stats_dict
        assert "misses" in stats_dict
        assert "hit_rate" in stats_dict
        assert stats_dict["hits"] == 1
