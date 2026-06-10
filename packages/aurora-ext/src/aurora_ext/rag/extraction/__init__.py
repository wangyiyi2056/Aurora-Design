"""Knowledge graph extraction — entity/relationship extraction via LLM.

Migrated from LightRAG ``operate.py`` and ``prompt.py``.
"""

from aurora_ext.rag.extraction.config import (
    AddonParams,
    ExtractionConfig,
    EntityTypeConfig,
    KGExtractionFullConfig,
)
from aurora_ext.rag.extraction.orchestrator import (
    BatchExtractionResult,
    BatchExtractionStats,
    ExtractionOrchestrator,
)
from aurora_ext.rag.extraction.types import (
    ExtractedEntity,
    ExtractedRelationship,
    ExtractionResult,
)
from aurora_ext.rag.extraction.extractor import EntityRelationExtractor
from aurora_ext.rag.extraction.merger import merge_entities, merge_relationships
from aurora_ext.rag.extraction.multimodal_analyzer import (
    AnalysisMode,
    DocumentAnalysisReport,
    MultimodalAnalyzer,
    MultimodalAnalysisResult,
    get_enabled_modes,
    has_vlm_hints,
)
from aurora_ext.rag.extraction.summarizer import summarize_descriptions

__all__ = [
    "AddonParams",
    "AnalysisMode",
    "BatchExtractionResult",
    "BatchExtractionStats",
    "DocumentAnalysisReport",
    "EntityRelationExtractor",
    "EntityTypeConfig",
    "ExtractedEntity",
    "ExtractedRelationship",
    "ExtractionConfig",
    "ExtractionOrchestrator",
    "ExtractionResult",
    "KGExtractionFullConfig",
    "MultimodalAnalyzer",
    "MultimodalAnalysisResult",
    "get_enabled_modes",
    "has_vlm_hints",
    "merge_entities",
    "merge_relationships",
    "summarize_descriptions",
]
