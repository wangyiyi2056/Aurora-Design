"""Tests for cache manager orchestrator.

Covers initialization, selective clearing, statistics aggregation,
and configuration management.
"""

import asyncio
import tempfile

import pytest

from aurora_ext.rag.cache import (
    CacheConfig,
    CacheManager,
    EmbeddingCacheConfig,
    EntityCacheConfig,
    LLMCacheConfig,
    QueryMode,
)
from aurora_ext.rag.cache.embedding_cache import EmbeddingResult
from aurora_ext.rag.cache.entity_cache import EntityExtractionResult
from aurora_ext.rag.cache.stats import MultiLayerCacheStats


@pytest.fixture
def config():
    """Default test configuration."""
    return CacheConfig(
        enabled=True,
        llm=LLMCacheConfig(enabled=True, ttl=60, max_size=10),
        entity=EntityCacheConfig(enabled=True, ttl=60, max_size=10),
        embedding=EmbeddingCacheConfig(enabled=True, similarity_threshold=0.95),
    )


@pytest.fixture
def manager(config):
    """Create a test cache manager instance."""
    return CacheManager(config=config, working_dir=tempfile.mkdtemp())


@pytest.fixture
def sample_entity_result():
    """Sample entity extraction result."""
    return EntityExtractionResult(
        entities=[{"name": "Test", "type": "concept"}],
        relationships=[],
        raw_response="test response",
    )


@pytest.fixture
def sample_embedding_result():
    """Sample embedding result."""
    return EmbeddingResult(
        vector=[0.1, 0.2, 0.3],
        query_text="test query",
    )


class TestCacheManager:
    """Test suite for CacheManager."""

    def test_initialization(self, manager, config):
        """Test manager initialization."""
        assert manager.is_enabled is True
        assert manager.config.enabled is True
        assert manager.llm is not None
        assert manager.entity is not None
        assert manager.embedding is not None

    def test_initialization_with_defaults(self):
        """Test initialization with default configuration."""
        manager = CacheManager()
        assert manager.is_enabled is True

    @pytest.mark.asyncio
    async def test_llm_cache_operations(self, manager):
        """Test LLM cache through manager."""
        prompt = "What is Python?"
        response = "Python is a programming language."
        prompt_hash = manager.llm.hash_prompt(prompt)

        # Put
        await manager.llm.put(prompt_hash, response)

        # Get
        result = await manager.llm.get(prompt_hash)
        assert result == response

    @pytest.mark.asyncio
    async def test_entity_cache_operations(self, manager, sample_entity_result):
        """Test entity cache through manager."""
        content = "Test document content"
        content_hash = manager.entity.hash_content(content)

        # Put
        await manager.entity.put(content_hash, sample_entity_result)

        # Get
        result = await manager.entity.get(content_hash)
        assert result is not None
        assert result.entities == sample_entity_result.entities

    @pytest.mark.asyncio
    async def test_embedding_cache_operations(self, manager, sample_embedding_result):
        """Test embedding cache through manager."""
        text = "test query"
        text_hash = manager.embedding.hash_text(text)

        # Put
        await manager.embedding.put(text_hash, sample_embedding_result)

        # Get
        result = await manager.embedding.get(text_hash)
        assert result is not None
        assert result.vector == sample_embedding_result.vector

    @pytest.mark.asyncio
    async def test_get_stats(self, manager, sample_entity_result, sample_embedding_result):
        """Test getting aggregated statistics."""
        # Add some entries to each cache
        await manager.llm.put("llm_key", "llm_value")
        await manager.entity.put("entity_key", sample_entity_result)
        await manager.embedding.put("embed_key", sample_embedding_result)

        # Generate some hits/misses
        await manager.llm.get("llm_key")
        await manager.llm.get("missing")

        stats = await manager.get_stats()

        assert isinstance(stats, MultiLayerCacheStats)
        assert stats.llm.size == 1
        assert stats.entity.size == 1
        assert stats.embedding.size == 1
        assert stats.llm.hits == 1
        assert stats.llm.misses == 1

    @pytest.mark.asyncio
    async def test_clear_all(self, manager, sample_entity_result, sample_embedding_result):
        """Test clearing all caches."""
        # Add entries
        await manager.llm.put("llm_key", "llm_value")
        await manager.entity.put("entity_key", sample_entity_result)
        await manager.embedding.put("embed_key", sample_embedding_result)

        # Clear all
        results = await manager.clear_all()

        assert results["llm"] == 1
        assert results["entity"] == 1
        assert results["embedding"] == 1

        # Verify all cleared
        stats = await manager.get_stats()
        assert stats.llm.size == 0
        assert stats.entity.size == 0
        assert stats.embedding.size == 0

    @pytest.mark.asyncio
    async def test_clear_by_mode_all(self, manager, sample_entity_result, sample_embedding_result):
        """Test clearing by mode: all."""
        await manager.llm.put("key", "value")
        await manager.entity.put("key", sample_entity_result)
        await manager.embedding.put("key", sample_embedding_result)

        results = await manager.clear_by_mode(QueryMode.ALL)

        assert results["llm"] == 1
        assert results["entity"] == 1
        assert results["embedding"] == 1

    @pytest.mark.asyncio
    async def test_clear_by_mode_mix(self, manager, sample_entity_result, sample_embedding_result):
        """Test clearing by mode: mix (all caches)."""
        await manager.llm.put("key", "value")
        await manager.entity.put("key", sample_entity_result)
        await manager.embedding.put("key", sample_embedding_result)

        results = await manager.clear_by_mode(QueryMode.MIX)

        assert "llm" in results
        assert "entity" in results
        assert "embedding" in results

    @pytest.mark.asyncio
    async def test_clear_by_mode_hybrid(self, manager, sample_entity_result, sample_embedding_result):
        """Test clearing by mode: hybrid (LLM + entity)."""
        await manager.llm.put("key", "value")
        await manager.entity.put("key", sample_entity_result)
        await manager.embedding.put("key", sample_embedding_result)

        results = await manager.clear_by_mode(QueryMode.HYBRID)

        assert "llm" in results
        assert "entity" in results
        assert "embedding" not in results

    @pytest.mark.asyncio
    async def test_clear_by_mode_local(self, manager, sample_entity_result, sample_embedding_result):
        """Test clearing by mode: local (entity + embedding)."""
        await manager.llm.put("key", "value")
        await manager.entity.put("key", sample_entity_result)
        await manager.embedding.put("key", sample_embedding_result)

        results = await manager.clear_by_mode(QueryMode.LOCAL)

        assert "llm" not in results
        assert "entity" in results
        assert "embedding" in results

    @pytest.mark.asyncio
    async def test_clear_by_mode_naive(self, manager, sample_entity_result, sample_embedding_result):
        """Test clearing by mode: naive (embedding only)."""
        await manager.llm.put("key", "value")
        await manager.entity.put("key", sample_entity_result)
        await manager.embedding.put("key", sample_embedding_result)

        results = await manager.clear_by_mode(QueryMode.NAIVE)

        assert "llm" not in results
        assert "entity" not in results
        assert "embedding" in results

    @pytest.mark.asyncio
    async def test_clear_by_mode_string(self, manager, sample_entity_result):
        """Test clearing by mode with string input."""
        await manager.llm.put("key", "value")

        results = await manager.clear_by_mode("all")

        assert results["llm"] == 1

    @pytest.mark.asyncio
    async def test_clear_llm_cache(self, manager):
        """Test clearing only LLM cache."""
        await manager.llm.put("key1", "value1")
        await manager.llm.put("key2", "value2")

        cleared = await manager.clear_llm_cache()
        assert cleared == 2

    @pytest.mark.asyncio
    async def test_clear_entity_cache(self, manager, sample_entity_result):
        """Test clearing only entity cache."""
        await manager.entity.put("key1", sample_entity_result)
        await manager.entity.put("key2", sample_entity_result)

        cleared = await manager.clear_entity_cache()
        assert cleared == 2

    @pytest.mark.asyncio
    async def test_clear_embedding_cache(self, manager, sample_embedding_result):
        """Test clearing only embedding cache."""
        await manager.embedding.put("key1", sample_embedding_result)
        await manager.embedding.put("key2", sample_embedding_result)

        cleared = await manager.clear_embedding_cache()
        assert cleared == 2

    @pytest.mark.asyncio
    async def test_clear_by_document_ids(self, manager, sample_entity_result):
        """Test clearing entity cache by document IDs."""
        await manager.entity.put("hash1", sample_entity_result, document_id="doc1")
        await manager.entity.put("hash2", sample_entity_result, document_id="doc2")
        await manager.entity.put("hash3", sample_entity_result, document_id="doc3")

        cleared = await manager.clear_by_document_ids(["doc1", "doc2"])
        assert cleared == 2

        # doc3 should still exist
        result = await manager.entity.get("hash3")
        assert result is not None

    @pytest.mark.asyncio
    async def test_cleanup_expired(self, manager, sample_entity_result):
        """Test cleaning up expired entries."""
        # Add entries with short TTL
        await manager.llm.put("short", "value", ttl=1)
        await manager.entity.put("short", sample_entity_result, ttl=1)

        await asyncio.sleep(1.5)

        cleaned = await manager.cleanup_expired()

        assert cleaned["llm"] == 1
        assert cleaned["entity"] == 1

    def test_get_config_summary(self, manager):
        """Test getting configuration summary."""
        summary = manager.get_config_summary()

        assert summary["enabled"] is True
        assert "llm" in summary
        assert "entity" in summary
        assert "embedding" in summary
        assert summary["llm"]["enabled"] is True
        assert summary["entity"]["enabled"] is True
        assert summary["embedding"]["enabled"] is True


class TestCacheConfig:
    """Test suite for CacheConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = CacheConfig()

        assert config.enabled is True
        assert config.llm.enabled is True
        assert config.llm.ttl == 86400
        assert config.entity.enabled is True
        assert config.embedding.enabled is True
        assert config.embedding.similarity_threshold == 0.95

    def test_from_dict_nested(self):
        """Test creating config from nested dictionary."""
        data = {
            "enabled": True,
            "llm": {"enabled": True, "ttl": 3600, "max_size": 5000},
            "entity": {"enabled": False, "ttl": 7200},
            "embedding": {"similarity_threshold": 0.98},
        }

        config = CacheConfig.from_dict(data)

        assert config.enabled is True
        assert config.llm.ttl == 3600
        assert config.llm.max_size == 5000
        assert config.entity.enabled is False
        assert config.embedding.similarity_threshold == 0.98

    def test_from_dict_flat(self):
        """Test creating config from flat dictionary (TOML format)."""
        data = {
            "enabled": True,
            "llm_cache_enabled": True,
            "llm_cache_ttl": 7200,
            "llm_cache_max_size": 8000,
            "entity_cache_enabled": False,
            "embedding_cache_threshold": 0.97,
        }

        config = CacheConfig.from_dict(data)

        assert config.llm.ttl == 7200
        assert config.llm.max_size == 8000
        assert config.entity.enabled is False
        assert config.embedding.similarity_threshold == 0.97

    def test_from_dict_empty(self):
        """Test creating config from empty dictionary."""
        config = CacheConfig.from_dict({})

        assert config.enabled is True  # Uses defaults

    def test_from_dict_none(self):
        """Test creating config from None."""
        config = CacheConfig.from_dict(None)

        assert config.enabled is True  # Uses defaults

    def test_frozen_dataclass(self):
        """Test that config is immutable."""
        config = CacheConfig()

        with pytest.raises(Exception):  # FrozenInstanceError
            config.enabled = False

    def test_config_subclasses_frozen(self):
        """Test that sub-configs are also frozen."""
        llm_config = LLMCacheConfig()
        entity_config = EntityCacheConfig()
        embedding_config = EmbeddingCacheConfig()

        with pytest.raises(Exception):
            llm_config.enabled = False

        with pytest.raises(Exception):
            entity_config.ttl = 100

        with pytest.raises(Exception):
            embedding_config.similarity_threshold = 0.5


class TestQueryMode:
    """Test suite for QueryMode enum."""

    def test_enum_values(self):
        """Test QueryMode enum values."""
        assert QueryMode.MIX.value == "mix"
        assert QueryMode.HYBRID.value == "hybrid"
        assert QueryMode.LOCAL.value == "local"
        assert QueryMode.GLOBAL.value == "global"
        assert QueryMode.NAIVE.value == "naive"
        assert QueryMode.ALL.value == "all"

    def test_from_string(self):
        """Test creating QueryMode from string."""
        mode = QueryMode("hybrid")
        assert mode == QueryMode.HYBRID

    def test_invalid_string(self):
        """Test creating QueryMode from invalid string."""
        with pytest.raises(ValueError):
            QueryMode("invalid_mode")


class TestMultiLayerCacheStats:
    """Test suite for MultiLayerCacheStats."""

    def test_aggregate_properties(self):
        """Test aggregate statistics calculations."""
        from aurora_ext.rag.cache.base import CacheStats

        stats = MultiLayerCacheStats(
            llm=CacheStats(hits=10, misses=5, evictions=2, size=100, memory_bytes=1000),
            entity=CacheStats(hits=20, misses=10, evictions=5, size=200, memory_bytes=2000),
            embedding=CacheStats(hits=30, misses=15, evictions=8, size=300, memory_bytes=3000),
        )

        assert stats.total_hits == 60
        assert stats.total_misses == 30
        assert stats.total_evictions == 15
        assert stats.total_memory_bytes == 6000
        assert stats.overall_hit_rate == 60 / 90

    def test_to_dict(self):
        """Test serialization to dictionary."""
        stats = MultiLayerCacheStats()
        result = stats.to_dict()

        assert "layers" in result
        assert "aggregate" in result
        assert "llm" in result["layers"]
        assert "entity" in result["layers"]
        assert "embedding" in result["layers"]

    def test_zero_hit_rate(self):
        """Test hit rate with no requests."""
        stats = MultiLayerCacheStats()
        assert stats.overall_hit_rate == 0.0
