import os
from typing import Any, AsyncIterator, Dict, List, Union

import openai

from chatbi_core.model.base import BaseLLM
from chatbi_core.schema.message import Message, ModelOutput, ToolCall
from chatbi_core.schema.model import LLMConfig
from chatbi_core.utils.retry import retry_on_transient


class OpenAILLM(BaseLLM):
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.client = openai.AsyncOpenAI(
            api_key=config.api_key or os.getenv("OPENAI_API_KEY"),
            base_url=config.api_base,
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
            text=message.content or "",
            usage=response.usage.model_dump() if response.usage else None,
            finish_reason=choice.finish_reason,
            tool_calls=tool_calls,
        )

    async def achat_stream(
        self, messages: List[Message], **kwargs
    ) -> AsyncIterator[ModelOutput]:
        response = await self.client.chat.completions.create(
            model=self.config.model_name,
            messages=self._build_openai_messages(messages),
            stream=True,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            **kwargs,
        )
        async for chunk in response:
            delta = chunk.choices[0].delta
            text = delta.content or ""
            tool_calls: List[ToolCall] | None = None
            if delta.tool_calls:
                tool_calls = [
                    ToolCall(
                        id=tc.id or "",
                        type=tc.type or "function",
                        function={
                            "name": tc.function.name or "",
                            "arguments": tc.function.arguments or "",
                        },
                    )
                    for tc in delta.tool_calls
                ]
            yield ModelOutput(
                text=text,
                finish_reason=chunk.choices[0].finish_reason,
                tool_calls=tool_calls,
            )
