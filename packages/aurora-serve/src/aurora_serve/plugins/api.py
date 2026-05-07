from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from aurora_serve.metadata import PluginEntity
from aurora_serve.plugins.service import PluginService

router = APIRouter(prefix="/plugins", tags=["plugins"])


class PluginRequest(BaseModel):
    name: str
    description: str = ""
    entrypoint: str = ""
    enabled: bool = False
    config: dict = Field(default_factory=dict)


class PluginUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    entrypoint: str | None = None
    enabled: bool | None = None
    config: dict | None = None


class PluginEnableRequest(BaseModel):
    enabled: bool = True


def get_plugin_service(request: Request) -> PluginService:
    return request.app.state.system_app.get_component("plugin_service", PluginService)


def plugin_to_dict(entity: PluginEntity) -> dict:
    return {
        "id": entity.id,
        "name": entity.name,
        "description": entity.description,
        "entrypoint": entity.entrypoint,
        "enabled": entity.enabled,
        "config": entity.config or {},
        "created_at": entity.created_at,
        "updated_at": entity.updated_at,
    }


@router.get("")
async def list_plugins(service: PluginService = Depends(get_plugin_service)) -> dict:
    return {"items": [plugin_to_dict(item) for item in service.list()]}


@router.post("")
async def create_plugin(
    req: PluginRequest,
    service: PluginService = Depends(get_plugin_service),
) -> dict:
    return plugin_to_dict(service.create(**req.model_dump()))


@router.get("/{plugin_id}")
async def get_plugin(
    plugin_id: str,
    service: PluginService = Depends(get_plugin_service),
) -> dict:
    try:
        return plugin_to_dict(service.get(plugin_id))
    except KeyError:
        raise HTTPException(status_code=404, detail="Plugin not found")


@router.put("/{plugin_id}")
async def update_plugin(
    plugin_id: str,
    req: PluginUpdateRequest,
    service: PluginService = Depends(get_plugin_service),
) -> dict:
    try:
        return plugin_to_dict(service.update(plugin_id, **req.model_dump(exclude_unset=True)))
    except KeyError:
        raise HTTPException(status_code=404, detail="Plugin not found")


@router.post("/{plugin_id}/enable")
async def enable_plugin(
    plugin_id: str,
    req: PluginEnableRequest,
    service: PluginService = Depends(get_plugin_service),
) -> dict:
    try:
        return plugin_to_dict(service.update(plugin_id, enabled=req.enabled))
    except KeyError:
        raise HTTPException(status_code=404, detail="Plugin not found")


@router.post("/{plugin_id}/disable")
async def disable_plugin(
    plugin_id: str,
    service: PluginService = Depends(get_plugin_service),
) -> dict:
    try:
        return plugin_to_dict(service.update(plugin_id, enabled=False))
    except KeyError:
        raise HTTPException(status_code=404, detail="Plugin not found")


@router.delete("/{plugin_id}")
async def delete_plugin(
    plugin_id: str,
    service: PluginService = Depends(get_plugin_service),
) -> dict:
    return {"success": service.delete(plugin_id)}
