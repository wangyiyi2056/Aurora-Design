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


# ── Document Content & Chunks ─────────────────────────────────────────


@router.get("/documents/{doc_id}/content")
async def get_document_content(
    name: str,
    doc_id: str,
    service: Any = Depends(get_knowledge_v2_service),
) -> Dict[str, Any]:
    """Retrieve the full text content of a processed document.

    Returns ``{content, file_path, content_type}``.
    """
    try:
        return await service.get_document_content(name, doc_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to get document content for %s", doc_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/documents/{doc_id}/chunks")
async def get_document_chunks(
    name: str,
    doc_id: str,
    service: Any = Depends(get_knowledge_v2_service),
) -> Dict[str, Any]:
    """Retrieve all chunks produced from a document, sorted by order index.

    Returns ``{chunks: [{id, content, chunk_order_index, tokens, file_path}]}``.
    """
    try:
        chunks = await service.get_document_chunks(name, doc_id)
        return {"chunks": chunks, "total": len(chunks)}
    except Exception as exc:
        logger.exception("Failed to get chunks for document %s", doc_id)
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


@router.get("/documents/cache_stats")
async def get_llm_cache_stats(
    name: str,
    service: Any = Depends(get_knowledge_v2_service),
) -> Dict[str, Any]:
    """Get statistics about the LLM response cache."""
    try:
        return await service.get_llm_cache_stats(name)
    except Exception as exc:
        logger.exception("Failed to get LLM cache stats")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/documents/clear_cache")
async def clear_llm_cache(
    name: str,
    service: Any = Depends(get_knowledge_v2_service),
) -> Dict[str, Any]:
    """Clear the LLM response cache.

    Returns:
        - success: whether the operation succeeded
        - deleted_count: number of cache entries deleted
    """
    try:
        return await service.clear_llm_cache(name)
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
    """Clear LLM cache and reprocess ALL documents (including already processed).

    Only clears the LLM extraction cache — does NOT delete document content or chunks.
    """
    try:
        result = await service.reprocess_all(name)
        return result
    except Exception as exc:
        logger.exception("Failed to reprocess all documents")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── Diagnostics & Repair ──────────────────────────────────────────────


@router.get("/documents/diagnose")
async def diagnose_documents(
    name: str,
    service: Any = Depends(get_knowledge_v2_service),
) -> Dict[str, Any]:
    """Diagnose documents for missing content or chunks.

    Returns a report showing which PROCESSED documents have lost their
    content/chunks (e.g., due to a previous ``clear_llm_cache`` bug) and
    which ones can be repaired from the original file on disk.
    """
    try:
        return await service.diagnose_documents(name)
    except Exception as exc:
        logger.exception("Failed to diagnose documents")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/documents/repair")
async def repair_documents(
    name: str,
    service: Any = Depends(get_knowledge_v2_service),
) -> Dict[str, Any]:
    """Re-process documents that lost their content/chunks.

    Only repairs documents whose original file still exists on disk.
    Documents inserted via ``insert_text`` that lost their content
    cannot be automatically repaired — they need to be re-uploaded.
    """
    try:
        return await service.repair_documents(name)
    except Exception as exc:
        logger.exception("Failed to repair documents")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
