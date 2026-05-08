import os
from typing import Any, AsyncIterator, Dict, List, Union

import openai

from aurora_core.model.base import BaseLLM
from aurora_core.schema.message import Message, ModelOutput, ToolCall
from aurora_core.schema.model import LLMConfig
from aurora_core.utils.retry import retry_on_transient


class OpenAILLM(BaseLLM):
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        extra_headers: Dict[str, str] = {}
        api_base = config.api_base or ""

        # Kimi coding API requires specific User-Agent and /v1 path
        if "kimi.com/coding" in api_base:
            extra_headers["User-Agent"] = "KimiCLI/1.0"
            # Ensure /v1 is in the path for Kimi Coding API
            if not api_base.rstrip("/").endswith("/v1"):
                api_base = api_base.rstrip("/") + "/v1"

        if config.model_type == "azure":
            self.client = openai.AsyncAzureOpenAI(
                api_key=config.api_key or os.getenv("AZURE_OPENAI_API_KEY") or "EMPTY",
                azure_endpoint=(api_base or "").rstrip("/"),
                api_version=str(config.extra.get("api_version") or "2024-10-21"),
                default_headers=extra_headers if extra_headers else None,
            )
        else:
            self.client = openai.AsyncOpenAI(
                api_key=config.api_key or os.getenv("OPENAI_API_KEY") or "EMPTY",
                base_url=api_base,
                default_headers=extra_headers if extra_headers else None,
            )

    def _build_openai_messages(
        self, messages: List[Message]
    ) -> List[Dict[str, Any]]:
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
        response = await self.client.chat.completions.create(
            model=self.config.model_name,
            messages=self._build_openai_messages(messages),
            stream=False,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            **kwargs,
        )
        choice = response.choices[0]
        message = choice.message
        content = message.content or ""
        # Kimi coding model may return reasoning_content instead of content
        if not content:
            reasoning = getattr(message, "reasoning_content", None) or ""
            content = reasoning
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
        import json as _json

        response = await self.client.chat.completions.create(
            model=self.config.model_name,
            messages=self._build_openai_messages(messages),
            stream=True,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            **kwargs,
        )
        # Use raw SSE lines to avoid SDK iterator hanging with Kimi's non-standard format
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
            data_str = line[5:].lstrip()  # remove "data:" prefix
            try:
                chunk_data = _json.loads(data_str)
            except _json.JSONDecodeError:
                continue
            choices = chunk_data.get("choices", [])
            if not choices:
                continue
            delta_data = choices[0].get("delta", {})

            # Check for actual content first
            content = delta_data.get("content", "") or ""
            is_reasoning = False

            # If no content, check for reasoning_content
            if not content:
                content = delta_data.get("reasoning_content", "") or ""
                is_reasoning = True

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
                for index in sorted(tool_call_buffers):
                    buffered = tool_call_buffers[index]
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
                    is_reasoning=is_reasoning,
                )
                continue

            if not content and not finish_reason:
                continue
            yield ModelOutput(
                text=content,
                finish_reason=finish_reason,
                is_reasoning=is_reasoning,
            )
