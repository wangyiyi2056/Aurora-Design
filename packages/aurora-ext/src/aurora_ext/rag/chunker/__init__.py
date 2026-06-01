"""Text chunking strategies — split documents into indexable chunks.

Migrated from LightRAG ``chunker/`` module.
"""

from aurora_ext.rag.chunker.base import BaseChunker, ChunkParameters, TextChunk
from aurora_ext.rag.chunker.fixed_token import FixedTokenChunker
from aurora_ext.rag.chunker.recursive_char import RecursiveCharacterChunker
from aurora_ext.rag.chunker.semantic_vector import SemanticVectorChunker
from aurora_ext.rag.chunker.paragraph_semantic import ParagraphChunker

__all__ = [
    "BaseChunker",
    "ChunkParameters",
    "FixedTokenChunker",
    "ParagraphChunker",
    "RecursiveCharacterChunker",
    "SemanticVectorChunker",
    "TextChunk",
]
