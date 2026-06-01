"""Multi-layer intelligent cache management system.

Provides LLM response caching, entity extraction caching, and
embedding similarity caching with LRU eviction and TTL expiration.

Usage:
    from aurora_ext.rag.cache import CacheManager, CacheConfig

    config = CacheConfig.from_dict(toml_config)
    manager = CacheManager(config, working_dir="./storage")

    # LLM caching
    prompt_hash = manager.llm.hash_prompt(prompt)
    response = await manager.llm.get(prompt_hash)
    if response is None:
        response = await llm.generate(prompt)
        await manager.llm.put(prompt_hash, response)

    # Entity extraction caching
    content_hash = manager.entity.hash_content(document)
    result = await manager.entity.get(content_hash)

    # Embedding similarity caching
    cached = await manager.embedding.get_similar(query, embedding)

    # Statistics
    stats = await manager.get_stats()

    # Clear by query mode
    await manager.clear_by_mode("hybrid")
"""

from aurora_ext.rag.cache.base import BaseCache, CacheStats
from aurora_ext.rag.cache.config import (
    CacheConfig,
    EmbeddingCacheConfig,
    EntityCacheConfig,
    LLMCacheConfig,
)
from aurora_ext.rag.cache.embedding_cache import EmbeddingResult, EmbeddingSimilarityCache
from aurora_ext.rag.cache.entity_cache import EntityExtractionCache, EntityExtractionResult
from aurora_ext.rag.cache.llm_cache import LLMResponseCache
from aurora_ext.rag.cache.manager import CacheManager, QueryMode
from aurora_ext.rag.cache.stats import CacheStatsCollector, MultiLayerCacheStats

__all__ = [
    # Core interfaces
    "BaseCache",
    "CacheStats",
    # Configuration
    "CacheConfig",
    "LLMCacheConfig",
    "EntityCacheConfig",
    "EmbeddingCacheConfig",
    # Cache implementations
    "LLMResponseCache",
    "EntityExtractionCache",
    "EntityExtractionResult",
    "EmbeddingSimilarityCache",
    "EmbeddingResult",
    # Manager and stats
    "CacheManager",
    "QueryMode",
    "CacheStatsCollector",
    "MultiLayerCacheStats",
]
