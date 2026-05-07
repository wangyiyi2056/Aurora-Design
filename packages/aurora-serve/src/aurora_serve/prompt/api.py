from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from aurora_serve.metadata import PromptTemplateEntity
from aurora_serve.prompt.service import PromptTemplateService

router = APIRouter(prefix="/prompts", tags=["prompts"])


class PromptTemplateCreate(BaseModel):
    name: str
    category: str = "general"
    template: str
    variables: list[str] = Field(default_factory=list)
    version: int = 1
    enabled: bool = True
    description: str = ""


class PromptTemplateUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    template: str | None = None
    variables: list[str] | None = None
    version: int | None = None
    enabled: bool | None = None
    description: str | None = None


class PromptRenderRequest(BaseModel):
    variables: dict[str, object] = Field(default_factory=dict)


def get_prompt_service(request: Request) -> PromptTemplateService:
    return request.app.state.system_app.get_component(
        "prompt_template_service", PromptTemplateService
    )


def prompt_to_dict(entity: PromptTemplateEntity) -> dict:
    return {
        "id": entity.id,
        "name": entity.name,
        "category": entity.category,
        "template": entity.template,
        "variables": entity.variables or [],
        "version": entity.version,
        "enabled": entity.enabled,
        "description": entity.description,
        "created_at": entity.created_at,
        "updated_at": entity.updated_at,
    }


@router.get("")
async def list_prompts(
    category: str | None = None,
    service: PromptTemplateService = Depends(get_prompt_service),
) -> dict:
    return {"items": [prompt_to_dict(item) for item in service.list(category=category)]}


@router.post("")
async def create_prompt(
    req: PromptTemplateCreate,
    service: PromptTemplateService = Depends(get_prompt_service),
) -> dict:
    return prompt_to_dict(service.create(**req.model_dump()))


@router.get("/{prompt_id}")
async def get_prompt(
    prompt_id: str,
    service: PromptTemplateService = Depends(get_prompt_service),
) -> dict:
    try:
        return prompt_to_dict(service.get(prompt_id))
    except KeyError:
        raise HTTPException(status_code=404, detail="Prompt not found")


@router.put("/{prompt_id}")
async def update_prompt(
    prompt_id: str,
    req: PromptTemplateUpdate,
    service: PromptTemplateService = Depends(get_prompt_service),
) -> dict:
    try:
        return prompt_to_dict(service.update(prompt_id, **req.model_dump(exclude_unset=True)))
    except KeyError:
        raise HTTPException(status_code=404, detail="Prompt not found")


@router.delete("/{prompt_id}")
async def delete_prompt(
    prompt_id: str,
    service: PromptTemplateService = Depends(get_prompt_service),
) -> dict:
    return {"success": service.delete(prompt_id)}


@router.post("/{prompt_id}/render")
async def render_prompt(
    prompt_id: str,
    req: PromptRenderRequest,
    service: PromptTemplateService = Depends(get_prompt_service),
) -> dict:
    try:
        return {"content": service.render(prompt_id, req.variables)}
    except KeyError:
        raise HTTPException(status_code=404, detail="Prompt not found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
