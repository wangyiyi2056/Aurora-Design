"""LLM response cache implementation.

Caches responses from LLM calls to avoid redundant API calls for
identical prompts. Supports LRU eviction and TTL expiration.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Optional

from aurora_ext.rag.cache.base import BaseCache, CacheStats
from aurora_ext.rag.cache.config import LLMCacheConfig

logger = logging.getLogger(__name__)


@dataclass
class _CacheEntry:
    """Internal cache entry with metadata.

    Attributes:
        value: The cached LLM response.
        created_at: Unix timestamp when entry was created.
        ttl: Time-to-live in seconds.
        access_count: Number of times this entry has been accessed.
    """

    value: str
    created_at: float
    ttl: int
    access_count: int = 0

    @property
    def is_expired(self) -> bool:
        """Check if this entry has expired."""
        return time.time() - self.created_at > self.ttl


class LLMResponseCache(BaseCache[str, str]):
    """Cache for LLM API responses.

    Features:
        - LRU (Least Recently Used) eviction policy
        - TTL-based expiration
        - Optional disk persistence
        - Thread-safe operations via asyncio.Lock

    Usage:
        cache = LLMResponseCache(config)
        response = await cache.get(prompt_hash)
        if response is None:
            response = await llm.generate(prompt)
            await cache.put(prompt_hash, response)
    """

    def __init__(
        self,
        config: Optional[LLMCacheConfig] = None,
        working_dir: str = "./rag_storage",
    ) -> None:
        """Initialize the LLM response cache.

        Args:
            config: Cache configuration (uses defaults if None).
            working_dir: Base directory for disk persistence.
        """
        self._config = config or LLMCacheConfig()
        self._working_dir = working_dir
        self._cache: OrderedDict[str, _CacheEntry] = OrderedDict()
        self._lock = asyncio.Lock()

        # Statistics
        self._hits = 0
        self._misses = 0
        self._evictions = 0

        # Disk persistence path
        if self._config.persist_to_disk:
            self._disk_path = os.path.join(working_dir, self._config.disk_path)
            os.makedirs(self._disk_path, exist_ok=True)
            self._disk_file = os.path.join(self._disk_path, "llm_cache.json")
        else:
            self._disk_file = None

    @staticmethod
    def hash_prompt(prompt: str) -> str:
        """Generate a SHA-256 hash for a prompt.

        Args:
            prompt: The LLM prompt text.

        Returns:
            Hexadecimal hash string.
        """
        return hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    async def get(self, key: str) -> Optional[str]:
        """Retrieve a cached LLM response.

        Args:
            key: The prompt hash.

        Returns:
            The cached response if found and valid, None otherwise.
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
                # Remove expired entry
                del self._cache[key]
                self._evictions += 1
                self._misses += 1
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            entry.access_count += 1
            self._hits += 1

            return entry.value

    async def put(self, key: str, value: str, ttl: Optional[int] = None) -> None:
        """Store an LLM response in the cache.

        Args:
            key: The prompt hash.
            value: The LLM response text.
            ttl: Optional TTL override in seconds.
        """
        if not self._config.enabled:
            return

        effective_ttl = ttl if ttl is not None else self._config.ttl

        async with self._lock:
            # Evict LRU entries if at capacity
            while len(self._cache) >= self._config.max_size:
                oldest_key, _ = self._cache.popitem(last=False)
                self._evictions += 1
                logger.debug("Evicted LRU entry: %s", oldest_key[:16])

            # Add or update entry
            self._cache[key] = _CacheEntry(
                value=value,
                created_at=time.time(),
                ttl=effective_ttl,
            )
            self._cache.move_to_end(key)

            # Persist to disk if enabled
            await self._persist_to_disk()

    async def delete(self, key: str) -> bool:
        """Remove a cached response.

        Args:
            key: The prompt hash to remove.

        Returns:
            True if the key was found and removed.
        """
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                await self._persist_to_disk()
                return True
            return False

    async def clear(self) -> int:
        """Clear all cached responses.

        Returns:
            Number of entries that were cleared.
        """
        async with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._hits = 0
            self._misses = 0
            self._evictions = 0

            if self._disk_file and os.path.exists(self._disk_file):
                os.remove(self._disk_file)

            return count

    async def stats(self) -> CacheStats:
        """Retrieve cache statistics.

        Returns:
            Current cache statistics snapshot.
        """
        async with self._lock:
            # Estimate memory usage (rough approximation)
            memory_bytes = sum(
                len(entry.value.encode("utf-8")) + 100  # entry overhead
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
            key: The prompt hash to check.

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
                del self._cache[key]
                self._evictions += 1

            if expired_keys:
                await self._persist_to_disk()

            return len(expired_keys)

    async def _persist_to_disk(self) -> None:
        """Persist cache to disk (called while holding lock)."""
        if not self._disk_file:
            return

        try:
            data = {
                key: {
                    "value": entry.value,
                    "created_at": entry.created_at,
                    "ttl": entry.ttl,
                    "access_count": entry.access_count,
                }
                for key, entry in self._cache.items()
            }
            with open(self._disk_file, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except OSError as e:
            logger.warning("Failed to persist LLM cache to disk: %s", e)

    async def load_from_disk(self) -> int:
        """Load cache from disk.

        Returns:
            Number of entries loaded.
        """
        if not self._disk_file or not os.path.exists(self._disk_file):
            return 0

        try:
            with open(self._disk_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            async with self._lock:
                count = 0
                for key, entry_data in data.items():
                    entry = _CacheEntry(
                        value=entry_data["value"],
                        created_at=entry_data["created_at"],
                        ttl=entry_data["ttl"],
                        access_count=entry_data.get("access_count", 0),
                    )
                    # Skip expired entries
                    if not entry.is_expired:
                        self._cache[key] = entry
                        count += 1

                return count
        except (OSError, json.JSONDecodeError, KeyError) as e:
            logger.warning("Failed to load LLM cache from disk: %s", e)
            return 0
