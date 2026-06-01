"""Ollama embedding adapter using HTTP API.

Uses the raw Ollama HTTP API for embedding generation without any SDK dependency.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

import httpx

from aurora_core.model.base import BaseEmbeddings
from aurora_core.schema.model import LLMConfig

logger = logging.getLogger(__name__)

DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"


class OllamaEmbeddings(BaseEmbeddings):
    """Ollama embedding adapter using the ``/api/embed`` endpoint.

    Configuration:

    - ``api_base`` or ``OLLAMA_BASE_URL`` env var: Ollama server URL
      (default: ``http://localhost:11434``)
    - ``model_name``: Ollama embedding model identifier
      (e.g. ``nomic-embed-text``, ``mxbai-embed-large``)
    - ``timeout``: Request timeout in seconds (via ``extra["timeout"]``, default 120)

    Parameters
    ----------
    config:
        LLM configuration (reused for embedding model settings).
    """

    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self.base_url = (
            config.api_base
            or os.getenv("OLLAMA_BASE_URL")
            or DEFAULT_OLLAMA_BASE_URL
        ).rstrip("/")
        self._timeout = float(config.extra.get("timeout", 120))

    async def aembed(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of texts using Ollama.

        Parameters
        ----------
        texts:
            Input texts to embed.

        Returns
        -------
        list[list[float]]
            Embedding vectors, one per input text.

        Raises
        ------
        ConnectionError
            If the Ollama server is not reachable.
        httpx.HTTPStatusError
            If the API returns an error status.
        """
        url = f"{self.base_url}/api/embed"
        payload: Dict[str, Any] = {
            "model": self.config.model_name,
            "input": texts,
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
        except httpx.ConnectError as e:
            logger.error(
                "Ollama connection failed at %s. Is Ollama running?",
                self.base_url,
            )
            raise ConnectionError(
                f"Cannot connect to Ollama at {self.base_url}. "
                "Ensure Ollama is running: `ollama serve`"
            ) from e
        except httpx.HTTPStatusError as e:
            logger.error(
                "Ollama embed API error: %s %s",
                e.response.status_code,
                e.response.text,
            )
            raise

        embeddings = data.get("embeddings", [])

        if len(embeddings) != len(texts):
            logger.warning(
                "Ollama returned %d embeddings for %d input texts",
                len(embeddings),
                len(texts),
            )

        return embeddings
