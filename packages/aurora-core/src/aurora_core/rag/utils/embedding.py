"""Embedding function wrapper with batch support and asymmetric prefixes.

Migrated from LightRAG ``utils.EmbeddingFunc``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Optional

import numpy as np

if TYPE_CHECKING:
    from aurora_core.rag.utils.embedding_cache import EmbeddingCache

logger = logging.getLogger(__name__)

NO_PREFIX = "__NO_PREFIX__"


@dataclass
class EmbeddingConfig:
    """Configuration for an embedding function.

    Attributes
    ----------
    embedding_dim:
        Dimensionality of the embedding vectors.
    max_token_size:
        Maximum number of tokens per embedding call.
    func_max_async:
        Maximum concurrent async embedding calls.
    batch_num:
        Number of texts per batch.
    timeout:
        Request timeout in seconds.
    asymmetric:
        Whether to use different prefixes for queries vs documents.
    query_prefix:
        Prefix prepended to query texts (only when ``asymmetric=True``).
    document_prefix:
        Prefix prepended to document texts (only when ``asymmetric=True``).
    """

    embedding_dim: int = 1536
    max_token_size: int = 8192
    func_max_async: int = 8
    batch_num: int = 10
    timeout: float = 30.0
    asymmetric: bool = False
    query_prefix: Optional[str] = None
    document_prefix: Optional[str] = None


class EmbeddingFunc:
    """Wraps a raw embedding callable with batching, prefixes, and limits.

    Parameters
    ----------
    embed_func:
        An async callable that takes ``list[str]`` and returns
        ``list[list[float]]``.
    config:
        Embedding configuration.
    cache:
        Optional embedding cache for avoiding redundant API calls.

    Usage::

        async def raw_embed(texts: list[str]) -> list[list[float]]:
            ...

        func = EmbeddingFunc(raw_embed, EmbeddingConfig(
            embedding_dim=1536,
            asymmetric=True,
            query_prefix="query: ",
            document_prefix="document: ",
        ))
        vectors = await func(["What is AI?"], is_query=True)
    """

    def __init__(
        self,
        embed_func: Callable[[list[str]], Awaitable[list[list[float]]]],
        config: Optional[EmbeddingConfig] = None,
        cache: Optional[EmbeddingCache] = None,
    ) -> None:
        self._embed_func = embed_func
        self._config = config or EmbeddingConfig()
        self._cache = cache

    @property
    def embedding_dim(self) -> int:
        return self._config.embedding_dim

    @property
    def max_token_size(self) -> int:
        return self._config.max_token_size

    @property
    def cache(self) -> Optional[EmbeddingCache]:
        """Return the cache instance, if configured."""
        return self._cache

    def _apply_prefix(self, texts: list[str], is_query: bool) -> list[str]:
        """Prepend query or document prefix if asymmetric mode is enabled."""
        if not self._config.asymmetric:
            return texts

        prefix = (
            self._config.query_prefix if is_query else self._config.document_prefix
        )
        if prefix is None or prefix == NO_PREFIX:
            return texts

        return [prefix + t for t in texts]

    async def __call__(
        self,
        texts: list[str],
        is_query: bool = False,
    ) -> np.ndarray:
        """Embed *texts* with batching, optional prefix, and caching.

        Parameters
        ----------
        texts:
            Input texts to embed.
        is_query:
            If ``True`` and asymmetric mode is enabled, the query prefix
            is prepended.

        Returns
        -------
        np.ndarray
            Shape ``(len(texts), embedding_dim)``.
        """
        prefixed = self._apply_prefix(texts, is_query)

        if self._cache is not None and self._cache.enabled:
            all_embeddings = await self._embed_with_cache(prefixed)
        else:
            all_embeddings = await self._embed_batched(prefixed)

        return np.array(all_embeddings, dtype=np.float32)

    async def _embed_with_cache(
        self, texts: list[str]
    ) -> list[list[float]]:
        """Embed texts with cache lookup and population."""
        assert self._cache is not None

        results: list[Optional[list[float]]] = [None] * len(texts)
        uncached_indices: list[int] = []
        uncached_texts: list[str] = []

        for i, text in enumerate(texts):
            cached = await self._cache.get(text)
            if cached is not None:
                results[i] = cached
            else:
                uncached_indices.append(i)
                uncached_texts.append(text)

        if uncached_texts:
            computed = await self._embed_batched(uncached_texts)
            for idx, embedding in zip(uncached_indices, computed):
                results[idx] = embedding
                await self._cache.put(texts[idx], embedding)

        return [r for r in results if r is not None]

    async def _embed_batched(self, texts: list[str]) -> list[list[float]]:
        """Embed texts in batches without caching."""
        batch_size = max(1, self._config.batch_num)
        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            result = await self._embed_func(batch)
            all_embeddings.extend(result)

        return all_embeddings

    async def embed_query(self, text: str) -> np.ndarray:
        """Embed a single query string."""
        result = await self([text], is_query=True)
        return result[0]

    async def embed_documents(self, texts: list[str]) -> np.ndarray:
        """Embed a batch of document strings."""
        return await self(texts, is_query=False)
