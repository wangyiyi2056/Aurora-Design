"""Dedicated Azure OpenAI adapter with Azure-specific configuration.

This adapter provides a cleaner interface for Azure OpenAI deployments,
separating Azure concerns from the generic OpenAI adapter.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, AsyncIterator, Dict, List

import openai

from aurora_core.model.base import BaseLLM
from aurora_core.schema.message import Message, ModelOutput, ToolCall
from aurora_core.schema.model import LLMConfig
from aurora_core.utils.retry import retry_on_transient

logger = logging.getLogger(__name__)


class AzureOpenAILLM(BaseLLM):
    """Dedicated Azure OpenAI adapter with Azure-specific configuration.

    Configuration is read from ``LLMConfig.extra``:

    - ``api_version``: Azure API version (default: ``2024-10-21``)
    - ``deployment_name``: Azure deployment name (defaults to ``model_name``)

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
        super().__init__(config)

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
        self._deployment_name = str(
            config.extra.get("deployment_name") or config.model_name
        )

        if not api_key:
            logger.warning(
                "AzureOpenAILLM: no API key provided. "
                "Set AZURE_OPENAI_API_KEY or pass api_key in config."
            )
        if not azure_endpoint:
            logger.warning(
                "AzureOpenAILLM: no endpoint provided. "
                "Set AZURE_OPENAI_ENDPOINT or pass api_base in config."
            )

        self.client = openai.AsyncAzureOpenAI(
            api_key=api_key or "EMPTY",
            azure_endpoint=azure_endpoint,
            api_version=api_version,
        )

    def _build_openai_messages(
        self, messages: List[Message]
    ) -> List[Dict[str, Any]]:
        """Convert Aurora messages to OpenAI-compatible format."""
        result: List[Dict[str, Any]] = []
        for m in messages:
            msg: Dict[str, Any] = {"role": m.role}
            if isinstance(m.content, list):
                msg["content"] = m.content
            else:
                msg["content"] = m.content
            if m.name:
                msg["name"] = m.name
            if m.tool_calls:
                msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": tc.function,
                    }
                    for tc in m.tool_calls
                ]
            if m.tool_call_id:
                msg["tool_call_id"] = m.tool_call_id
            result.append(msg)
        return result

    @retry_on_transient(max_retries=3, base_delay=1.0)
    async def achat(self, messages: List[Message], **kwargs) -> ModelOutput:
        """Non-streaming chat completion via Azure OpenAI."""
        response = await self.client.chat.completions.create(
            model=self._deployment_name,
            messages=self._build_openai_messages(messages),
            stream=False,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            **kwargs,
        )
        choice = response.choices[0]
        message = choice.message
        content = message.content or ""

        tool_calls: List[ToolCall] | None = None
        if message.tool_calls:
            tool_calls = [
                ToolCall(
                    id=tc.id,
                    type=tc.type,
                    function={
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                )
                for tc in message.tool_calls
            ]

        return ModelOutput(
            text=content,
            usage=response.usage.model_dump() if response.usage else None,
            finish_reason=choice.finish_reason,
            tool_calls=tool_calls,
        )

    async def achat_stream(
        self, messages: List[Message], **kwargs
    ) -> AsyncIterator[ModelOutput]:
        """Streaming chat completion via Azure OpenAI."""
        response = await self.client.chat.completions.create(
            model=self._deployment_name,
            messages=self._build_openai_messages(messages),
            stream=True,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            **kwargs,
        )

        raw_response = response.response
        tool_call_buffers: Dict[int, Dict[str, Any]] = {}

        async for line in raw_response.aiter_lines():
            line = line.strip()
            if not line:
                continue
            if line == "data: [DONE]":
                break
            if not line.startswith("data:"):
                continue

            data_str = line[5:].lstrip()
            try:
                chunk_data = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            choices = chunk_data.get("choices", [])
            if not choices:
                continue

            delta_data = choices[0].get("delta", {})
            content = delta_data.get("content", "") or ""

            for tool_delta in delta_data.get("tool_calls") or []:
                index = int(tool_delta.get("index", 0))
                buffered = tool_call_buffers.setdefault(
                    index,
                    {
                        "id": "",
                        "type": "function",
                        "name": "",
                        "arguments": "",
                    },
                )
                if tool_delta.get("id"):
                    buffered["id"] = tool_delta["id"]
                if tool_delta.get("type"):
                    buffered["type"] = tool_delta["type"]
                function_delta = tool_delta.get("function") or {}
                if function_delta.get("name"):
                    buffered["name"] += function_delta["name"]
                if function_delta.get("arguments"):
                    buffered["arguments"] += function_delta["arguments"]

            finish_reason = choices[0].get("finish_reason")

            if finish_reason == "tool_calls" and tool_call_buffers:
                tool_calls: List[ToolCall] = []
                for idx in sorted(tool_call_buffers):
                    buffered = tool_call_buffers[idx]
                    tool_calls.append(
                        ToolCall(
                            id=buffered["id"],
                            type=buffered["type"],
                            function={
                                "name": buffered["name"],
                                "arguments": buffered["arguments"],
                            },
                        )
                    )
                yield ModelOutput(
                    text=content,
                    finish_reason=finish_reason,
                    tool_calls=tool_calls,
                )
                continue

            if not content and not finish_reason:
                continue

            yield ModelOutput(
                text=content,
                finish_reason=finish_reason,
            )
