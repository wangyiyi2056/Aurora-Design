"""Knowledge graph extraction — entity/relationship extraction via LLM.

Migrated from LightRAG ``operate.py`` and ``prompt.py``.
"""

from aurora_ext.rag.extraction.types import (
    ExtractedEntity,
    ExtractedRelationship,
    ExtractionResult,
)
from aurora_ext.rag.extraction.extractor import EntityRelationExtractor
from aurora_ext.rag.extraction.merger import merge_entities, merge_relationships
from aurora_ext.rag.extraction.summarizer import summarize_descriptions

__all__ = [
    "EntityRelationExtractor",
    "ExtractedEntity",
    "ExtractedRelationship",
    "ExtractionResult",
    "merge_entities",
    "merge_relationships",
    "summarize_descriptions",
]
