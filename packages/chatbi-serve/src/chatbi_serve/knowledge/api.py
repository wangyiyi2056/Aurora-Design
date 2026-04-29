from typing import Any, Dict, List

from fastapi import APIRouter, Depends, File, Request, UploadFile

from chatbi_serve.knowledge.service import KnowledgeService

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


def get_knowledge_service(request: Request) -> KnowledgeService:
    return request.app.state.system_app.get_component("knowledge_service", KnowledgeService)


@router.post("/upload")
async def upload_knowledge(
    name: str,
    file: UploadFile = File(...),
    service: KnowledgeService = Depends(get_knowledge_service),
) -> Dict[str, Any]:
    return await service.upload(name, file)


@router.get("")
async def list_knowledge(
    service: KnowledgeService = Depends(get_knowledge_service),
) -> List[str]:
    return service.list_names()


@router.post("/{name}/query")
async def query_knowledge(
    name: str,
    query: str,
    service: KnowledgeService = Depends(get_knowledge_service),
) -> Dict[str, Any]:
    return await service.query(name, query)
