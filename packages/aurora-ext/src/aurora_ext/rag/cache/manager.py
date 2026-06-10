"""Cache manager orchestrating all cache layers.

Provides a unified interface for cache operations across LLM,
entity extraction, and embedding caches. Supports selective
clearing based on query mode.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Optional

from aurora_ext.rag.cache.config import CacheConfig
from aurora_ext.rag.cache.embedding_cache import (
    EmbeddingResult,
    EmbeddingSimilarityCache,
)
from aurora_ext.rag.cache.entity_cache import (
    EntityExtractionCache,
    EntityExtractionResult,
)
from aurora_ext.rag.cache.llm_cache import LLMResponseCache
from aurora_ext.rag.cache.stats import CacheStatsCollector, MultiLayerCacheStats

logger = logging.getLogger(__name__)


class QueryMode(str, Enum):
    """Query modes for selective cache clearing."""

    MIX = "mix"
    HYBRID = "hybrid"
    LOCAL = "local"
    GLOBAL = "global"
    NAIVE = "naive"
    ALL = "all"


class CacheManager:
    """Orchestrator for the multi-layer cache system.

    Coordinates LLM response caching, entity extraction caching,
    and embedding similarity caching. Provides unified operations
    for clearing and statistics.

    Usage:
        config = CacheConfig.from_dict(toml_config)
        manager = CacheManager(config, working_dir="./storage")

        # Use individual caches
        llm_response = await manager.llm.get(prompt_hash)
        entity_result = await manager.entity.get(content_hash)
        embedding_result = await manager.embedding.get_similar(query)

        # Get aggregate statistics
        stats = await manager.get_stats()

        # Clear caches by query mode
        await manager.clear_by_mode(QueryMode.HYBRID)
    """

    def __init__(
        self,
        config: Optional[CacheConfig] = None,
        working_dir: str = "./rag_storage",
        llm_verifier: Optional[Any] = None,
    ) -> None:
        """Initialize the cache manager.

        Args:
            config: Master cache configuration (uses defaults if None).
            working_dir: Base directory for disk persistence.
            llm_verifier: Optional LLM callable for embedding verification.
        """
        self._config = config or CacheConfig()
        self._working_dir = working_dir

        # Initialize cache layers
        self._llm_cache = LLMResponseCache(
            config=self._config.llm if self._config.enabled else None,
            working_dir=working_dir,
        )
        self._entity_cache = EntityExtractionCache(
            config=self._config.entity if self._config.enabled else None,
        )
        self._embedding_cache = EmbeddingSimilarityCache(
            config=self._config.embedding if self._config.enabled else None,
            llm_verifier=llm_verifier,
        )

        # Set up statistics collector
        self._stats_collector = CacheStatsCollector()
        self._stats_collector.register("llm", self._llm_cache)
        self._stats_collector.register("entity", self._entity_cache)
        self._stats_collector.register("embedding", self._embedding_cache)

        logger.info(
            "CacheManager initialized: enabled=%s, llm=%s, entity=%s, embedding=%s",
            self._config.enabled,
            self._config.llm.enabled,
            self._config.entity.enabled,
            self._config.embedding.enabled,
        )

    @property
    def llm(self) -> LLMResponseCache:
        """Access the LLM response cache."""
        return self._llm_cache

    @property
    def entity(self) -> EntityExtractionCache:
        """Access the entity extraction cache."""
        return self._entity_cache

    @property
    def embedding(self) -> EmbeddingSimilarityCache:
        """Access the embedding similarity cache."""
        return self._embedding_cache

    @property
    def config(self) -> CacheConfig:
        """Access the cache configuration."""
        return self._config

    @property
    def is_enabled(self) -> bool:
        """Check if caching is globally enabled."""
        return self._config.enabled

    async def get_stats(self) -> MultiLayerCacheStats:
        """Get aggregated statistics from all cache layers.

        Returns:
            Multi-layer cache statistics.
        """
        return await self._stats_collector.collect_all()

    async def clear_all(self) -> dict[str, int]:
        """Clear all cache layers.

        Returns:
            Dictionary mapping cache layer names to cleared counts.
        """
        results = {
            "llm": await self._llm_cache.clear(),
            "entity": await self._entity_cache.clear(),
            "embedding": await self._embedding_cache.clear(),
        }
        total = sum(results.values())
        logger.info("Cleared all caches: %d entries total", total)
        return results

    async def clear_by_mode(self, mode: QueryMode | str) -> dict[str, int]:
        """Clear caches based on query mode.

        Different query modes use different cache layers:
        - mix: All caches (LLM + entity + embedding)
        - hybrid: LLM + entity caches
        - local: Entity + embedding caches
        - global: LLM + entity caches
        - naive: Embedding cache only
        - all: All caches

        Args:
            mode: Query mode determining which caches to clear.

        Returns:
            Dictionary mapping cache layer names to cleared counts.
        """
        if isinstance(mode, str):
            mode = QueryMode(mode)

        results: dict[str, int] = {}

        if mode == QueryMode.ALL or mode == QueryMode.MIX:
            # All caches
            results["llm"] = await self._llm_cache.clear()
            results["entity"] = await self._entity_cache.clear()
            results["embedding"] = await self._embedding_cache.clear()

        elif mode == QueryMode.HYBRID or mode == QueryMode.GLOBAL:
            # LLM + entity (uses KG extraction)
            results["llm"] = await self._llm_cache.clear()
            results["entity"] = await self._entity_cache.clear()

        elif mode == QueryMode.LOCAL:
            # Entity + embedding (uses both KG and vector)
            results["entity"] = await self._entity_cache.clear()
            results["embedding"] = await self._embedding_cache.clear()

        elif mode == QueryMode.NAIVE:
            # Embedding only (pure vector search)
            results["embedding"] = await self._embedding_cache.clear()

        else:
            logger.warning("Unknown query mode: %s", mode)

        total = sum(results.values())
        logger.info("Cleared caches for mode=%s: %d entries total", mode.value, total)
        return results

    async def clear_llm_cache(self) -> int:
        """Clear only the LLM response cache.

        Returns:
            Number of entries cleared.
        """
        return await self._llm_cache.clear()

    async def clear_entity_cache(self) -> int:
        """Clear only the entity extraction cache.

        Returns:
            Number of entries cleared.
        """
        return await self._entity_cache.clear()

    async def clear_embedding_cache(self) -> int:
        """Clear only the embedding similarity cache.

        Returns:
            Number of entries cleared.
        """
        return await self._embedding_cache.clear()

    async def clear_by_document_ids(self, document_ids: list[str]) -> int:
        """Clear entity cache entries for specific documents.

        Args:
            document_ids: List of document IDs to clear.

        Returns:
            Number of entries cleared.
        """
        return await self._entity_cache.clear_by_document_ids(document_ids)

    async def cleanup_expired(self) -> dict[str, int]:
        """Remove expired entries from all cache layers.

        Returns:
            Dictionary mapping cache layer names to cleanup counts.
        """
        results: dict[str, int] = {}

        # LLM cache has TTL-based expiration
        results["llm"] = await self._llm_cache.cleanup_expired()

        # Entity cache has TTL-based expiration
        results["entity"] = await self._entity_cache.cleanup_expired()

        # Embedding cache doesn't use TTL (eviction only)
        results["embedding"] = 0

        total = sum(results.values())
        if total > 0:
            logger.debug("Cleaned up expired entries: %d total", total)

        return results

    async def warm_up(self) -> dict[str, int]:
        """Warm up caches by loading from disk (if persistence enabled).

        Returns:
            Dictionary mapping cache layer names to loaded counts.
        """
        results: dict[str, int] = {}

        # Load LLM cache from disk if persistence enabled
        if self._config.llm.persist_to_disk:
            results["llm"] = await self._llm_cache.load_from_disk()
        else:
            results["llm"] = 0

        # Entity and embedding caches are in-memory only
        results["entity"] = 0
        results["embedding"] = 0

        total = sum(results.values())
        logger.info("Cache warm-up complete: %d entries loaded", total)
        return results

    def get_config_summary(self) -> dict[str, Any]:
        """Get a summary of cache configuration.

        Returns:
            Dictionary with configuration summary.
        """
        return {
            "enabled": self._config.enabled,
            "llm": {
                "enabled": self._config.llm.enabled,
                "ttl": self._config.llm.ttl,
                "max_size": self._config.llm.max_size,
                "persist_to_disk": self._config.llm.persist_to_disk,
            },
            "entity": {
                "enabled": self._config.entity.enabled,
                "ttl": self._config.entity.ttl,
                "max_size": self._config.entity.max_size,
            },
            "embedding": {
                "enabled": self._config.embedding.enabled,
                "similarity_threshold": self._config.embedding.similarity_threshold,
                "use_llm_verify": self._config.embedding.use_llm_verify,
                "max_size": self._config.embedding.max_size,
            },
        }
