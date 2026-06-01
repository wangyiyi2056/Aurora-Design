from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from aurora_serve.auth.middleware import get_current_user, verify_password
from aurora_serve.auth.schema import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Response / request models
# ---------------------------------------------------------------------------


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AuthStatusResponse(BaseModel):
    enabled: bool
    authenticated: bool
    user: dict | None = None
    guest_token: str | None = None


class APIKeyCreateRequest(BaseModel):
    name: str


class APIKeyCreateResponse(BaseModel):
    key: str
    record: dict


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    request: Request = None,
):
    """Authenticate with username and password (OAuth2 password flow).

    Returns a JWT access token on success. When authentication is disabled
    the endpoint still validates that the user exists (or auto-creates one)
    so the frontend login flow remains consistent.
    """
    from aurora_serve.metadata import UserCredentialEntity, UserEntity

    jwt_handler = getattr(request.app.state, "jwt_handler", None)
    if jwt_handler is None:
        raise HTTPException(
            status_code=503,
            detail="Authentication service not initialised",
        )

    with request.app.state.metadata_store.session() as session:
        user_entity: UserEntity | None = (
            session.query(UserEntity)
            .filter_by(username=form_data.username)
            .first()
        )
        if user_entity is None or not user_entity.enabled:
            raise HTTPException(
                status_code=401,
                detail="Invalid username or password",
            )

        credential: UserCredentialEntity | None = session.get(
            UserCredentialEntity, user_entity.id
        )
        if credential is None or not verify_password(
            form_data.password, credential.password_hash
        ):
            raise HTTPException(
                status_code=401,
                detail="Invalid username or password",
            )

        token = jwt_handler.create_token(
            user_id=user_entity.id,
            username=user_entity.username,
            role=user_entity.role,
        )

    return TokenResponse(access_token=token)


@router.get("/status", response_model=AuthStatusResponse)
async def auth_status(request: Request):
    """Return authentication status and an optional guest token.

    This endpoint is always public and unauthenticated.
    """
    auth_config = getattr(request.app.state, "auth_config", None)
    jwt_handler = getattr(request.app.state, "jwt_handler", None)

    enabled = auth_config.enabled if auth_config else False

    guest_token: str | None = None
    if enabled and auth_config.guest_enabled and jwt_handler:
        guest_token = jwt_handler.create_guest_token()

    return AuthStatusResponse(
        enabled=enabled,
        authenticated=False,
        guest_token=guest_token,
    )


@router.post("/api-keys", response_model=APIKeyCreateResponse)
async def create_api_key(
    req: APIKeyCreateRequest,
    request: Request,
    user: User = Depends(get_current_user),
):
    """Create a new API key for the authenticated user."""
    api_key_manager = getattr(request.app.state, "api_key_manager", None)
    if api_key_manager is None:
        raise HTTPException(
            status_code=503,
            detail="API key service not initialised",
        )

    plaintext_key, record = await api_key_manager.create_key(
        user.user_id, req.name
    )
    return APIKeyCreateResponse(key=plaintext_key, record=record)


@router.get("/api-keys")
async def list_api_keys(
    request: Request,
    user: User = Depends(get_current_user),
):
    """List all API keys belonging to the authenticated user."""
    api_key_manager = getattr(request.app.state, "api_key_manager", None)
    if api_key_manager is None:
        raise HTTPException(
            status_code=503,
            detail="API key service not initialised",
        )

    keys = await api_key_manager.list_keys(user.user_id)
    return {"items": keys}


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(
    key_id: str,
    request: Request,
    user: User = Depends(get_current_user),
):
    """Revoke (delete) an API key by its ID."""
    api_key_manager = getattr(request.app.state, "api_key_manager", None)
    if api_key_manager is None:
        raise HTTPException(
            status_code=503,
            detail="API key service not initialised",
        )

    revoked = await api_key_manager.revoke_key(key_id)
    if not revoked:
        raise HTTPException(status_code=404, detail="API key not found")
    return {"revoked": True}
