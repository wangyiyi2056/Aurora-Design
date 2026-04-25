"""Models API endpoint for testing model connections."""

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/models", tags=["models"])


class ModelTestRequest(BaseModel):
    base_url: str
    api_key: str
    model_type: str = "llm"


class ModelTestResponse(BaseModel):
    success: bool
    message: str
    model_info: dict | None = None


@router.post("/test", response_model=ModelTestResponse)
async def test_model_connection(req: ModelTestRequest):
    """Test model connection by calling the API endpoint."""
    base_url = req.base_url.rstrip("/")

    if req.model_type == "anthropic":
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