"""Reranker integration — Cohere, Jina, Aliyun.

Migrated from LightRAG ``rerank.py``.
"""

from __future__ import annotations

import asyncio
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class RerankResult:
    """A single reranking result."""

    index: int
    score: float
    text: str


@dataclass(frozen=True)
class RerankOptions:
    """Configuration options shared by all reranker implementations.

    Attributes
    ----------
    enable_chunking:
        When ``True``, documents exceeding *max_tokens_per_doc* are split
        into sub-chunks before reranking.  Per-document scores are then
        aggregated back using *score_aggregation*.
    max_tokens_per_doc:
        Approximate token threshold above which a document is split into
        sub-chunks (only effective when *enable_chunking* is ``True``).
    score_aggregation:
        Strategy for combining sub-chunk scores into a single document
        score: ``"max"`` (highest), ``"mean"`` (average), or ``"first"``
        (first chunk's score).
    min_score:
        Minimum relevance score for a result to be included.
    timeout:
        HTTP request timeout in seconds.
    max_retries:
        Maximum number of retry attempts with exponential backoff.
    """

    enable_chunking: bool = False
    max_tokens_per_doc: int = 4096
    score_aggregation: str = "max"
    min_score: float = 0.0
    timeout: int = 30
    max_retries: int = 3


class RerankerBase(ABC):
    """Abstract reranker interface."""

    @abstractmethod
    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_n: int,
        min_score: float = 0.0,
    ) -> list[RerankResult]:
        """Rerank *documents* by relevance to *query*.

        Returns at most *top_n* results with ``score >= min_score``.
        """


class CohereReranker(RerankerBase):
    """Cohere rerank-v3.5 integration.

    Migrated from LightRAG ``rerank.cohere_rerank()``.
    """

    DEFAULT_MODEL = "rerank-v3.5"
    DEFAULT_ENDPOINT = "https://api.cohere.com/v2/rerank"

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        endpoint: str = DEFAULT_ENDPOINT,
        max_tokens_per_doc: int = 4096,
        timeout: float = 30.0,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._endpoint = endpoint
        self._max_tokens = max_tokens_per_doc
        self._timeout = timeout

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_n: int,
        min_score: float = 0.0,
    ) -> list[RerankResult]:
        import aiohttp

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "query": query,
            "documents": [
                {"text": doc[: self._max_tokens * 4]} for doc in documents
            ],
            "top_n": top_n,
            "max_tokens_per_doc": self._max_tokens,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self._endpoint,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self._timeout),
                ) as resp:
                    if resp.status != 200:
                        logger.error("Cohere rerank failed: %s", resp.status)
                        return []
                    data = await resp.json()

            results: list[RerankResult] = []
            for item in data.get("results", []):
                score = item.get("relevance_score", 0.0)
                if score >= min_score:
                    results.append(RerankResult(
                        index=item["index"],
                        score=score,
                        text=documents[item["index"]],
                    ))
            return results

        except Exception as exc:
            logger.error("Cohere rerank error: %s", exc)
            return []


class JinaReranker(RerankerBase):
    """Jina AI reranker integration.

    Migrated from LightRAG ``rerank.jina_rerank()``.
    """

    DEFAULT_MODEL = "jina-reranker-v2-base-multilingual"
    DEFAULT_ENDPOINT = "https://api.jina.ai/v1/rerank"

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        endpoint: str = DEFAULT_ENDPOINT,
        timeout: float = 30.0,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._endpoint = endpoint
        self._timeout = timeout

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_n: int,
        min_score: float = 0.0,
    ) -> list[RerankResult]:
        import aiohttp

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "query": query,
            "documents": documents,
            "top_n": top_n,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self._endpoint,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self._timeout),
                ) as resp:
                    if resp.status != 200:
                        logger.error("Jina rerank failed: %s", resp.status)
                        return []
                    data = await resp.json()

            results: list[RerankResult] = []
            for item in data.get("results", []):
                score = item.get("relevance_score", 0.0)
                if score >= min_score:
                    results.append(RerankResult(
                        index=item["index"],
                        score=score,
                        text=documents[item["index"]],
                    ))
            return results

        except Exception as exc:
            logger.error("Jina rerank error: %s", exc)
            return []


# ── Score aggregation helpers ────────────────────────────────────


def _aggregate_scores(scores: list[float], method: str) -> float:
    """Combine multiple sub-chunk scores into a single document score.

    Parameters
    ----------
    scores:
        Relevance scores from individual sub-chunks.
    method:
        Aggregation strategy: ``"max"``, ``"mean"``, or ``"first"``.

    Returns
    -------
    float
        The aggregated score.  Returns ``0.0`` when *scores* is empty.
    """
    if not scores:
        return 0.0

    if method == "mean":
        return sum(scores) / len(scores)

    if method == "first":
        return scores[0]

    # Default: max
    return max(scores)


def _split_into_chunks(text: str, max_chars: int) -> list[str]:
    """Split *text* into chunks of approximately *max_chars* characters.

    Splits on whitespace boundaries to avoid cutting words mid-token.

    Parameters
    ----------
    text:
        The input text to split.
    max_chars:
        Approximate character limit per chunk.

    Returns
    -------
    list[str]
        A list of text chunks.  Always returns at least one chunk.
    """
    if len(text) <= max_chars:
        return [text]

    words = text.split()
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for word in words:
        word_len = len(word) + 1  # +1 for space
        if current_len + word_len > max_chars and current:
            chunks.append(" ".join(current))
            current = [word]
            current_len = word_len
        else:
            current.append(word)
            current_len += word_len

    if current:
        chunks.append(" ".join(current))

    return chunks if chunks else [text]


# ── Retry helper ─────────────────────────────────────────────────


async def _retry_with_backoff(
    coro_factory,
    *,
    max_retries: int = 3,
    min_delay: float = 4.0,
    max_delay: float = 60.0,
    label: str = "rerank",
):
    """Execute *coro_factory* with exponential backoff on failure.

    Parameters
    ----------
    coro_factory:
        A zero-argument callable that returns an awaitable.
    max_retries:
        Maximum number of attempts (including the first).
    min_delay:
        Initial delay in seconds before the first retry.
    max_delay:
        Maximum delay cap in seconds.
    label:
        Human-readable label for log messages.

    Returns
    -------
    The result of the last successful call.

    Raises
    ------
    Exception
        Re-raises the last exception if all retries are exhausted.
    """
    last_exc: Exception | None = None

    for attempt in range(max_retries):
        try:
            return await coro_factory()
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                delay = min(min_delay * (2 ** attempt), max_delay)
                logger.warning(
                    "%s attempt %d/%d failed (%s); retrying in %.1fs",
                    label,
                    attempt + 1,
                    max_retries,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)

    raise last_exc  # type: ignore[misc]


# ── Aliyun DashScope reranker ────────────────────────────────────


class AliyunReranker(RerankerBase):
    """Aliyun DashScope reranker using the ``gte-rerank-v2`` model.

    Authenticates via the ``DASHSCOPE_API_KEY`` environment variable
    (or an explicitly provided *api_key*).

    Parameters
    ----------
    api_key:
        DashScope API key.  Falls back to ``$DASHSCOPE_API_KEY``.
    model:
        Model identifier.  Default ``"gte-rerank-v2"``.
    endpoint:
        DashScope rerank endpoint URL.
    options:
        Optional :class:`RerankOptions` for chunking, aggregation,
        retry, and timeout configuration.
    """

    DEFAULT_MODEL = "gte-rerank-v2"
    DEFAULT_ENDPOINT = "https://dashscope.aliyuncs.com/api/v1/services/rerank"

    def __init__(
        self,
        api_key: str = "",
        model: str = DEFAULT_MODEL,
        endpoint: str = DEFAULT_ENDPOINT,
        options: RerankOptions | None = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("DASHSCOPE_API_KEY", "")
        self._model = model
        self._endpoint = endpoint
        self._options = options or RerankOptions()

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_n: int,
        min_score: float = 0.0,
    ) -> list[RerankResult]:
        """Rerank documents via the Aliyun DashScope rerank API.

        When :attr:`RerankOptions.enable_chunking` is ``True``, documents
        exceeding *max_tokens_per_doc* are split into sub-chunks.  Each
        sub-chunk is reranked independently and the per-document score is
        aggregated using :attr:`RerankOptions.score_aggregation`.
        """
        effective_min_score = max(min_score, self._options.min_score)

        if self._options.enable_chunking:
            return await self._rerank_with_chunking(
                query, documents, top_n, effective_min_score
            )

        return await self._rerank_direct(
            query, documents, top_n, effective_min_score
        )

    async def _rerank_direct(
        self,
        query: str,
        documents: list[str],
        top_n: int,
        min_score: float,
    ) -> list[RerankResult]:
        """Single-shot reranking without document chunking."""
        import aiohttp

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "input": {
                "query": query,
                "documents": documents,
            },
            "parameters": {
                "top_n": top_n,
                "return_documents": False,
            },
        }

        async def _call():
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self._endpoint,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self._options.timeout),
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        raise RuntimeError(
                            f"Aliyun rerank HTTP {resp.status}: {body[:200]}"
                        )
                    return await resp.json()

        try:
            data = await _retry_with_backoff(
                _call,
                max_retries=self._options.max_retries,
                label="AliyunReranker",
            )
        except Exception as exc:
            logger.error("Aliyun rerank failed after retries: %s", exc)
            return []

        return self._parse_response(data, documents, min_score)

    async def _rerank_with_chunking(
        self,
        query: str,
        documents: list[str],
        top_n: int,
        min_score: float,
    ) -> list[RerankResult]:
        """Rerank with long-document chunking and score aggregation."""
        import aiohttp

        # Build chunk list, tracking which document each chunk belongs to.
        all_chunks: list[str] = []
        chunk_to_doc: list[int] = []  # maps chunk index -> original doc index
        max_chars = self._options.max_tokens_per_doc * 4  # rough char estimate

        for doc_idx, doc in enumerate(documents):
            sub_chunks = _split_into_chunks(doc, max_chars)
            for sc in sub_chunks:
                all_chunks.append(sc)
                chunk_to_doc.append(doc_idx)

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "input": {
                "query": query,
                "documents": all_chunks,
            },
            "parameters": {
                "top_n": len(all_chunks),
                "return_documents": False,
            },
        }

        async def _call():
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self._endpoint,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self._options.timeout),
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        raise RuntimeError(
                            f"Aliyun rerank HTTP {resp.status}: {body[:200]}"
                        )
                    return await resp.json()

        try:
            data = await _retry_with_backoff(
                _call,
                max_retries=self._options.max_retries,
                label="AliyunReranker(chunked)",
            )
        except Exception as exc:
            logger.error("Aliyun chunked rerank failed: %s", exc)
            return []

        # Collect per-chunk scores grouped by original document.
        doc_scores: dict[int, list[float]] = {}
        for item in data.get("output", {}).get("results", []):
            chunk_idx = item.get("index", 0)
            score = float(item.get("relevance_score", 0.0))
            if 0 <= chunk_idx < len(chunk_to_doc):
                orig_idx = chunk_to_doc[chunk_idx]
                doc_scores.setdefault(orig_idx, []).append(score)

        # Aggregate and build final results.
        aggregated: list[RerankResult] = []
        for doc_idx, scores in doc_scores.items():
            agg_score = _aggregate_scores(scores, self._options.score_aggregation)
            if agg_score >= min_score:
                aggregated.append(RerankResult(
                    index=doc_idx,
                    score=agg_score,
                    text=documents[doc_idx],
                ))

        aggregated.sort(key=lambda r: r.score, reverse=True)
        return aggregated[:top_n]

    @staticmethod
    def _parse_response(
        data: dict[str, Any],
        documents: list[str],
        min_score: float,
    ) -> list[RerankResult]:
        """Parse the DashScope rerank API response into RerankResult objects."""
        results: list[RerankResult] = []
        output = data.get("output", {})
        for item in output.get("results", []):
            score = float(item.get("relevance_score", 0.0))
            idx = int(item.get("index", 0))
            if score >= min_score and 0 <= idx < len(documents):
                results.append(RerankResult(
                    index=idx,
                    score=score,
                    text=documents[idx],
                ))
        return results
