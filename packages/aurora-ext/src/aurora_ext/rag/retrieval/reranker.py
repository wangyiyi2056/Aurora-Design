"""Reranker integration — Cohere, Jina, Aliyun.

Migrated from LightRAG ``rerank.py``.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class RerankResult:
    """A single reranking result."""

    index: int
    score: float
    text: str


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
