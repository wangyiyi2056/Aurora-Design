"""Semantic vector chunking — split by embedding similarity breakpoints.

Migrated from LightRAG ``chunker/semantic_vector.py`` (strategy code ``V``).
Uses ``langchain-experimental`` SemanticChunker when available, falling
back to RecursiveCharacterChunker.
"""

from __future__ import annotations

import logging
from typing import Any

from aurora_ext.rag.chunker.base import BaseChunker, ChunkParameters, TextChunk

logger = logging.getLogger(__name__)


class SemanticVectorChunker(BaseChunker):
    """Split text at semantic boundaries using embedding similarity.

    Sentences with low cosine similarity to their neighbours are treated
    as chunk boundaries.  Falls back to recursive character chunking
    when ``langchain-experimental`` or an embedding function is not
    available.
    """

    def __init__(
        self,
        params: ChunkParameters | None = None,
        embedding_func: Any | None = None,
    ) -> None:
        super().__init__(params)
        self._embedding_func = embedding_func

    async def split(self, text: str, doc_id: str, **metadata: Any) -> list[TextChunk]:
        if self._embedding_func is None:
            logger.warning("No embedding function provided — falling back to recursive chunker")
            return await self._fallback_split(text, doc_id, **metadata)

        try:
            from langchain_experimental.text_splitter import SemanticChunker
            from langchain_core.embeddings import Embeddings

            class _Adapter(Embeddings):
                def __init__(self, func: Any) -> None:
                    self._func = func

                def embed_documents(self, texts: list[str]) -> list[list[float]]:
                    import asyncio
                    return asyncio.get_event_loop().run_until_complete(self._func(texts))

                def embed_query(self, text: str) -> list[float]:
                    import asyncio
                    result = asyncio.get_event_loop().run_until_complete(self._func([text]))
                    return result[0]

            splitter = SemanticChunker(
                embeddings=_Adapter(self._embedding_func),
                breakpoint_threshold_type="percentile",
                breakpoint_threshold_amount=95,
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

        except ImportError:
            logger.warning("langchain-experimental not installed — falling back")
            return await self._fallback_split(text, doc_id, **metadata)
        except Exception as exc:
            logger.warning("Semantic chunking failed (%s) — falling back", exc)
            return await self._fallback_split(text, doc_id, **metadata)

    async def _fallback_split(self, text: str, doc_id: str, **metadata: Any) -> list[TextChunk]:
        from aurora_ext.rag.chunker.recursive_char import RecursiveCharacterChunker
        return await RecursiveCharacterChunker(self.params).split(text, doc_id, **metadata)
