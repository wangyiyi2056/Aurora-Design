"""Document management routes — ingestion, pipeline, status tracking.

Endpoints for uploading files, inserting texts, scanning directories,
and managing the document processing pipeline.

All routes receive ``name: str`` as a path parameter (from the
``/knowledge/{name}`` prefix applied at registration time).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from aurora_serve.knowledge.v2.schemas import (
    DeleteDocRequest,
    DocStatusResponse,
    DocumentsRequest,
    InsertResponse,
    InsertTextRequest,
    InsertTextsRequest,
    PipelineStatusResponse,
    ScanResponse,
    StatusCountsResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["documents"])


def get_knowledge_v2_service(request: Request) -> Any:
    """Resolve the KnowledgeV2Service from the system app registry."""
    from aurora_serve.knowledge.v2.service import KnowledgeV2Service

    return request.app.state.system_app.get_component(
        "knowledge_v2_service", KnowledgeV2Service
    )


# ── Upload & Insert ──────────────────────────────────────────────────


@router.post("/documents/upload", response_model=InsertResponse)
async def upload_document(
    name: str,
    file: UploadFile = File(...),
    service: Any = Depends(get_knowledge_v2_service),
) -> InsertResponse:
    """Upload a file for ingestion into the knowledge base."""
    try:
        return await service.upload_file(name, file)
    except Exception as exc:
        logger.exception("Failed to upload file: %s", file.filename)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/documents/text", response_model=InsertResponse)
async def insert_text(
    name: str,
    req: InsertTextRequest,
    service: Any = Depends(get_knowledge_v2_service),
) -> InsertResponse:
    """Insert a single text document into the knowledge base."""
    try:
        return await service.insert_text(name, req.text, file_source=req.file_source)
    except Exception as exc:
        logger.exception("Failed to insert text")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/documents/texts", response_model=InsertResponse)
async def insert_texts(
    name: str,
    req: InsertTextsRequest,
    service: Any = Depends(get_knowledge_v2_service),
) -> InsertResponse:
    """Batch-insert multiple text documents."""
    try:
        return await service.insert_texts(
            name, req.texts, file_sources=req.file_sources
        )
    except Exception as exc:
        logger.exception("Failed to insert texts")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── Pipeline & Scanning ──────────────────────────────────────────────


@router.post("/documents/scan", response_model=ScanResponse)
async def scan_directory(
    name: str,
    service: Any = Depends(get_knowledge_v2_service),
) -> ScanResponse:
    """Scan the input directory for new documents to ingest."""
    try:
        return await service.scan_directory(name)
    except Exception as exc:
        logger.exception("Failed to scan directory")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/documents/pipeline_status", response_model=PipelineStatusResponse)
async def get_pipeline_status(
    name: str,
    service: Any = Depends(get_knowledge_v2_service),
) -> PipelineStatusResponse:
    """Get the current state of the ingestion pipeline."""
    try:
        return await service.get_pipeline_status(name)
    except Exception as exc:
        logger.exception("Failed to get pipeline status")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/documents/cancel_pipeline")
async def cancel_pipeline(
    name: str,
    service: Any = Depends(get_knowledge_v2_service),
) -> Dict[str, Any]:
    """Request cancellation of the running pipeline job."""
    try:
        cancelled = await service.cancel_pipeline(name)
        return {"cancelled": cancelled}
    except Exception as exc:
        logger.exception("Failed to cancel pipeline")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── Status & Listing ─────────────────────────────────────────────────


@router.get("/documents/status_counts", response_model=StatusCountsResponse)
async def get_status_counts(
    name: str,
    service: Any = Depends(get_knowledge_v2_service),
) -> StatusCountsResponse:
    """Get document counts grouped by processing status."""
    try:
        return await service.get_status_counts(name)
    except Exception as exc:
        logger.exception("Failed to get status counts")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/documents/paginated")
async def list_documents_paginated(
    name: str,
    req: DocumentsRequest,
    service: Any = Depends(get_knowledge_v2_service),
) -> Dict[str, Any]:
    """Paginated document listing with status filters."""
    try:
        docs, total = await service.get_documents_paginated(
            name,
            status_filter=req.status_filter,
            status_filters=req.status_filters,
            page=req.page,
            page_size=req.page_size,
            sort_field=req.sort_field,
            sort_direction=req.sort_direction,
        )
        return {
            "items": [DocStatusResponse(**d) for d in docs],
            "total": total,
            "page": req.page,
            "page_size": req.page_size,
        }
    except Exception as exc:
        logger.exception("Failed to list documents")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/documents/track/{track_id}", response_model=List[DocStatusResponse])
async def get_track_status(
    name: str,
    track_id: str,
    service: Any = Depends(get_knowledge_v2_service),
) -> List[DocStatusResponse]:
    """Get processing status for all documents in a tracking batch."""
    try:
        docs = await service.get_docs_by_track_id(name, track_id)
        return [DocStatusResponse(**d) for d in docs]
    except Exception as exc:
        logger.exception("Failed to get track status for %s", track_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── Delete & Cache ───────────────────────────────────────────────────


@router.delete("/documents")
async def delete_documents(
    name: str,
    req: DeleteDocRequest,
    service: Any = Depends(get_knowledge_v2_service),
) -> Dict[str, Any]:
    """Delete one or more documents by ID."""
    try:
        result = await service.delete_documents(
            name,
            doc_ids=req.doc_ids,
            delete_file=req.delete_file,
            delete_llm_cache=req.delete_llm_cache,
            force=req.force,
        )
        return result
    except Exception as exc:
        logger.exception("Failed to delete documents")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/documents/clear_cache")
async def clear_llm_cache(
    name: str,
    service: Any = Depends(get_knowledge_v2_service),
) -> Dict[str, Any]:
    """Clear the LLM response cache."""
    try:
        cleared = await service.clear_llm_cache(name)
        return {"cleared": cleared}
    except Exception as exc:
        logger.exception("Failed to clear LLM cache")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/documents/reprocess_failed")
async def reprocess_failed_documents(
    name: str,
    service: Any = Depends(get_knowledge_v2_service),
) -> Dict[str, Any]:
    """Retry processing of previously failed documents."""
    try:
        result = await service.reprocess_failed(name)
        return result
    except Exception as exc:
        logger.exception("Failed to reprocess documents")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/documents/reprocess_all")
async def reprocess_all_documents(
    name: str,
    service: Any = Depends(get_knowledge_v2_service),
) -> Dict[str, Any]:
    """Clear LLM cache and reprocess ALL documents (including already processed)."""
    try:
        result = await service.reprocess_all(name)
        return result
    except Exception as exc:
        logger.exception("Failed to reprocess all documents")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
