"""Entity extraction cache implementation.

Caches entity extraction results for documents based on content hash,
avoiding redundant LLM calls for identical document content.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Optional

from aurora_ext.rag.cache.base import BaseCache, CacheStats
from aurora_ext.rag.cache.config import EntityCacheConfig

logger = logging.getLogger(__name__)


@dataclass
class EntityExtractionResult:
    """Structured entity extraction result.

    Attributes:
        entities: List of extracted entities with their properties.
        relationships: List of extracted relationships.
        raw_response: Original LLM response text.
        model_used: Name of the LLM model used.
    """

    entities: list[dict[str, Any]] = field(default_factory=list)
    relationships: list[dict[str, Any]] = field(default_factory=list)
    raw_response: str = ""
    model_used: str = ""


@dataclass
class _EntityCacheEntry:
    """Internal cache entry with metadata.

    Attributes:
        result: The cached extraction result.
        content_hash: SHA-256 hash of the original document content.
        document_id: Optional document identifier.
        created_at: Unix timestamp when entry was created.
        ttl: Time-to-live in seconds.
    """

    result: EntityExtractionResult
    content_hash: str
    document_id: Optional[str]
    created_at: float
    ttl: int

    @property
    def is_expired(self) -> bool:
        """Check if this entry has expired."""
        return time.time() - self.created_at > self.ttl


class EntityExtractionCache(BaseCache[str, EntityExtractionResult]):
    """Cache for document entity extraction results.

    Features:
        - Content-based caching via SHA-256 hash
        - Document ID tracking for targeted invalidation
        - LRU eviction with TTL expiration
        - Independent enable/disable toggle

    Usage:
        cache = EntityExtractionCache(config)
        content_hash = cache.hash_content(document_content)
        result = await cache.get(content_hash)
        if result is None:
            result = await extract_entities(document_content)
            await cache.put(content_hash, result, document_id="doc_123")
    """

    def __init__(
        self,
        config: Optional[EntityCacheConfig] = None,
    ) -> None:
        """Initialize the entity extraction cache.

        Args:
            config: Cache configuration (uses defaults if None).
        """
        self._config = config or EntityCacheConfig()
        self._cache: OrderedDict[str, _EntityCacheEntry] = OrderedDict()
        self._doc_to_hash: dict[str, str] = {}  # document_id -> content_hash mapping
        self._lock = asyncio.Lock()

        # Statistics
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    @staticmethod
    def hash_content(content: str) -> str:
        """Generate a SHA-256 hash for document content.

        Args:
            content: The document text content.

        Returns:
            Hexadecimal hash string.
        """
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    async def get(self, key: str) -> Optional[EntityExtractionResult]:
        """Retrieve a cached extraction result.

        Args:
            key: The content hash.

        Returns:
            The cached extraction result if found and valid, None otherwise.
        """
        if not self._config.enabled:
            self._misses += 1
            return None

        async with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._misses += 1
                return None

            if entry.is_expired:
                del self._cache[key]
                self._evictions += 1
                self._misses += 1
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self._hits += 1

            return entry.result

    async def put(
        self,
        key: str,
        value: EntityExtractionResult,
        ttl: Optional[int] = None,
        document_id: Optional[str] = None,
        content_hash: Optional[str] = None,
    ) -> None:
        """Store an extraction result in the cache.

        Args:
            key: The content hash (primary key).
            value: The extraction result to cache.
            ttl: Optional TTL override in seconds.
            document_id: Optional document identifier for tracking.
            content_hash: Optional explicit content hash (defaults to key).
        """
        if not self._config.enabled:
            return

        effective_ttl = ttl if ttl is not None else self._config.ttl
        actual_hash = content_hash or key

        async with self._lock:
            # Evict LRU entries if at capacity
            while len(self._cache) >= self._config.max_size:
                oldest_key, oldest_entry = self._cache.popitem(last=False)
                self._evictions += 1

                # Clean up document mapping
                if oldest_entry.document_id and oldest_key in self._doc_to_hash:
                    if self._doc_to_hash.get(oldest_entry.document_id) == oldest_key:
                        del self._doc_to_hash[oldest_entry.document_id]

                logger.debug("Evicted LRU entity entry: %s", oldest_key[:16])

            # Add or update entry
            self._cache[key] = _EntityCacheEntry(
                result=value,
                content_hash=actual_hash,
                document_id=document_id,
                created_at=time.time(),
                ttl=effective_ttl,
            )
            self._cache.move_to_end(key)

            # Track document_id -> content_hash mapping
            if document_id:
                self._doc_to_hash[document_id] = key

    async def delete(self, key: str) -> bool:
        """Remove a cached extraction result.

        Args:
            key: The content hash to remove.

        Returns:
            True if the key was found and removed.
        """
        async with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                if entry.document_id and self._doc_to_hash.get(entry.document_id) == key:
                    del self._doc_to_hash[entry.document_id]
                del self._cache[key]
                return True
            return False

    async def delete_by_document_id(self, document_id: str) -> bool:
        """Remove cached result by document ID.

        Args:
            document_id: The document identifier.

        Returns:
            True if a cached entry was found and removed.
        """
        async with self._lock:
            content_hash = self._doc_to_hash.get(document_id)
            if content_hash and content_hash in self._cache:
                del self._cache[content_hash]
                del self._doc_to_hash[document_id]
                return True
            return False

    async def clear(self) -> int:
        """Clear all cached extraction results.

        Returns:
            Number of entries that were cleared.
        """
        async with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._doc_to_hash.clear()
            self._hits = 0
            self._misses = 0
            self._evictions = 0
            return count

    async def clear_by_document_ids(self, document_ids: list[str]) -> int:
        """Clear cached results for specific document IDs.

        Args:
            document_ids: List of document identifiers to clear.

        Returns:
            Number of entries that were cleared.
        """
        async with self._lock:
            cleared = 0
            for doc_id in document_ids:
                content_hash = self._doc_to_hash.get(doc_id)
                if content_hash and content_hash in self._cache:
                    del self._cache[content_hash]
                    del self._doc_to_hash[doc_id]
                    cleared += 1
            return cleared

    async def stats(self) -> CacheStats:
        """Retrieve cache statistics.

        Returns:
            Current cache statistics snapshot.
        """
        async with self._lock:
            # Estimate memory usage
            memory_bytes = sum(
                len(entry.result.raw_response.encode("utf-8"))
                + len(entry.result.entities) * 200
                + len(entry.result.relationships) * 200
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
            key: The content hash to check.

        Returns:
            True if the key exists and is not expired.
        """
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return False
            if entry.is_expired:
                del self._cache[key]
                return False
            return True

    async def cleanup_expired(self) -> int:
        """Remove all expired entries.

        Returns:
            Number of expired entries removed.
        """
        async with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items() if entry.is_expired
            ]
            for key in expired_keys:
                entry = self._cache[key]
                if entry.document_id and self._doc_to_hash.get(entry.document_id) == key:
                    del self._doc_to_hash[entry.document_id]
                del self._cache[key]
                self._evictions += 1

            return len(expired_keys)
