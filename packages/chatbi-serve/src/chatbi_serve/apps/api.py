from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from chatbi_serve.apps.service import AppService
from chatbi_serve.chat.schema import ChatMessage, ChatRequest
from chatbi_serve.chat.service import ChatService
from chatbi_serve.metadata import AppEntity

router = APIRouter(prefix="/apps", tags=["apps"])


class AppRequest(BaseModel):
    name: str | None = None
    description: str = ""
    type: str = "chat"
    model: str = ""
    published: bool = False
    knowledge_ids: list[str] = Field(default_factory=list)
    datasource_ids: list[str] = Field(default_factory=list)
    skill_names: list[str] = Field(default_factory=list)


class PublishRequest(BaseModel):
    published: bool = True


class AppRunRequest(BaseModel):
    messages: list[ChatMessage]
    stream: bool = False
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    session_id: str | None = None
    ext_info: dict[str, Any] = Field(default_factory=dict)


def get_app_service(request: Request) -> AppService:
    return request.app.state.system_app.get_component("app_service", AppService)


def get_chat_service(request: Request) -> ChatService:
    return request.app.state.chat_service


def app_to_dict(entity: AppEntity) -> dict:
    return {
        "id": entity.id,
        "name": entity.name,
        "description": entity.description,
        "type": entity.type,
        "model": entity.model,
        "published": entity.published,
        "knowledge_ids": entity.knowledge_ids or [],
        "datasource_ids": entity.datasource_ids or [],
        "skill_names": entity.skill_names or [],
    }


@router.get("")
async def list_apps(service: AppService = Depends(get_app_service)) -> dict:
    return {"items": [app_to_dict(entity) for entity in service.list()]}


@router.post("")
async def create_app(req: AppRequest, service: AppService = Depends(get_app_service)) -> dict:
    if not req.name:
        raise HTTPException(status_code=422, detail="name is required")
    return app_to_dict(service.create(**req.model_dump()))


@router.put("/{app_id}")
async def update_app(
    app_id: str, req: AppRequest, service: AppService = Depends(get_app_service)
) -> dict:
    try:
        return app_to_dict(service.update(app_id, **req.model_dump(exclude_unset=True)))
    except KeyError:
        raise HTTPException(status_code=404, detail="App not found")


@router.delete("/{app_id}")
async def delete_app(app_id: str, service: AppService = Depends(get_app_service)) -> dict:
    return {"success": service.delete(app_id)}


@router.post("/{app_id}/publish")
async def publish_app(
    app_id: str, req: PublishRequest, service: AppService = Depends(get_app_service)
) -> dict:
    try:
        return app_to_dict(service.update(app_id, published=req.published))
    except KeyError:
        raise HTTPException(status_code=404, detail="App not found")


@router.post("/{app_id}/run")
async def run_app(
    app_id: str,
    req: AppRunRequest,
    app_service: AppService = Depends(get_app_service),
    chat_service: ChatService = Depends(get_chat_service),
):
    app = app_service.get(app_id)
    if app is None:
        raise HTTPException(status_code=404, detail="App not found")

    ext_info = dict(req.ext_info or {})
    datasource_ids = app.datasource_ids or []
    ext_info.update(
        {
            "app_id": app.id,
            "app_name": app.name,
            "knowledge_ids": app.knowledge_ids or [],
            "datasource_ids": datasource_ids,
            "skill_names": app.skill_names or [],
        }
    )
    if datasource_ids and "database_name" not in ext_info:
        ext_info["database_name"] = datasource_ids[0]

    chat_req = ChatRequest(
        model=req.model or app.model or None,
        messages=req.messages,
        stream=req.stream,
        temperature=req.temperature,
        max_tokens=req.max_tokens,
        session_id=req.session_id,
        ext_info=ext_info,
    )
    if req.stream:
        return StreamingResponse(
            chat_service.chat_stream(chat_req, session_id=req.session_id),
            media_type="text/event-stream",
        )
    return await chat_service.chat(chat_req, session_id=req.session_id)
