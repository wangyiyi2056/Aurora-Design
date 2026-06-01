"""Cache statistics collector.

Aggregates statistics from all cache layers and provides
a unified view of cache performance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from aurora_ext.rag.cache.base import CacheStats


@dataclass(frozen=True)
class MultiLayerCacheStats:
    """Aggregated statistics across all cache layers.

    Attributes:
        llm: Statistics for LLM response cache.
        entity: Statistics for entity extraction cache.
        embedding: Statistics for embedding similarity cache.
        total_hits: Combined hits across all layers.
        total_misses: Combined misses across all layers.
        total_evictions: Combined evictions across all layers.
        total_memory_bytes: Combined memory usage across all layers.
    """

    llm: CacheStats = field(default_factory=CacheStats)
    entity: CacheStats = field(default_factory=CacheStats)
    embedding: CacheStats = field(default_factory=CacheStats)

    @property
    def total_hits(self) -> int:
        """Total cache hits across all layers."""
        return self.llm.hits + self.entity.hits + self.embedding.hits

    @property
    def total_misses(self) -> int:
        """Total cache misses across all layers."""
        return self.llm.misses + self.entity.misses + self.embedding.misses

    @property
    def total_evictions(self) -> int:
        """Total evictions across all layers."""
        return self.llm.evictions + self.entity.evictions + self.embedding.evictions

    @property
    def total_memory_bytes(self) -> int:
        """Total memory usage across all layers."""
        return self.llm.memory_bytes + self.entity.memory_bytes + self.embedding.memory_bytes

    @property
    def overall_hit_rate(self) -> float:
        """Overall cache hit rate across all layers."""
        total = self.total_hits + self.total_misses
        return self.total_hits / total if total > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses.

        Returns:
            Dictionary with per-layer and aggregate statistics.
        """
        return {
            "layers": {
                "llm": self.llm.to_dict(),
                "entity": self.entity.to_dict(),
                "embedding": self.embedding.to_dict(),
            },
            "aggregate": {
                "total_hits": self.total_hits,
                "total_misses": self.total_misses,
                "total_evictions": self.total_evictions,
                "total_memory_bytes": self.total_memory_bytes,
                "overall_hit_rate": round(self.overall_hit_rate, 4),
            },
        }


class CacheStatsCollector:
    """Collects and aggregates statistics from multiple cache layers.

    Usage:
        collector = CacheStatsCollector()
        collector.register("llm", llm_cache)
        collector.register("entity", entity_cache)
        collector.register("embedding", embedding_cache)

        stats = await collector.collect_all()
        print(stats.to_dict())
    """

    def __init__(self) -> None:
        """Initialize the statistics collector."""
        self._caches: dict[str, Any] = {}

    def register(self, name: str, cache: Any) -> None:
        """Register a cache layer for statistics collection.

        Args:
            name: Name identifier for the cache layer.
            cache: Cache instance implementing BaseCache interface.
        """
        self._caches[name] = cache

    def unregister(self, name: str) -> None:
        """Unregister a cache layer.

        Args:
            name: Name identifier to unregister.
        """
        self._caches.pop(name, None)

    async def collect(self, name: str) -> Optional[CacheStats]:
        """Collect statistics for a specific cache layer.

        Args:
            name: Name of the cache layer.

        Returns:
            Cache statistics or None if layer not registered.
        """
        cache = self._caches.get(name)
        if cache is None:
            return None
        return await cache.stats()

    async def collect_all(self) -> MultiLayerCacheStats:
        """Collect statistics from all registered cache layers.

        Returns:
            Aggregated multi-layer cache statistics.
        """
        llm_stats = CacheStats()
        entity_stats = CacheStats()
        embedding_stats = CacheStats()

        if "llm" in self._caches:
            llm_stats = await self._caches["llm"].stats()

        if "entity" in self._caches:
            entity_stats = await self._caches["entity"].stats()

        if "embedding" in self._caches:
            embedding_stats = await self._caches["embedding"].stats()

        return MultiLayerCacheStats(
            llm=llm_stats,
            entity=entity_stats,
            embedding=embedding_stats,
        )

    def get_registered_layers(self) -> list[str]:
        """Get list of registered cache layer names.

        Returns:
            List of registered cache layer names.
        """
        return list(self._caches.keys())
