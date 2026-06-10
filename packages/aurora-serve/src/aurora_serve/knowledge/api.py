import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from aurora_serve.knowledge.service import KnowledgeService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


def get_knowledge_service(request: Request) -> KnowledgeService:
    return request.app.state.system_app.get_component("knowledge_service", KnowledgeService)


def get_knowledge_v2_service(request: Request):
    from aurora_serve.knowledge.v2.service import KnowledgeV2Service
    return request.app.state.system_app.get_component("knowledge_v2_service", KnowledgeV2Service)


class CreateKnowledgeRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    chunk_strategy: str = "fixed"
    chunk_size: int = Field(default=1200, ge=1, le=8192)
    chunk_overlap: int = Field(default=100, ge=0)


@router.post("")
async def create_knowledge(
    body: CreateKnowledgeRequest,
    service: KnowledgeService = Depends(get_knowledge_service),
) -> Dict[str, Any]:
    try:
        return service.create(
            name=body.name,
            chunk_strategy=body.chunk_strategy,
            chunk_size=body.chunk_size,
            chunk_overlap=body.chunk_overlap,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/upload")
async def upload_knowledge(
    name: str,
    chunk_strategy: str = "fixed",
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    file: UploadFile = File(...),
    service: KnowledgeService = Depends(get_knowledge_service),
) -> Dict[str, Any]:
    return await service.upload(
        name,
        file,
        chunk_strategy=chunk_strategy,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )


@router.get("")
async def list_knowledge(
    request: Request,
    service: KnowledgeService = Depends(get_knowledge_service),
) -> List[str]:
    """List all knowledge bases (merged from V1 ChromaDB and V2 doc_status)."""
    names = set(service.list_names())

    # Also include V2 knowledge base names from doc_status storage
    try:
        v2_service = get_knowledge_v2_service(request)
        if v2_service is not None:
            all_docs, _ = await v2_service._doc_status.get_all_docs(
                page_size=99999
            )
            for doc in all_docs:
                if doc.kb_name:
                    names.add(doc.kb_name)
    except Exception:
        logger.debug("Could not query V2 doc_status for knowledge base names", exc_info=True)

    return sorted(names)


@router.get("/{name}")
async def get_knowledge_detail(
    name: str,
    request: Request,
    service: KnowledgeService = Depends(get_knowledge_service),
) -> Dict[str, Any]:
    """Get knowledge base detail, merging V1 and V2 data."""
    detail = service.detail(name)

    # Try to enrich with V2 document stats
    v2_docs = 0
    v2_chunks = 0
    try:
        v2_service = get_knowledge_v2_service(request)
        if v2_service is not None:
            all_docs, total = await v2_service._doc_status.get_all_docs(
                kb_name=name, page_size=99999
            )
            v2_docs = total
            v2_chunks = sum(d.chunks_count for d in all_docs)
    except Exception:
        logger.debug("Could not query V2 doc_status for KB '%s'", name, exc_info=True)

    if detail is not None:
        # Merge V2 stats into V1 detail
        detail["chunks"] = detail.get("chunks", 0) + v2_chunks
        detail["documents"] = v2_docs
        return detail

    # V1 not found — return V2-only detail if available
    if v2_docs > 0:
        return {
            "name": name,
            "collection_name": name,
            "persist_directory": "data/rag",
            "chunks": v2_chunks,
            "chunk_strategy": "fixed",
            "chunk_size": 1200,
            "chunk_overlap": 100,
            "documents": v2_docs,
            "source": "v2",
        }

    raise HTTPException(status_code=404, detail="Knowledge base not found")


@router.get("/{name}/documents")
async def list_knowledge_documents(
    name: str,
    service: KnowledgeService = Depends(get_knowledge_service),
) -> Dict[str, Any]:
    if service.detail(name) is None:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return {"items": service.list_documents(name)}


@router.delete("/{name}/documents/{document_id}")
async def delete_knowledge_document(
    name: str,
    document_id: str,
    service: KnowledgeService = Depends(get_knowledge_service),
) -> Dict[str, Any]:
    return {"success": service.delete_document(name, document_id)}


@router.delete("/{name}")
async def delete_knowledge_base(
    name: str,
    service: KnowledgeService = Depends(get_knowledge_service),
) -> Dict[str, Any]:
    return {"success": service.delete_knowledge_base(name)}


@router.post("/{name}/query")
async def query_knowledge(
    name: str,
    query: str,
    top_k: int = 5,
    source_filter: str | None = None,
    min_score: float = 0.0,
    service: KnowledgeService = Depends(get_knowledge_service),
) -> Dict[str, Any]:
    """Query a knowledge base and receive results with citation tracking.

    Returns an answer together with a list of citations pointing back to
    the original source documents, including file path, page number,
    chunk ID, and relevance score.
    """
    return await service.query(
        name,
        query,
        top_k=top_k,
        source_filter=source_filter,
        min_score=min_score,
    )
