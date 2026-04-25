import asyncio
import json
import logging
import os
from typing import Any, AsyncIterator, Dict, List

import httpx

from chatbi_core.model.base import BaseLLM
from chatbi_core.schema.message import Message, ModelOutput, ToolCall
from chatbi_core.schema.model import LLMConfig
from chatbi_core.utils.retry import retry_on_transient

logger = logging.getLogger(__name__)


class AnthropicLLM(BaseLLM):
    """Anthropic-compatible LLM adapter (supports Kimi and other Anthropic-style APIs)."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.api_key = config.api_key or os.getenv("ANTHROPIC_API_KEY")
        self.base_url = config.api_base or "https://api.anthropic.com"
        self.api_version = "2023-06-01"

    def _build_anthropic_messages(
        self, messages: List[Message]
    ) -> tuple[List[Dict[str, Any]], str | None]:
        result: List[Dict[str, Any]] = []
        system_content: str | None = None

        for m in messages:
            if m.role == "system":
                if isinstance(m.content, str):
                    system_content = m.content
                continue

            msg: Dict[str, Any] = {"role": m.role}
            if isinstance(m.content, list):
                content_parts = []
                for part in m.content:
                    if isinstance(part, dict):
                        if part.get("type") == "text":
                            content_parts.append({"type": "text", "text": part.get("text", "")})
                        elif part.get("type") == "image_url":
                            content_parts.append({
                                "type": "image",
                                "source": {
                                    "type": "url",
                                    "url": part.get("image_url", {}).get("url", ""),
                                },
                            })
                    else:
                        content_parts.append({"type": "text", "text": str(part)})
                msg["content"] = content_parts
            else:
                msg["content"] = [{"type": "text", "text": m.content}]

            if m.tool_calls:
                msg["content"].extend([
                    {
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.function.get("name", ""),
                        "input": tc.function.get("arguments", {}),
                    }
                    for tc in m.tool_calls
                ])

            if m.tool_call_id:
                msg["content"] = [
                    {
                        "type": "tool_result",
                        "tool_use_id": m.tool_call_id,
                        "content": m.content if isinstance(m.content, str) else str(m.content),
                    }
                ]

            result.append(msg)

        return result, system_content

    @retry_on_transient(max_retries=3, base_delay=1.0)
    async def achat(self, messages: List[Message], **kwargs) -> ModelOutput:
        anthropic_messages, system = self._build_anthropic_messages(messages)

        payload: Dict[str, Any] = {
            "model": self.config.model_name,
            "max_tokens": self.config.max_tokens or 4096,
            "messages": anthropic_messages,
        }

        if system:
            payload["system"] = system

        if self.config.temperature is not None:
            payload["temperature"] = self.config.temperature

        tools = kwargs.get("tools")
        if tools:
            payload["tools"] = [
                {
                    "name": t.get("name"),
                    "description": t.get("description", ""),
                    "input_schema": t.get("parameters", {}),
                }
                for t in tools
            ]

        # Debug logging
        logger.info(f"[AnthropicLLM] POST {self.base_url}/v1/messages")
        logger.info(f"[AnthropicLLM] payload: {json.dumps(payload, ensure_ascii=False)}")

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.api_version,
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.base_url}/v1/messages",
                json=payload,
                headers=headers,
            )
            if resp.status_code >= 400:
                error_detail = resp.text
                raise httpx.HTTPStatusError(
                    f"{resp.status_code} error: {error_detail}",
                    request=resp.request,
                    response=resp,
                )
            data = resp.json()

        text_content = ""
        tool_calls: List[ToolCall] | None = None

        for block in data.get("content", []):
            if block.get("type") == "text":
                text_content += block.get("text", "")
            elif block.get("type") == "tool_use":
                if tool_calls is None:
                    tool_calls = []
                tool_calls.append(
                    ToolCall(
                        id=block.get("id", ""),
                        type="function",
                        function={
                            "name": block.get("name", ""),
                            "arguments": block.get("input", {}),
                        },
                    )
                )

        return ModelOutput(
            text=text_content,
            usage=data.get("usage"),
            finish_reason=data.get("stop_reason"),
            tool_calls=tool_calls,
        )

    async def achat_stream(
        self, messages: List[Message], **kwargs
    ) -> AsyncIterator[ModelOutput]:
        anthropic_messages, system = self._build_anthropic_messages(messages)

        payload: Dict[str, Any] = {
            "model": self.config.model_name,
            "max_tokens": self.config.max_tokens or 4096,
            "messages": anthropic_messages,
            "stream": True,
        }

        if system:
            payload["system"] = system

        if self.config.temperature is not None:
            payload["temperature"] = self.config.temperature

        tools = kwargs.get("tools")
        if tools:
            payload["tools"] = [
                {
                    "name": t.get("name"),
                    "description": t.get("description", ""),
                    "input_schema": t.get("parameters", {}),
                }
                for t in tools
            ]

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.api_version,
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/v1/messages",
                json=payload,
                headers=headers,
            ) as response:
                response.raise_for_status()
                text_buffer = ""
                tool_call_buffers: Dict[str, Dict[str, Any]] = {}

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break

                    try:
                        event = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    event_type = event.get("type")

                    if event_type == "content_block_delta":
                        delta = event.get("delta", {})
                        if delta.get("type") == "text_delta":
                            text_buffer += delta.get("text", "")
                            yield ModelOutput(text=delta.get("text", ""))

                    elif event_type == "content_block_start":
                        block = event.get("content_block", {})
                        if block.get("type") == "tool_use":
                            idx = event.get("index", 0)
                            tool_call_buffers[str(idx)] = {
                                "id": block.get("id", ""),
                                "name": block.get("name", ""),
                                "input": "",
                            }

                    elif event_type == "content_block_stop":
                        idx = str(event.get("index", 0))
                        if idx in tool_call_buffers:
                            tc_data = tool_call_buffers[idx]
                            try:
                                input_dict = json.loads(tc_data["input"]) if tc_data["input"] else {}
                            except json.JSONDecodeError:
                                input_dict = {}
                            yield ModelOutput(
                                text="",
                                tool_calls=[
                                    ToolCall(
                                        id=tc_data["id"],
                                        type="function",
                                        function={
                                            "name": tc_data["name"],
                                            "arguments": input_dict,
                                        },
                                    )
                                ],
                            )

                    elif event_type == "message_stop":
                        yield ModelOutput(
                            text="",
                            finish_reason="end_turn",
                        )