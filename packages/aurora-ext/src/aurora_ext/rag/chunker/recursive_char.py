"""Recursive character text splitting.

Migrated from LightRAG ``chunker/recursive_character.py`` (strategy
code ``R``).  Uses ``langchain-text-splitters`` with CJK-aware
separators.
"""

from __future__ import annotations

from typing import Any

from aurora_ext.rag.chunker.base import BaseChunker, ChunkParameters, TextChunk

_SEPARATORS = (
    "\n\n",
    "\n",
    "。",   # Chinese period
    "！",   # Chinese exclamation
    "？",   # Chinese question
    "；",   # Chinese semicolon
    "，",   # Chinese comma
    " ",
    "",
)

_SENTENCE_SPLIT_REGEX = r"(?<=[.?!])\s+|(?<=[。？！])"


class RecursiveCharacterChunker(BaseChunker):
    """Split text using LangChain's RecursiveCharacterTextSplitter.

    Uses CJK-aware separators for multilingual support.
    """

    def __init__(self, params: ChunkParameters | None = None) -> None:
        super().__init__(params)

    async def split(self, text: str, doc_id: str, **metadata: Any) -> list[TextChunk]:
        try:
            from langchain_text_splitters import RecursiveCharacterTextSplitter
        except ImportError:
            return await self._fallback_split(text, doc_id, **metadata)

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.params.chunk_size,
            chunk_overlap=self.params.chunk_overlap,
            separators=list(_SEPARATORS),
            length_function=len,
        )

        raw_chunks = splitter.split_text(text)
        return [
            TextChunk(
                content=chunk_text,
                chunk_index=i,
                doc_id=doc_id,
                tokens=len(chunk_text) // 4,
                metadata=dict(metadata),
            )
            for i, chunk_text in enumerate(raw_chunks)
        ]

    async def _fallback_split(self, text: str, doc_id: str, **metadata: Any) -> list[TextChunk]:
        """Fallback when langchain-text-splitters is not installed."""
        from aurora_ext.rag.chunker.fixed_token import FixedTokenChunker

        fallback = FixedTokenChunker(self.params)
        return await fallback.split(text, doc_id, **metadata)
