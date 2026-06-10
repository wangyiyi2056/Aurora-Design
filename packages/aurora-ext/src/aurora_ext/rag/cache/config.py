"""Cache configuration dataclasses.

Frozen dataclasses for configuring the multi-layer cache system.
All configurations are immutable to ensure thread safety.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class LLMCacheConfig:
    """Configuration for LLM response caching.

    Attributes:
        enabled: Whether LLM caching is active.
        ttl: Time-to-live in seconds (default 24 hours).
        max_size: Maximum number of cached responses.
        persist_to_disk: Whether to persist cache to disk.
        disk_path: Path for disk persistence (relative to working_dir).
    """

    enabled: bool = True
    ttl: int = 86400  # 24 hours
    max_size: int = 10000
    persist_to_disk: bool = False
    disk_path: str = "cache/llm"


@dataclass(frozen=True)
class EntityCacheConfig:
    """Configuration for entity extraction caching.

    Attributes:
        enabled: Whether entity extraction caching is active.
        ttl: Time-to-live in seconds (default 7 days).
        max_size: Maximum number of cached extraction results.
    """

    enabled: bool = True
    ttl: int = 604800  # 7 days
    max_size: int = 5000


@dataclass(frozen=True)
class EmbeddingCacheConfig:
    """Configuration for embedding similarity caching.

    Attributes:
        enabled: Whether embedding caching is active.
        similarity_threshold: Cosine similarity threshold for cache hits.
        use_llm_verify: Whether to use LLM for secondary verification.
        max_size: Maximum number of cached embeddings.
    """

    enabled: bool = True
    similarity_threshold: float = 0.95
    use_llm_verify: bool = False
    max_size: int = 10000


@dataclass(frozen=True)
class CacheConfig:
    """Master configuration for the multi-layer cache system.

    Attributes:
        enabled: Global cache toggle.
        llm: LLM response cache configuration.
        entity: Entity extraction cache configuration.
        embedding: Embedding similarity cache configuration.
    """

    enabled: bool = True
    llm: LLMCacheConfig = LLMCacheConfig()
    entity: EntityCacheConfig = EntityCacheConfig()
    embedding: EmbeddingCacheConfig = EmbeddingCacheConfig()

    @classmethod
    def from_dict(cls, data: dict) -> CacheConfig:
        """Create CacheConfig from a dictionary (e.g., from TOML).

        Args:
            data: Dictionary with cache configuration.

        Returns:
            Immutable CacheConfig instance.
        """
        if not data:
            return cls()

        llm_data = data.get("llm", {})
        entity_data = data.get("entity", {})
        embedding_data = data.get("embedding", {})

        # Handle flat config format (from aurora.toml)
        if "llm_cache_ttl" in data:
            llm_data = {
                "enabled": data.get("llm_cache_enabled", True),
                "ttl": data.get("llm_cache_ttl", 86400),
                "max_size": data.get("llm_cache_max_size", 10000),
                "persist_to_disk": data.get("llm_cache_persist", False),
            }

        if "entity_cache_enabled" in data:
            entity_data = {
                "enabled": data.get("entity_cache_enabled", True),
                "ttl": data.get("entity_cache_ttl", 604800),
                "max_size": data.get("entity_cache_max_size", 5000),
            }

        if "embedding_cache_threshold" in data:
            embedding_data = {
                "enabled": data.get("embedding_cache_enabled", True),
                "similarity_threshold": data.get("embedding_cache_threshold", 0.95),
                "use_llm_verify": data.get("embedding_cache_use_llm_verify", False),
                "max_size": data.get("embedding_cache_max_size", 10000),
            }

        return cls(
            enabled=data.get("enabled", True),
            llm=LLMCacheConfig(**llm_data) if llm_data else LLMCacheConfig(),
            entity=EntityCacheConfig(**entity_data) if entity_data else EntityCacheConfig(),
            embedding=EmbeddingCacheConfig(**embedding_data) if embedding_data else EmbeddingCacheConfig(),
        )
