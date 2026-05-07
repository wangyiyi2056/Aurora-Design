"""Models API endpoints for persisted model configuration and connection tests."""

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

from aurora_core.model.local_cli import detect_agents
from aurora_serve.metadata import ModelConfigEntity
from aurora_serve.models.service import ModelConfigService, mask_api_key

router = APIRouter(prefix="/models", tags=["models"])


class ModelConfigCreate(BaseModel):
    name: str
    type: str = "llm"
    base_url: str = ""
    api_key: str = ""
    is_default: bool = False


class ModelConfigUpdate(BaseModel):
    name: str | None = None
    type: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    is_default: bool | None = None
    status: str | None = None
    status_message: str | None = None


class ModelConfigResponse(BaseModel):
    id: str
    name: str
    type: str
    base_url: str
    api_key: str
    is_default: bool
    status: str
    status_message: str | None = None


class ModelConfigListResponse(BaseModel):
    items: list[ModelConfigResponse] = Field(default_factory=list)


class ModelTestRequest(BaseModel):
    base_url: str
    api_key: str
    model_type: str = "llm"


class ModelTestResponse(BaseModel):
    success: bool
    message: str
    model_info: dict | None = None


def get_model_config_service(request: Request) -> ModelConfigService:
    return request.app.state.system_app.get_component(
        "model_config_service", ModelConfigService
    )


def model_to_response(entity: ModelConfigEntity, masked: bool = True) -> ModelConfigResponse:
    return ModelConfigResponse(
        id=entity.id,
        name=entity.name,
        type=entity.type,
        base_url=entity.base_url,
        api_key=mask_api_key(entity.api_key) if masked else entity.api_key,
        is_default=entity.is_default,
        status=entity.status,
        status_message=entity.status_message,
    )


def effective_model_type(model_type: str, base_url: str) -> str:
    if "kimi.com/coding" in (base_url or ""):
        return "llm"
    return model_type


@router.get("", response_model=ModelConfigListResponse)
async def list_model_configs(
    service: ModelConfigService = Depends(get_model_config_service),
) -> ModelConfigListResponse:
    return ModelConfigListResponse(
        items=[model_to_response(entity) for entity in service.list()]
    )


@router.post("", response_model=ModelConfigResponse)
async def create_model_config(
    req: ModelConfigCreate,
    service: ModelConfigService = Depends(get_model_config_service),
) -> ModelConfigResponse:
    try:
        entity = service.create(**req.model_dump())
    except IntegrityError:
        raise HTTPException(status_code=409, detail=f"Model '{req.name}' already exists")
    return model_to_response(entity)


@router.put("/{model_id}", response_model=ModelConfigResponse)
async def update_model_config(
    model_id: str,
    req: ModelConfigUpdate,
    service: ModelConfigService = Depends(get_model_config_service),
) -> ModelConfigResponse:
    try:
        entity = service.update(model_id, **req.model_dump(exclude_unset=True))
    except KeyError:
        raise HTTPException(status_code=404, detail="Model config not found")
    return model_to_response(entity)


@router.delete("/{model_id}")
async def delete_model_config(
    model_id: str,
    service: ModelConfigService = Depends(get_model_config_service),
) -> dict:
    return {"success": service.delete(model_id)}


@router.post("/test", response_model=ModelTestResponse)
async def test_model_connection(req: ModelTestRequest):
    """Test model connection by calling the API endpoint."""
    base_url = req.base_url.rstrip("/")
    model_type = effective_model_type(req.model_type, base_url)

    if model_type in {"daemon", "cli"}:
        agents = await detect_agents()
        agent = next(
            (
                item
                for item in agents
                if item.get("id") == base_url or item.get("bin") == base_url
            ),
            None,
        )
        if agent and agent.get("available"):
            return ModelTestResponse(
                success=True,
                message="Local CLI detected",
                model_info=agent,
            )
        raise HTTPException(status_code=404, detail=f"Local CLI agent '{base_url}' not found")

    if model_type == "anthropic":
        # Anthropic-style API test
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    f"{base_url}/v1/messages",
                    json={
                        "model": "kimi-for-coding",
                        "max_tokens": 10,
                        "messages": [{"role": "user", "content": "test"}],
                    },
                    headers={
                        "x-api-key": req.api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                )
                response.raise_for_status()
                data = response.json()

                if data.get("type") == "message":
                    return ModelTestResponse(
                        success=True,
                        message="Connection successful",
                        model_info={
                            "model": data.get("model"),
                            "type": "anthropic",
                        },
                    )
                else:
                    raise HTTPException(
                        status_code=400,
                        detail="Invalid response format from Anthropic API",
                    )
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"API error: {e.response.text}",
            )
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Connection failed: {str(e)}")


    else:
        # OpenAI-style API test
        try:
            url = f"{base_url}/models" if base_url.endswith("/v1") else f"{base_url}/v1/models"
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {req.api_key}"},
                )
                response.raise_for_status()
                data = response.json()

                models = data.get("data", [])
                return ModelTestResponse(
                    success=True,
                    message="Connection successful",
                    model_info={
                        "models_count": len(models),
                        "models": [m.get("id") for m in models[:5]],
                    },
                )
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"API error: {e.response.text}",
            )
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Connection failed: {str(e)}")


@router.post("/{model_id}/test", response_model=ModelTestResponse)
async def test_saved_model_connection(
    model_id: str,
    service: ModelConfigService = Depends(get_model_config_service),
) -> ModelTestResponse:
    try:
        entity = service.get(model_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Model config not found")
    try:
        response = await test_model_connection(
            ModelTestRequest(
                base_url=entity.base_url,
                api_key=entity.api_key,
                model_type=effective_model_type(entity.type, entity.base_url),
            )
        )
    except HTTPException as exc:
        service.set_test_status(model_id, False, str(exc.detail))
        raise
    service.set_test_status(model_id, response.success, response.message)
    return response
