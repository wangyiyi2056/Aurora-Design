"""Fixed-token-size chunking with overlap.

Migrated from LightRAG ``chunker/token_size.py`` (strategy code ``F``).
Uses ``tiktoken`` for token-aware splitting, falling back to character-
based estimation when tiktoken is unavailable.
"""

from __future__ import annotations

from typing import Any

from aurora_core.rag.utils.tokenizer import TiktokenTokenizer
from aurora_ext.rag.chunker.base import BaseChunker, ChunkParameters, TextChunk


class FixedTokenChunker(BaseChunker):
    """Split text into fixed-size token windows with overlap."""

    def __init__(self, params: ChunkParameters | None = None) -> None:
        super().__init__(params)
        self._tokenizer = TiktokenTokenizer()

    async def split(self, text: str, doc_id: str, **metadata: Any) -> list[TextChunk]:
        chunk_size = self.params.chunk_size
        overlap = min(self.params.chunk_overlap, chunk_size // 4)

        tokens = self._tokenizer.encode(text)
        if not tokens:
            return []

        chunks: list[TextChunk] = []
        idx = 0
        start = 0

        while start < len(tokens):
            end = min(start + chunk_size, len(tokens))
            chunk_tokens = tokens[start:end]
            chunk_text = self._tokenizer.decode(chunk_tokens)

            chunks.append(TextChunk(
                content=chunk_text,
                chunk_index=idx,
                doc_id=doc_id,
                tokens=len(chunk_tokens),
                metadata=dict(metadata),
            ))

            idx += 1
            if end >= len(tokens):
                break
            start = end - overlap

        return chunks
