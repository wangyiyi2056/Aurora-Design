from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from aurora_ext.rag.knowledge.base import Document
from aurora_ext.rag.retrieval.citation_tracker import generate_chunk_id


@dataclass
class ChunkParameters:
    chunk_size: int = 500
    chunk_overlap: int = 50


class ChunkManager:
    """Split documents into overlapping chunks with citation metadata.

    Each resulting chunk carries the following extra metadata keys:

    * ``chunk_id`` — deterministic unique identifier
    * ``file_path`` — originating file path (copied from the source doc)
    * ``start_pos`` / ``end_pos`` — character offsets inside the source
    * ``page_number`` — page number when the source doc provides
      ``page_boundaries`` (list of character offsets for each page)
    """

    def __init__(self, params: ChunkParameters):
        self.params = params

    def split(self, documents: List[Document]) -> List[Document]:
        chunks: list[Document] = []
        for doc in documents:
            text = doc.content
            file_path: str = doc.metadata.get("source", doc.metadata.get("file_path", ""))
            page_boundaries: list[int] = doc.metadata.get("page_boundaries", [])

            start = 0
            while start < len(text):
                end = start + self.params.chunk_size
                chunk_text = text[start:end]
                chunk_index = len(chunks)

                meta: Dict[str, Any] = {
                    **doc.metadata,
                    "chunk_index": chunk_index,
                    "chunk_id": generate_chunk_id(file_path or str(id(doc)), chunk_index),
                    "start_pos": start,
                    "end_pos": min(end, len(text)),
                }

                if file_path:
                    meta["file_path"] = file_path

                page = self._resolve_page(start, page_boundaries)
                if page is not None:
                    meta["page_number"] = page

                chunks.append(Document(content=chunk_text, metadata=meta))
                start += self.params.chunk_size - self.params.chunk_overlap
        return chunks

    @staticmethod
    def _resolve_page(
        char_offset: int,
        page_boundaries: list[int],
    ) -> Optional[int]:
        """Map a character offset to a 1-based page number.

        ``page_boundaries[i]`` is the character offset where page *i+1*
        begins.  Returns ``None`` when no boundaries are provided.
        """
        if not page_boundaries:
            return None
        for page_idx in range(len(page_boundaries) - 1, -1, -1):
            if char_offset >= page_boundaries[page_idx]:
                return page_idx + 1
        return 1
