from abc import ABC, abstractmethod
from typing import AsyncIterator, List

from chatbi_core.schema.message import Message, ModelOutput
from chatbi_core.schema.model import LLMConfig


class BaseLLM(ABC):
    def __init__(self, config: LLMConfig):
        self.config = config

    @abstractmethod
    async def achat(self, messages: List[Message], **kwargs) -> ModelOutput:
        """Non-streaming chat."""

    @abstractmethod
    async def achat_stream(
        self, messages: List[Message], **kwargs
    ) -> AsyncIterator[ModelOutput]:
        """Streaming chat."""


class BaseEmbeddings(ABC):
    @abstractmethod
    async def aembed(self, texts: List[str]) -> List[List[float]]:
        """Embed texts into vectors."""
