"""Extraction configuration routes — KG extraction config CRUD & batch extract.

Endpoints:

- ``GET  /extract/config``   — retrieve current extraction configuration
- ``POST /extract/config``   — update extraction configuration
- ``POST /extract/batch``    — run batch concurrent extraction on supplied texts

All routes receive ``name: str`` as a path parameter (from the
``/knowledge/{name}`` prefix applied at registration time).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(tags=["extraction"])


def get_knowledge_v2_service(request: Request) -> Any:
    """Resolve the KnowledgeV2Service from the system app registry."""
    from aurora_serve.knowledge.v2.service import KnowledgeV2Service

    return request.app.state.system_app.get_component(
        "knowledge_v2_service", KnowledgeV2Service
    )


# ── Request / Response schemas ───────────────────────────────────────


class ExtractionLanguageConfig(BaseModel):
    output_language: str = Field(
        default="English",
        description="Output language: English, Chinese, Japanese, Korean, etc.",
    )


class ExtractionEntityTypeConfig(BaseModel):
    custom_types: List[str] = Field(
        default_factory=list,
        description="Custom entity types to extract",
    )
    type_prompt_file: Optional[str] = Field(
        default=None,
        description="Path to an entity types prompt file",
    )


class ExtractionRelationTypeConfig(BaseModel):
    custom_types: List[str] = Field(
        default_factory=list,
        description="Custom relationship keyword types",
    )


class ExtractionConfigUpdateRequest(BaseModel):
    """Request body for updating extraction configuration."""

    entity_extract_max_gleaning: Optional[int] = Field(
        default=None, ge=0, le=10,
        description="LLM gleaning rounds for entity extraction",
    )
    relation_extract_max_gleaning: Optional[int] = Field(
        default=None, ge=0, le=10,
        description="LLM gleaning rounds for relationship extraction",
    )
    max_parallel_extract: Optional[int] = Field(
        default=None, ge=1, le=50,
        description="Maximum concurrent extraction tasks",
    )
    enable_incremental_extract: Optional[bool] = Field(
        default=None,
        description="Skip already-processed chunks",
    )
    max_total_records: Optional[int] = Field(default=None, ge=1, le=500)
    max_entity_records: Optional[int] = Field(default=None, ge=1, le=500)
    use_json: Optional[bool] = Field(default=None)
    enable_cache: Optional[bool] = Field(default=None)

    language: Optional[ExtractionLanguageConfig] = None
    entity_types: Optional[ExtractionEntityTypeConfig] = None
    relation_types: Optional[ExtractionRelationTypeConfig] = None

    entity_types_guidance: Optional[str] = Field(
        default=None, description="Free-form entity type guidance override"
    )
    relation_types_guidance: Optional[str] = Field(
        default=None, description="Free-form relation type guidance override"
    )


class ExtractionConfigResponse(BaseModel):
    """Response body for the current extraction configuration."""

    entity_extract_max_gleaning: int
    relation_extract_max_gleaning: int
    max_parallel_extract: int
    enable_incremental_extract: bool
    max_total_records: int
    max_entity_records: int
    use_json: bool
    enable_cache: bool
    language: str
    entity_types: List[str]
    relation_types: List[str]
    entity_types_guidance: Optional[str] = None
    relation_types_guidance: Optional[str] = None


class BatchExtractRequest(BaseModel):
    """Batch extraction request."""

    texts: List[str] = Field(
        ..., min_length=1,
        description="List of text chunks to extract from",
    )
    chunk_ids: Optional[List[str]] = Field(
        default=None,
        description="Optional chunk IDs (auto-generated if omitted)",
    )
    file_paths: Optional[List[str]] = Field(
        default=None,
        description="Optional source file paths for provenance",
    )


class BatchExtractItemResponse(BaseModel):
    entities: List[Dict[str, Any]] = Field(default_factory=list)
    relationships: List[Dict[str, Any]] = Field(default_factory=list)
    chunk_id: str = ""


class BatchExtractResponse(BaseModel):
    results: List[BatchExtractItemResponse] = Field(default_factory=list)
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    stats: Dict[str, Any] = Field(default_factory=dict)


# ── Routes ───────────────────────────────────────────────────────────


@router.get("/extract/config", response_model=ExtractionConfigResponse)
async def get_extract_config(
    name: str,
    service: Any = Depends(get_knowledge_v2_service),
) -> ExtractionConfigResponse:
    """Return the current KG extraction configuration."""
    try:
        cfg = service.get_extraction_config(name)
        return ExtractionConfigResponse(
            entity_extract_max_gleaning=cfg.extraction.entity_extract_max_gleaning,
            relation_extract_max_gleaning=cfg.extraction.relation_extract_max_gleaning,
            max_parallel_extract=cfg.extraction.max_parallel_extract,
            enable_incremental_extract=cfg.extraction.enable_incremental_extract,
            max_total_records=cfg.extraction.max_total_records,
            max_entity_records=cfg.extraction.max_entity_records,
            use_json=cfg.extraction.use_json,
            enable_cache=cfg.extraction.enable_cache,
            language=cfg.addon.language,
            entity_types=list(cfg.entity_types.effective_types),
            relation_types=list(cfg.entity_types.custom_relation_types),
            entity_types_guidance=cfg.addon.entity_types_guidance,
            relation_types_guidance=cfg.addon.relation_types_guidance,
        )
    except Exception as exc:
        logger.exception("Failed to get extraction config")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/extract/config", response_model=ExtractionConfigResponse)
async def update_extract_config(
    name: str,
    body: ExtractionConfigUpdateRequest,
    service: Any = Depends(get_knowledge_v2_service),
) -> ExtractionConfigResponse:
    """Update the KG extraction configuration (partial update)."""
    try:
        cfg = service.update_extraction_config(name, body.model_dump(exclude_none=True))
        return ExtractionConfigResponse(
            entity_extract_max_gleaning=cfg.extraction.entity_extract_max_gleaning,
            relation_extract_max_gleaning=cfg.extraction.relation_extract_max_gleaning,
            max_parallel_extract=cfg.extraction.max_parallel_extract,
            enable_incremental_extract=cfg.extraction.enable_incremental_extract,
            max_total_records=cfg.extraction.max_total_records,
            max_entity_records=cfg.extraction.max_entity_records,
            use_json=cfg.extraction.use_json,
            enable_cache=cfg.extraction.enable_cache,
            language=cfg.addon.language,
            entity_types=list(cfg.entity_types.effective_types),
            relation_types=list(cfg.entity_types.custom_relation_types),
            entity_types_guidance=cfg.addon.entity_types_guidance,
            relation_types_guidance=cfg.addon.relation_types_guidance,
        )
    except Exception as exc:
        logger.exception("Failed to update extraction config")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/extract/batch", response_model=BatchExtractResponse)
async def batch_extract(
    name: str,
    body: BatchExtractRequest,
    service: Any = Depends(get_knowledge_v2_service),
) -> BatchExtractResponse:
    """Run batch concurrent KG extraction on the supplied text chunks."""
    try:
        chunk_ids = body.chunk_ids or [
            f"batch-{i}" for i in range(len(body.texts))
        ]
        file_paths = body.file_paths or ["" for _ in body.texts]

        if len(chunk_ids) != len(body.texts):
            raise HTTPException(
                status_code=422,
                detail="chunk_ids length must match texts length",
            )

        chunks = [
            {
                "text": text,
                "chunk_id": cid,
                "file_path": fp,
            }
            for text, cid, fp in zip(body.texts, chunk_ids, file_paths)
        ]

        result = await service.batch_extract(name, chunks)

        items = [
            BatchExtractItemResponse(
                entities=[
                    {
                        "entity_name": e.entity_name,
                        "entity_type": e.entity_type,
                        "entity_description": e.entity_description,
                    }
                    for e in r.entities
                ],
                relationships=[
                    {
                        "source_entity": rel.source_entity,
                        "target_entity": rel.target_entity,
                        "relationship_keywords": rel.relationship_keywords,
                        "relationship_description": rel.relationship_description,
                    }
                    for rel in r.relationships
                ],
                chunk_id=r.chunk_id,
            )
            for r in result.results
        ]

        return BatchExtractResponse(
            results=items,
            errors=result.errors,
            stats={
                "total_chunks": result.stats.total_chunks,
                "successful_chunks": result.stats.successful_chunks,
                "failed_chunks": result.stats.failed_chunks,
                "skipped_chunks": result.stats.skipped_chunks,
                "total_entities": result.stats.total_entities,
                "total_relationships": result.stats.total_relationships,
                "elapsed_seconds": result.stats.elapsed_seconds,
            },
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Batch extraction failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
