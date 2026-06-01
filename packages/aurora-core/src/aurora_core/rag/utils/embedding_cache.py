"""Three-tier embedding cache: exact → approximate → compute.

Caches embedding vectors to avoid redundant API calls. Supports:

- **Exact match**: hash-based dict lookup for identical texts.
- **Approximate match**: cosine similarity between query embedding and cached
  embeddings. If similarity ≥ threshold, reuse the cached vector.
- **LRU eviction**: evicts least-recently-used entries when capacity is reached.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmbeddingCacheConfig:
    """Configuration for the embedding cache.

    Attributes
    ----------
    enabled:
        Whether caching is active. When ``False``, all operations are no-ops.
    similarity_threshold:
        Minimum cosine similarity for an approximate cache hit.
        Values closer to 1.0 require near-identical embeddings.
    use_llm_check:
        Reserved for future use: verify approximate hits with an LLM
        semantic equivalence check.
    max_cache_size:
        Maximum number of entries before LRU eviction kicks in.
    """

    enabled: bool = False
    similarity_threshold: float = 0.95
    use_llm_check: bool = False
    max_cache_size: int = 10000


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b) or not a:
        return 0.0

    dot_product = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return dot_product / (norm_a * norm_b)


def _text_hash(text: str) -> str:
    """Compute a stable hash for a text string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class _CacheEntry:
    """Internal cache entry holding text, embedding, and access metadata."""

    text: str
    embedding: List[float]
    text_hash: str


class EmbeddingCache:
    """Three-tier embedding cache: exact → approximate → compute.

    Thread-safe via ``asyncio.Lock``. Supports LRU eviction when the
    cache exceeds ``max_cache_size``.

    Parameters
    ----------
    config:
        Cache configuration.

    Usage::

        cache = EmbeddingCache(EmbeddingCacheConfig(enabled=True))
        cached = await cache.get("What is AI?")
        if cached is None:
            embedding = await compute_embedding("What is AI?")
            await cache.put("What is AI?", embedding)
    """

    def __init__(self, config: EmbeddingCacheConfig) -> None:
        self._config = config
        self._cache: OrderedDict[str, _CacheEntry] = OrderedDict()
        self._lock = asyncio.Lock()

        self._hits = 0
        self._approximate_hits = 0
        self._misses = 0
        self._evictions = 0

    @property
    def enabled(self) -> bool:
        """Whether the cache is active."""
        return self._config.enabled

    async def get(self, text: str) -> Optional[List[float]]:
        """Check cache for exact or approximate match.

        Parameters
        ----------
        text:
            The query text.

        Returns
        -------
        list[float] | None
            Cached embedding if a match is found, otherwise ``None``.
        """
        if not self._config.enabled:
            return None

        text_hash = _text_hash(text)

        async with self._lock:
            if text_hash in self._cache:
                self._hits += 1
                self._cache.move_to_end(text_hash)
                logger.debug("Embedding cache exact hit for hash=%s", text_hash[:8])
                return list(self._cache[text_hash].embedding)

            self._misses += 1
            return None

    async def get_approximate(
        self, query_embedding: List[float]
    ) -> Optional[Tuple[List[float], float]]:
        """Check cache for an approximate match using cosine similarity.

        This is a second-tier lookup called after exact match fails.
        Requires the query embedding to compare against cached vectors.

        Parameters
        ----------
        query_embedding:
            The embedding vector of the query text.

        Returns
        -------
        tuple[list[float], float] | None
            A tuple of (cached_embedding, similarity) if a match ≥ threshold
            is found, otherwise ``None``.
        """
        if not self._config.enabled:
            return None

        async with self._lock:
            best_match: Optional[Tuple[str, List[float], float]] = None

            for key, entry in self._cache.items():
                similarity = _cosine_similarity(query_embedding, entry.embedding)
                if similarity >= self._config.similarity_threshold:
                    if best_match is None or similarity > best_match[2]:
                        best_match = (key, entry.embedding, similarity)

            if best_match is not None:
                key, cached_embedding, similarity = best_match
                self._approximate_hits += 1
                self._cache.move_to_end(key)
                logger.debug(
                    "Embedding cache approximate hit: key=%s, similarity=%.4f",
                    key[:8],
                    similarity,
                )
                return list(cached_embedding), similarity

            return None

    async def put(self, text: str, embedding: List[float]) -> None:
        """Store an embedding in the cache.

        If the cache is full, the least-recently-used entry is evicted.

        Parameters
        ----------
        text:
            The source text.
        embedding:
            The embedding vector to cache.
        """
        if not self._config.enabled:
            return

        text_hash = _text_hash(text)

        async with self._lock:
            if text_hash in self._cache:
                self._cache.move_to_end(text_hash)
                self._cache[text_hash].embedding = list(embedding)
                return

            while len(self._cache) >= self._config.max_cache_size:
                evicted_key, _ = self._cache.popitem(last=False)
                self._evictions += 1
                logger.debug(
                    "Embedding cache eviction: key=%s", evicted_key[:8]
                )

            self._cache[text_hash] = _CacheEntry(
                text=text,
                embedding=list(embedding),
                text_hash=text_hash,
            )

    async def clear(self) -> None:
        """Clear all cached entries and reset statistics."""
        async with self._lock:
            self._cache.clear()
            self._hits = 0
            self._approximate_hits = 0
            self._misses = 0
            self._evictions = 0
        logger.info("Embedding cache cleared")

    def stats(self) -> Dict[str, int]:
        """Return cache statistics.

        Returns
        -------
        dict
            Keys: ``hits``, ``approximate_hits``, ``misses``, ``evictions``,
            ``size``, ``max_size``.
        """
        total = self._hits + self._approximate_hits + self._misses
        return {
            "hits": self._hits,
            "approximate_hits": self._approximate_hits,
            "misses": self._misses,
            "evictions": self._evictions,
            "total_requests": total,
            "hit_rate": (
                (self._hits + self._approximate_hits) / total
                if total > 0
                else 0.0
            ),
            "size": len(self._cache),
            "max_size": self._config.max_cache_size,
            "enabled": self._config.enabled,
        }
