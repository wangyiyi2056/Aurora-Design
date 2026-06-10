"""Ollama local model adapter using HTTP API.

Uses the raw Ollama HTTP API without any SDK dependency. Supports both
streaming and non-streaming chat completions.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, AsyncIterator, Dict, List

import httpx

from aurora_core.model.base import BaseLLM
from aurora_core.schema.message import Message, ModelOutput
from aurora_core.schema.model import LLMConfig

logger = logging.getLogger(__name__)

DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"


class OllamaLLM(BaseLLM):
    """Ollama local model adapter using HTTP API.

    Configuration:

    - ``api_base`` or ``OLLAMA_BASE_URL`` env var: Ollama server URL
      (default: ``http://localhost:11434``)
    - ``model_name``: Ollama model identifier (e.g. ``llama3.2``, ``mistral``)
    - ``temperature``: Sampling temperature
    - ``max_tokens``: Maximum tokens to generate (mapped to ``num_predict``)
    - ``timeout``: Request timeout in seconds (via ``extra["timeout"]``, default 120)

    Parameters
    ----------
    config:
        LLM configuration.
    """

    def __init__(self, config: LLMConfig) -> None:
        super().__init__(config)
        raw_url = (
            config.api_base
            or os.getenv("OLLAMA_BASE_URL")
            or DEFAULT_OLLAMA_BASE_URL
        ).rstrip("/")
        # Strip /v1 suffix — Ollama's native API endpoints (/api/chat)
        # live at the root, not under /v1.
        if raw_url.endswith("/v1"):
            raw_url = raw_url[:-3]
        self.base_url = raw_url
        self._timeout = float(config.extra.get("timeout", 120))

    def _build_ollama_messages(
        self, messages: List[Message]
    ) -> List[Dict[str, str]]:
        """Convert Aurora messages to Ollama format."""
        result: List[Dict[str, str]] = []
        for m in messages:
            content = (
                m.content
                if isinstance(m.content, str)
                else json.dumps(m.content, ensure_ascii=False)
            )
            result.append({"role": m.role, "content": content})
        return result

    def _build_payload(
        self, messages: List[Message], stream: bool
    ) -> Dict[str, Any]:
        """Build the Ollama API request payload."""
        payload: Dict[str, Any] = {
            "model": self.config.model_name,
            "messages": self._build_ollama_messages(messages),
            "stream": stream,
        }

        options: Dict[str, Any] = {}
        if self.config.temperature is not None:
            options["temperature"] = self.config.temperature
        if self.config.max_tokens is not None:
            options["num_predict"] = self.config.max_tokens

        if options:
            payload["options"] = options

        return payload

    async def achat(self, messages: List[Message], **kwargs) -> ModelOutput:
        """Non-streaming chat completion via Ollama."""
        payload = self._build_payload(messages, stream=False)
        url = f"{self.base_url}/api/chat"

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
            logger.error("Ollama API error: %s %s",
                         e.response.status_code, e.response.text)
            raise

        message_data = data.get("message", {})
        content = message_data.get("content", "")

        return ModelOutput(
            text=content,
            usage=data.get("eval_count") and {
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
                "total_tokens": (
                    data.get("prompt_eval_count", 0) +
                    data.get("eval_count", 0)
                ),
            },
            finish_reason="stop" if data.get("done") else None,
        )

    async def achat_stream(
        self, messages: List[Message], **kwargs
    ) -> AsyncIterator[ModelOutput]:
        """Streaming chat completion via Ollama."""
        payload = self._build_payload(messages, stream=True)
        url = f"{self.base_url}/api/chat"

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                async with client.stream("POST", url, json=payload) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        line = line.strip()
                        if not line:
                            continue

                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        message_data = data.get("message", {})
                        content = message_data.get("content", "")
                        done = data.get("done", False)

                        if content:
                            yield ModelOutput(text=content)

                        if done:
                            yield ModelOutput(
                                text="",
                                usage=data.get("eval_count") and {
                                    "prompt_tokens": data.get("prompt_eval_count", 0),
                                    "completion_tokens": data.get("eval_count", 0),
                                    "total_tokens": (
                                        data.get("prompt_eval_count", 0)
                                        + data.get("eval_count", 0)
                                    ),
                                },
                                finish_reason="stop",
                            )
                            return
        except httpx.ConnectError as e:
            logger.error(
                "Ollama connection failed at %s. Is Ollama running?",
                self.base_url,
            )
            raise ConnectionError(
                f"Cannot connect to Ollama at {self.base_url}. "
                "Ensure Ollama is running: `ollama serve`"
            ) from e
