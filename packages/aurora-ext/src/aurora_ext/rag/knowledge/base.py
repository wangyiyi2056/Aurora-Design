from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List


@dataclass
class Document:
    content: str
    metadata: dict


class BaseKnowledge(ABC):
    @abstractmethod
    def load(self) -> List[Document]:
        ...
