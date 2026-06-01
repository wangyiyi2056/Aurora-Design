"""Abstract chunker base and shared data structures.

Migrated from LightRAG ``chunker/`` interfaces.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ChunkParameters:
    """Parameters controlling how text is split into chunks.

    Attributes
    ----------
    chunk_size:
        Target chunk size in tokens (default 1200, from LightRAG).
    chunk_overlap:
        Number of overlap tokens between consecutive chunks (default 100).
    strategy:
        Chunking strategy name: ``"fixed"``, ``"recursive"``,
        ``"semantic"``, ``"paragraph"``.
    """

    chunk_size: int = 1200
    chunk_overlap: int = 100
    strategy: str = "fixed"


@dataclass(frozen=True)
class TextChunk:
    """A single text chunk produced by a chunker.

    Attributes
    ----------
    content:
        The chunk text.
    chunk_index:
        Zero-based index within the source document.
    doc_id:
        Source document ID.
    tokens:
        Number of tokens in this chunk.
    metadata:
        Arbitrary metadata (file_path, page number, etc.).
    """

    content: str
    chunk_index: int
    doc_id: str
    tokens: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseChunker(ABC):
    """Abstract text chunker."""

    def __init__(self, params: ChunkParameters | None = None) -> None:
        self.params = params or ChunkParameters()

    @abstractmethod
    async def split(self, text: str, doc_id: str, **metadata: Any) -> list[TextChunk]:
        """Split *text* into chunks.

        Parameters
        ----------
        text:
            Full document text.
        doc_id:
            Source document identifier.
        metadata:
            Extra metadata to attach to every chunk.
        """
