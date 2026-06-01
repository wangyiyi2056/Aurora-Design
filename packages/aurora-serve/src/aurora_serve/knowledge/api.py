from typing import Any, Dict, List

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from aurora_serve.knowledge.service import KnowledgeService

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


def get_knowledge_service(request: Request) -> KnowledgeService:
    return request.app.state.system_app.get_component("knowledge_service", KnowledgeService)


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
    service: KnowledgeService = Depends(get_knowledge_service),
) -> List[str]:
    return service.list_names()


@router.get("/{name}")
async def get_knowledge_detail(
    name: str,
    service: KnowledgeService = Depends(get_knowledge_service),
) -> Dict[str, Any]:
    detail = service.detail(name)
    if detail is None:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return detail


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
