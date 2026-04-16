import os
from typing import Any, AsyncIterator, Dict, List, Union

import openai

from chatbi_core.model.base import BaseLLM
from chatbi_core.schema.message import Message, ModelOutput
from chatbi_core.schema.model import LLMConfig


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
            if isinstance(m.content, list):
                result.append({"role": m.role, "content": m.content})
            else:
                result.append({"role": m.role, "content": m.content})
        return result

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
        return ModelOutput(
            text=choice.message.content or "",
            usage=response.usage.model_dump() if response.usage else None,
            finish_reason=choice.finish_reason,
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
            delta = chunk.choices[0].delta.content or ""
            yield ModelOutput(
                text=delta,
                finish_reason=chunk.choices[0].finish_reason,
            )
