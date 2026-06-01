"""Abstract base classes for the cache system.

Defines the interface that all cache implementations must follow,
along with common data structures for cache statistics.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Generic, Optional, TypeVar

K = TypeVar("K")
V = TypeVar("V")


@dataclass(frozen=True)
class CacheStats:
    """Immutable snapshot of cache statistics.

    Attributes:
        hits: Number of cache hits.
        misses: Number of cache misses.
        evictions: Number of entries evicted due to size or TTL.
        size: Current number of entries in the cache.
        memory_bytes: Estimated memory usage in bytes.
    """

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    size: int = 0
    memory_bytes: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate the cache hit rate as a percentage.

        Returns:
            Hit rate between 0.0 and 1.0, or 0.0 if no requests.
        """
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert statistics to a dictionary for API responses.

        Returns:
            Dictionary representation of cache statistics.
        """
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "size": self.size,
            "memory_bytes": self.memory_bytes,
            "hit_rate": round(self.hit_rate, 4),
        }


class BaseCache(ABC, Generic[K, V]):
    """Abstract base class for all cache implementations.

    Provides a consistent interface for cache operations including
    get, put, delete, clear, and statistics retrieval.

    Type Parameters:
        K: Type of cache keys.
        V: Type of cache values.
    """

    @abstractmethod
    async def get(self, key: K) -> Optional[V]:
        """Retrieve a value from the cache.

        Args:
            key: The cache key to look up.

        Returns:
            The cached value if found and not expired, otherwise None.
        """

    @abstractmethod
    async def put(self, key: K, value: V, ttl: Optional[int] = None) -> None:
        """Store a value in the cache.

        Args:
            key: The cache key.
            value: The value to cache.
            ttl: Optional TTL override in seconds.
        """

    @abstractmethod
    async def delete(self, key: K) -> bool:
        """Remove a value from the cache.

        Args:
            key: The cache key to remove.

        Returns:
            True if the key was found and removed, False otherwise.
        """

    @abstractmethod
    async def clear(self) -> int:
        """Clear all entries from the cache.

        Returns:
            Number of entries that were cleared.
        """

    @abstractmethod
    async def stats(self) -> CacheStats:
        """Retrieve current cache statistics.

        Returns:
            Immutable snapshot of cache statistics.
        """

    @abstractmethod
    async def contains(self, key: K) -> bool:
        """Check if a key exists in the cache (without updating stats).

        Args:
            key: The cache key to check.

        Returns:
            True if the key exists and is not expired.
        """

    async def get_or_set(self, key: K, default_factory: Any, ttl: Optional[int] = None) -> V:
        """Get a value or compute and cache it if missing.

        Args:
            key: The cache key.
            default_factory: Callable that produces the value if missing.
            ttl: Optional TTL for the new value.

        Returns:
            The cached or newly computed value.
        """
        value = await self.get(key)
        if value is not None:
            return value

        # Call the factory (may be sync or async)
        import asyncio

        if asyncio.iscoroutinefunction(default_factory):
            new_value = await default_factory()
        else:
            new_value = default_factory()

        await self.put(key, new_value, ttl)
        return new_value
