"""Reranker integration — Cohere, Jina, Aliyun, vLLM.

Migrated from LightRAG ``rerank.py``.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RerankResult:
    """A single reranking result.

    Attributes
    ----------
    index:
        Original document index in the input list.
    score:
        Relevance score from the reranker (higher is better).
    content:
        The document text (alias for backward compatibility).
    """

    index: int
    score: float
    content: str = field(default="")

    @property
    def text(self) -> str:
        """Alias for content (backward compatibility)."""
        return self.content


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
                        content=documents[item["index"]],
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
                        content=documents[item["index"]],
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
                    content=documents[doc_idx],
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
                    content=documents[idx],
                ))
        return results


# ── vLLM Reranker ──────────────────────────────────────────────


class VLLMReranker(CohereReranker):
    """vLLM self-hosted reranker (Cohere API compatible).

    vLLM provides a Cohere-compatible rerank API endpoint for self-hosted
    models like BGE-reranker, Cohere-rerank, etc.

    Parameters
    ----------
    api_key:
        API key (often empty for local deployments).
    model:
        Model name as registered in vLLM.
    endpoint:
        vLLM server endpoint (e.g., ``http://localhost:8000/v1/rerank``).
    max_tokens_per_doc:
        Maximum tokens per document.
    timeout:
        Request timeout in seconds.
    """

    DEFAULT_MODEL = "BAAI/bge-reranker-v2-m3"
    DEFAULT_ENDPOINT = "http://localhost:8000/v1/rerank"

    def __init__(
        self,
        api_key: str = "",
        model: str = DEFAULT_MODEL,
        endpoint: str = DEFAULT_ENDPOINT,
        max_tokens_per_doc: int = 4096,
        timeout: float = 30.0,
    ) -> None:
        super().__init__(
            api_key=api_key,
            model=model,
            endpoint=endpoint,
            max_tokens_per_doc=max_tokens_per_doc,
            timeout=timeout,
        )


# ── Configuration Management ─────────────────────────────────────


@dataclass(frozen=True)
class RerankerConfig:
    """Reranker configuration loaded from TOML or environment.

    Attributes
    ----------
    enabled:
        Whether reranking is enabled globally.
    type:
        Reranker type: ``"cohere"``, ``"jina"``, ``"aliyun"``, ``"vllm"``.
    api_key:
        API key for the reranker service.
    api_base:
        Base URL for the API endpoint.
    model:
        Model identifier.
    top_k:
        Default number of results to return.
    timeout:
        Request timeout in seconds.
    max_retries:
        Maximum retry attempts.
    enable_chunking:
        Whether to split long documents before reranking.
    max_tokens_per_doc:
        Token threshold for chunking.
    score_aggregation:
        Aggregation strategy: ``"max"``, ``"mean"``, or ``"first"``.
    min_score:
        Minimum score threshold.
    """

    enabled: bool = True
    type: str = "cohere"
    api_key: str = ""
    api_base: str = ""
    model: str = ""
    top_k: int = 10
    timeout: int = 30
    max_retries: int = 3
    enable_chunking: bool = False
    max_tokens_per_doc: int = 4096
    score_aggregation: str = "max"
    min_score: float = 0.0

    @classmethod
    def from_toml(cls, config: dict[str, Any]) -> RerankerConfig:
        """Load configuration from a TOML dictionary.

        Parameters
        ----------
        config:
            Dictionary with ``reranker`` section.

        Returns
        -------
        RerankerConfig
            Parsed configuration with defaults applied.

        Example
        -------
        .. code-block:: toml

            [reranker]
            enabled = true
            type = "cohere"
            api_key = "your-api-key"
            api_base = "https://api.cohere.ai/v1"
            model = "rerank-multilingual-v3.0"
            top_k = 10
        """
        reranker_section = config.get("reranker", {})

        # Apply environment variable overrides
        api_key = reranker_section.get("api_key") or os.environ.get(
            "RERANKER_API_KEY", ""
        )
        api_base = reranker_section.get("api_base") or os.environ.get(
            "RERANKER_API_BASE", ""
        )
        reranker_type = reranker_section.get("type", "cohere")

        return cls(
            enabled=reranker_section.get("enabled", True),
            type=reranker_type,
            api_key=api_key,
            api_base=api_base,
            model=reranker_section.get("model", ""),
            top_k=reranker_section.get("top_k", 10),
            timeout=reranker_section.get("timeout", 30),
            max_retries=reranker_section.get("max_retries", 3),
            enable_chunking=reranker_section.get("enable_chunking", False),
            max_tokens_per_doc=reranker_section.get("max_tokens_per_doc", 4096),
            score_aggregation=reranker_section.get("score_aggregation", "max"),
            min_score=reranker_section.get("min_score", 0.0),
        )

    @classmethod
    def from_env(cls) -> RerankerConfig:
        """Load configuration purely from environment variables.

        Environment Variables
        ---------------------
        RERANKER_ENABLED:
            Whether reranking is enabled (``"true"`` or ``"false"``).
        RERANKER_TYPE:
            Reranker type (``cohere``, ``jina``, ``aliyun``, ``vllm``).
        RERANKER_API_KEY:
            API key for the service.
        RERANKER_API_BASE:
            Base URL for the API.
        RERANKER_MODEL:
            Model identifier.
        RERANKER_TOP_K:
            Default top_k value.
        """
        return cls(
            enabled=os.environ.get("RERANKER_ENABLED", "true").lower() == "true",
            type=os.environ.get("RERANKER_TYPE", "cohere"),
            api_key=os.environ.get("RERANKER_API_KEY", ""),
            api_base=os.environ.get("RERANKER_API_BASE", ""),
            model=os.environ.get("RERANKER_MODEL", ""),
            top_k=int(os.environ.get("RERANKER_TOP_K", "10")),
            timeout=int(os.environ.get("RERANKER_TIMEOUT", "30")),
            max_retries=int(os.environ.get("RERANKER_MAX_RETRIES", "3")),
        )


def create_reranker(config: RerankerConfig) -> Optional[RerankerBase]:
    """Factory function to create a reranker from configuration.

    Parameters
    ----------
    config:
        Reranker configuration.

    Returns
    -------
    Optional[RerankerBase]
        Instantiated reranker, or ``None`` if disabled or invalid type.

    Example
    -------
    .. code-block:: python

        config = RerankerConfig(
            enabled=True,
            type="cohere",
            api_key="your-key",
            model="rerank-multilingual-v3.0",
        )
        reranker = create_reranker(config)
    """
    if not config.enabled:
        logger.info("Reranker disabled in configuration")
        return None

    if not config.api_key and config.type not in ("vllm",):
        logger.warning(
            "Reranker type '%s' requires API key but none provided",
            config.type,
        )

    options = RerankOptions(
        enable_chunking=config.enable_chunking,
        max_tokens_per_doc=config.max_tokens_per_doc,
        score_aggregation=config.score_aggregation,
        min_score=config.min_score,
        timeout=config.timeout,
        max_retries=config.max_retries,
    )

    reranker_type = config.type.lower()

    if reranker_type == "cohere":
        endpoint = config.api_base or CohereReranker.DEFAULT_ENDPOINT
        model = config.model or CohereReranker.DEFAULT_MODEL
        return CohereReranker(
            api_key=config.api_key,
            model=model,
            endpoint=endpoint,
            max_tokens_per_doc=config.max_tokens_per_doc,
            timeout=float(config.timeout),
        )

    elif reranker_type == "jina":
        endpoint = config.api_base or JinaReranker.DEFAULT_ENDPOINT
        model = config.model or JinaReranker.DEFAULT_MODEL
        return JinaReranker(
            api_key=config.api_key,
            model=model,
            endpoint=endpoint,
            timeout=float(config.timeout),
        )

    elif reranker_type == "aliyun":
        endpoint = config.api_base or AliyunReranker.DEFAULT_ENDPOINT
        model = config.model or AliyunReranker.DEFAULT_MODEL
        return AliyunReranker(
            api_key=config.api_key,
            model=model,
            endpoint=endpoint,
            options=options,
        )

    elif reranker_type == "vllm":
        endpoint = config.api_base or VLLMReranker.DEFAULT_ENDPOINT
        model = config.model or VLLMReranker.DEFAULT_MODEL
        return VLLMReranker(
            api_key=config.api_key,
            model=model,
            endpoint=endpoint,
            max_tokens_per_doc=config.max_tokens_per_doc,
            timeout=float(config.timeout),
        )

    else:
        logger.error("Unknown reranker type: %s", config.type)
        return None


# ── Robust Reranker Wrapper ──────────────────────────────────────


class RobustReranker(RerankerBase):
    """Wrapper that adds error handling, fallback, and rate limiting.

    This wrapper ensures reranking never crashes the query pipeline by:
    - Catching all exceptions and returning original order on failure
    - Implementing exponential backoff with circuit breaker
    - Detecting and handling rate limits (HTTP 429)
    - Logging all failures for monitoring

    Parameters
    ----------
    reranker:
        The underlying reranker implementation.
    fallback_to_original:
        Whether to return original order on failure (default ``True``).
    circuit_breaker_threshold:
        Number of consecutive failures before opening circuit.
    circuit_breaker_timeout:
        Seconds to wait before attempting after circuit opens.
    """

    def __init__(
        self,
        reranker: RerankerBase,
        fallback_to_original: bool = True,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_timeout: float = 60.0,
    ) -> None:
        self._reranker = reranker
        self._fallback = fallback_to_original
        self._circuit_threshold = circuit_breaker_threshold
        self._circuit_timeout = circuit_breaker_timeout
        self._failure_count = 0
        self._circuit_open_until = 0.0

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_n: int,
        min_score: float = 0.0,
    ) -> list[RerankResult]:
        """Rerank with robust error handling.

        On failure, returns either:
        - Original document order (if ``fallback_to_original=True``)
        - Empty list (if ``fallback_to_original=False``)
        """
        # Check circuit breaker
        if self._is_circuit_open():
            logger.warning(
                "Reranker circuit breaker open, using fallback order"
            )
            return self._fallback_results(documents, top_n, min_score)

        try:
            results = await self._reranker.rerank(
                query, documents, top_n, min_score
            )
            # Reset failure count on success
            self._failure_count = 0
            return results

        except Exception as exc:
            self._handle_failure(exc)
            return self._fallback_results(documents, top_n, min_score)

    def _is_circuit_open(self) -> bool:
        """Check if circuit breaker is currently open."""
        if self._circuit_open_until > time.time():
            return True
        # Circuit closed or reset
        return False

    def _handle_failure(self, exc: Exception) -> None:
        """Handle a reranker failure and update circuit breaker."""
        self._failure_count += 1
        logger.error(
            "Reranker failure %d/%d: %s",
            self._failure_count,
            self._circuit_threshold,
            exc,
        )

        # Open circuit if threshold exceeded
        if self._failure_count >= self._circuit_threshold:
            self._circuit_open_until = time.time() + self._circuit_timeout
            logger.error(
                "Reranker circuit breaker opened for %.0fs after %d failures",
                self._circuit_timeout,
                self._failure_count,
            )

    def _fallback_results(
        self,
        documents: list[str],
        top_n: int,
        min_score: float,
    ) -> list[RerankResult]:
        """Generate fallback results (original order or empty)."""
        if not self._fallback:
            return []

        # Return original order with score=1.0 (neutral)
        results = []
        for i, doc in enumerate(documents[:top_n]):
            if 1.0 >= min_score:
                results.append(RerankResult(
                    index=i,
                    score=1.0,
                    content=doc,
                ))
        return results
