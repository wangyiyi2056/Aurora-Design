from abc import ABC, abstractmethod
from typing import Any, List

from chatbi_ext.rag.knowledge.base import Document
from chatbi_ext.rag.retriever.base import BaseRetriever


class BaseAssembler(ABC):
    @abstractmethod
    def as_retriever(self, **kwargs: Any) -> BaseRetriever:
        ...

    @abstractmethod
    def persist(self, **kwargs: Any) -> List[str]:
        ...
