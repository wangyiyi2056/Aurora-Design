import os
from typing import List

import openai

from aurora_core.model.base import BaseEmbeddings
from aurora_core.schema.model import LLMConfig


class OpenAIEmbeddings(BaseEmbeddings):
    def __init__(self, config: LLMConfig):
        self.config = config
        self.client = openai.AsyncOpenAI(
            api_key=config.api_key or os.getenv("OPENAI_API_KEY"),
            base_url=config.api_base,
        )

    async def aembed(self, texts: List[str]) -> List[List[float]]:
        response = await self.client.embeddings.create(
            model=self.config.model_name,
            input=texts,
        )
        return [item.embedding for item in response.data]
