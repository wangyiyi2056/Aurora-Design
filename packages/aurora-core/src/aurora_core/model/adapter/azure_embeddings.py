"""Azure OpenAI embedding adapter.

Provides embedding capabilities using Azure OpenAI's embedding models.
"""

from __future__ import annotations

import logging
import os
from typing import List

import openai

from aurora_core.model.base import BaseEmbeddings
from aurora_core.schema.model import LLMConfig

logger = logging.getLogger(__name__)


class AzureOpenAIEmbeddings(BaseEmbeddings):
    """Azure OpenAI embedding adapter.

    Configuration is read from ``LLMConfig.extra``:

    - ``api_version``: Azure API version (default: ``2024-10-21``)

    Environment variables:

    - ``AZURE_OPENAI_API_KEY``: API key
    - ``AZURE_OPENAI_ENDPOINT``: Azure endpoint URL

    Parameters
    ----------
    config:
        LLM configuration. ``api_base`` or ``AZURE_OPENAI_ENDPOINT`` env var
        provides the Azure endpoint.
    """

    def __init__(self, config: LLMConfig) -> None:
        self.config = config

        api_key = (
            config.api_key
            or os.getenv("AZURE_OPENAI_API_KEY")
            or ""
        )
        azure_endpoint = (
            config.api_base
            or os.getenv("AZURE_OPENAI_ENDPOINT")
            or ""
        ).rstrip("/")

        api_version = str(config.extra.get("api_version") or "2024-10-21")

        if not api_key:
            logger.warning(
                "AzureOpenAIEmbeddings: no API key provided. "
                "Set AZURE_OPENAI_API_KEY or pass api_key in config."
            )
        if not azure_endpoint:
            logger.warning(
                "AzureOpenAIEmbeddings: no endpoint provided. "
                "Set AZURE_OPENAI_ENDPOINT or pass api_base in config."
            )

        self.client = openai.AsyncAzureOpenAI(
            api_key=api_key or "EMPTY",
            azure_endpoint=azure_endpoint,
            api_version=api_version,
        )

    async def aembed(self, texts: List[str]) -> List[List[float]]:
        """Embed texts using Azure OpenAI.

        Parameters
        ----------
        texts:
            Input texts to embed.

        Returns
        -------
        list[list[float]]
            Embedding vectors, one per input text.
        """
        response = await self.client.embeddings.create(
            model=self.config.model_name,
            input=texts,
        )
        return [item.embedding for item in response.data]
