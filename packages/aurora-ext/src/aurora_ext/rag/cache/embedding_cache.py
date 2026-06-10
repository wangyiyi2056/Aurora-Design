"""Embedding similarity cache implementation.

Caches embedding vectors and provides similarity-based cache hits,
allowing semantically similar queries to reuse cached embeddings.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import math
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Optional

from aurora_ext.rag.cache.base import BaseCache, CacheStats
from aurora_ext.rag.cache.config import EmbeddingCacheConfig

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingResult:
    """Cached embedding result.

    Attributes:
        vector: The embedding vector.
        query_text: The original query text.
        model_used: Name of the embedding model used.
        dimensions: Dimensionality of the embedding vector.
    """

    vector: list[float]
    query_text: str
    model_used: str = ""
    dimensions: int = 0


@dataclass
class _EmbeddingCacheEntry:
    """Internal cache entry with metadata.

    Attributes:
        result: The cached embedding result.
        normalized_vector: Pre-normalized vector for fast similarity.
        text_hash: SHA-256 hash of the query text.
        created_at: Unix timestamp when entry was created.
    """

    result: EmbeddingResult
    normalized_vector: list[float]
    text_hash: str
    created_at: float


def _cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """Compute cosine similarity between two vectors.

    Args:
        v1: First vector.
        v2: Second vector.

    Returns:
        Cosine similarity in range [-1, 1].
    """
    if len(v1) != len(v2) or not v1:
        return 0.0

    dot_product = sum(a * b for a, b in zip(v1, v2))
    magnitude1 = math.sqrt(sum(a * a for a in v1))
    magnitude2 = math.sqrt(sum(b * b for b in v2))

    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0

    return dot_product / (magnitude1 * magnitude2)


def _normalize_vector(vector: list[float]) -> list[float]:
    """Normalize a vector to unit length.

    Args:
        vector: The input vector.

    Returns:
        Normalized vector (unit length), or zero vector if input is zero.
    """
    magnitude = math.sqrt(sum(x * x for x in vector))
    if magnitude == 0:
        return [0.0] * len(vector)
    return [x / magnitude for x in vector]


class EmbeddingSimilarityCache(BaseCache[str, EmbeddingResult]):
    """Cache for embedding vectors with similarity-based lookup.

    Features:
        - Exact match caching via text hash
        - Approximate match via cosine similarity threshold
        - Optional LLM-based secondary verification
        - LRU eviction policy

    Usage:
        cache = EmbeddingSimilarityCache(config)

        # Try cache lookup
        cached = await cache.get_similar(query_text)
        if cached:
            return cached.vector

        # Compute embedding and cache
        embedding = await compute_embedding(query_text)
        await cache.put(query_text, embedding)
    """

    def __init__(
        self,
        config: Optional[EmbeddingCacheConfig] = None,
        llm_verifier: Optional[Any] = None,
    ) -> None:
        """Initialize the embedding similarity cache.

        Args:
            config: Cache configuration (uses defaults if None).
            llm_verifier: Optional LLM callable for secondary verification.
        """
        self._config = config or EmbeddingCacheConfig()
        self._cache: OrderedDict[str, _EmbeddingCacheEntry] = OrderedDict()
        self._lock = asyncio.Lock()
        self._llm_verifier = llm_verifier

        # Statistics
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._similarity_hits = 0  # Hits from similarity matching

    @staticmethod
    def hash_text(text: str) -> str:
        """Generate a SHA-256 hash for text.

        Args:
            text: The query text.

        Returns:
            Hexadecimal hash string.
        """
        # Normalize whitespace for consistent hashing
        normalized = " ".join(text.split())
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    async def get(self, key: str) -> Optional[EmbeddingResult]:
        """Retrieve a cached embedding by exact text hash.

        Args:
            key: The text hash.

        Returns:
            The cached embedding result if found, None otherwise.
        """
        if not self._config.enabled:
            self._misses += 1
            return None

        async with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._misses += 1
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self._hits += 1

            return entry.result

    async def get_similar(
        self,
        query_text: str,
        query_embedding: Optional[list[float]] = None,
    ) -> Optional[tuple[EmbeddingResult, float]]:
        """Find a similar cached embedding.

        First tries exact match, then falls back to similarity search.

        Args:
            query_text: The query text to find embeddings for.
            query_embedding: Optional pre-computed embedding for similarity check.

        Returns:
            Tuple of (cached result, similarity score) if found, None otherwise.
        """
        if not self._config.enabled:
            self._misses += 1
            return None

        # Try exact match first
        text_hash = self.hash_text(query_text)
        exact_result = await self.get(text_hash)
        if exact_result is not None:
            return (exact_result, 1.0)

        # Fall back to similarity search if we have an embedding
        if query_embedding is None:
            self._misses += 1
            return None

        normalized_query = _normalize_vector(query_embedding)
        best_match: Optional[tuple[_EmbeddingCacheEntry, float, str]] = None

        async with self._lock:
            for key, entry in self._cache.items():
                similarity = _cosine_similarity(normalized_query, entry.normalized_vector)

                if similarity >= self._config.similarity_threshold:
                    if best_match is None or similarity > best_match[1]:
                        best_match = (entry, similarity, key)

            if best_match is not None:
                entry, similarity, key = best_match

                # Optional LLM verification
                if self._config.use_llm_verify and self._llm_verifier:
                    is_equivalent = await self._verify_with_llm(
                        query_text, entry.result.query_text
                    )
                    if not is_equivalent:
                        self._misses += 1
                        return None

                # Move to end (most recently used)
                self._cache.move_to_end(key)
                self._hits += 1
                self._similarity_hits += 1

                return (entry.result, similarity)

        self._misses += 1
        return None

    async def put(
        self,
        key: str,
        value: EmbeddingResult,
        ttl: Optional[int] = None,
        text: Optional[str] = None,
    ) -> None:
        """Store an embedding in the cache.

        Args:
            key: The text hash (or use text parameter to compute it).
            value: The embedding result to cache.
            ttl: TTL is not used for embedding cache (entries persist until evicted).
            text: Optional original text (used if key is not a hash).
        """
        if not self._config.enabled:
            return

        actual_key = key if not text else self.hash_text(text)
        normalized_vector = _normalize_vector(value.vector)

        async with self._lock:
            # Evict LRU entries if at capacity
            while len(self._cache) >= self._config.max_size:
                oldest_key, _ = self._cache.popitem(last=False)
                self._evictions += 1
                logger.debug("Evicted LRU embedding entry: %s", oldest_key[:16])

            # Add or update entry
            self._cache[actual_key] = _EmbeddingCacheEntry(
                result=value,
                normalized_vector=normalized_vector,
                text_hash=actual_key,
                created_at=time.time(),
            )
            self._cache.move_to_end(actual_key)

    async def delete(self, key: str) -> bool:
        """Remove a cached embedding.

        Args:
            key: The text hash to remove.

        Returns:
            True if the key was found and removed.
        """
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    async def clear(self) -> int:
        """Clear all cached embeddings.

        Returns:
            Number of entries that were cleared.
        """
        async with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._hits = 0
            self._misses = 0
            self._evictions = 0
            self._similarity_hits = 0
            return count

    async def stats(self) -> CacheStats:
        """Retrieve cache statistics.

        Returns:
            Current cache statistics snapshot.
        """
        async with self._lock:
            # Estimate memory usage (vector size + overhead)
            memory_bytes = sum(
                len(entry.result.vector) * 8  # float64 = 8 bytes
                + len(entry.result.query_text.encode("utf-8"))
                + 100  # entry overhead
                for entry in self._cache.values()
            )

            return CacheStats(
                hits=self._hits,
                misses=self._misses,
                evictions=self._evictions,
                size=len(self._cache),
                memory_bytes=memory_bytes,
            )

    async def contains(self, key: str) -> bool:
        """Check if a key exists without updating stats.

        Args:
            key: The text hash to check.

        Returns:
            True if the key exists.
        """
        async with self._lock:
            return key in self._cache

    async def _verify_with_llm(self, query1: str, query2: str) -> bool:
        """Use LLM to verify semantic equivalence of two queries.

        Args:
            query1: First query text.
            query2: Second query text.

        Returns:
            True if queries are semantically equivalent.
        """
        if not self._llm_verifier:
            return True

        try:
            prompt = (
                "Are the following two queries semantically equivalent? "
                "Answer only 'yes' or 'no'.\n\n"
                f"Query 1: {query1}\n"
                f"Query 2: {query2}"
            )

            if asyncio.iscoroutinefunction(self._llm_verifier):
                response = await self._llm_verifier(prompt)
            else:
                response = self._llm_verifier(prompt)

            return "yes" in str(response).lower()
        except Exception as e:
            logger.warning("LLM verification failed: %s", e)
            return False

    def get_similarity_stats(self) -> dict[str, Any]:
        """Get extended statistics about similarity matching.

        Returns:
            Dictionary with similarity-specific statistics.
        """
        return {
            "similarity_hits": self._similarity_hits,
            "similarity_threshold": self._config.similarity_threshold,
            "use_llm_verify": self._config.use_llm_verify,
        }
