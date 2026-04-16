from abc import ABC, abstractmethod
from typing import List

from chatbi_ext.rag.knowledge.base import Document


class BaseRetriever(ABC):
    @abstractmethod
    async def retrieve(self, query: str) -> List[Document]:
        ...
