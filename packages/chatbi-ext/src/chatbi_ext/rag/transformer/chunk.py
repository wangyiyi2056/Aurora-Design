from dataclasses import dataclass
from typing import List

from chatbi_ext.rag.knowledge.base import Document


@dataclass
class ChunkParameters:
    chunk_size: int = 500
    chunk_overlap: int = 50


class ChunkManager:
    def __init__(self, params: ChunkParameters):
        self.params = params

    def split(self, documents: List[Document]) -> List[Document]:
        chunks = []
        for doc in documents:
            text = doc.content
            start = 0
            while start < len(text):
                end = start + self.params.chunk_size
                chunk_text = text[start:end]
                chunks.append(
                    Document(
                        content=chunk_text,
                        metadata={**doc.metadata, "chunk_index": len(chunks)},
                    )
                )
                start += self.params.chunk_size - self.params.chunk_overlap
        return chunks
