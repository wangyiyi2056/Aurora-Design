from typing import Any, Dict, List

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from aurora_serve.knowledge.service import KnowledgeService

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


def get_knowledge_service(request: Request) -> KnowledgeService:
    return request.app.state.system_app.get_component("knowledge_service", KnowledgeService)


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
    service: KnowledgeService = Depends(get_knowledge_service),
) -> Dict[str, Any]:
    return await service.query(name, query, top_k=top_k)
