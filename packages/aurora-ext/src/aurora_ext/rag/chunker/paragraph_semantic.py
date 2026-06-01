"""Paragraph-aware semantic chunking.

Migrated from LightRAG ``chunker/paragraph_semantic.py`` (strategy
code ``P``).  Splits on paragraph boundaries (double newline) and
merges adjacent paragraphs until the chunk size limit is reached.
"""

from __future__ import annotations

from typing import Any

from aurora_core.rag.utils.tokenizer import count_tokens
from aurora_ext.rag.chunker.base import BaseChunker, ChunkParameters, TextChunk


class ParagraphChunker(BaseChunker):
    """Split text on paragraph boundaries, merging small paragraphs.

    Each paragraph (separated by ``\\n\\n``) is treated as an atomic
    unit.  Adjacent paragraphs are merged into the same chunk until
    ``chunk_size`` tokens are exceeded, at which point a new chunk
    starts.
    """

    def __init__(self, params: ChunkParameters | None = None) -> None:
        if params is None:
            params = ChunkParameters(chunk_size=2000, chunk_overlap=0)
        super().__init__(params)

    async def split(self, text: str, doc_id: str, **metadata: Any) -> list[TextChunk]:
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if not paragraphs:
            return []

        chunk_size = self.params.chunk_size
        chunks: list[TextChunk] = []
        current_parts: list[str] = []
        current_tokens = 0

        for para in paragraphs:
            para_tokens = count_tokens(para)

            if current_tokens + para_tokens > chunk_size and current_parts:
                chunk_text = "\n\n".join(current_parts)
                chunks.append(TextChunk(
                    content=chunk_text,
                    chunk_index=len(chunks),
                    doc_id=doc_id,
                    tokens=current_tokens,
                    metadata=dict(metadata),
                ))
                current_parts = []
                current_tokens = 0

            current_parts.append(para)
            current_tokens += para_tokens

        # Flush remaining
        if current_parts:
            chunk_text = "\n\n".join(current_parts)
            chunks.append(TextChunk(
                content=chunk_text,
                chunk_index=len(chunks),
                doc_id=doc_id,
                tokens=current_tokens,
                metadata=dict(metadata),
            ))

        return chunks
