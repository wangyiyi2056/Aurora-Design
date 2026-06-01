from __future__ import annotations

import json
import logging
import secrets
from typing import TYPE_CHECKING

from fastapi import Depends, HTTPException, Request
from starlette.types import ASGIApp, Receive, Scope, Send

from aurora_serve.auth.api_key import APIKeyManager
from aurora_serve.auth.jwt_handler import JWTHandler
from aurora_serve.auth.schema import AuthConfig, User

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)

# Paths that never require authentication.
PUBLIC_PATHS: frozenset[str] = frozenset({
    "/health",
    "/api/v1/health",
    "/api/v1/auth/login",
    "/api/v1/auth/status",
    "/docs",
    "/redoc",
    "/openapi.json",
})

_DEFAULT_ADMIN = User(
    user_id="default-admin",
    username="admin",
    role="admin",
)


def _is_public_path(path: str) -> bool:
    """Return True if the path does not require authentication."""
    if path in PUBLIC_PATHS:
        return True
    # Ollama-compatible routes live at /api/* but the main API is at
    # /api/v1/*.  Exclude /api/v1 so that protected endpoints remain
    # protected while Ollama routes stay public.
    if path.startswith("/api/") and not path.startswith("/api/v1/"):
        return True
    return False


def _extract_bearer(request: Request) -> str | None:
    """Extract a Bearer token from the Authorization header."""
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[7:]
    return None


def _extract_api_key(request: Request) -> str | None:
    """Extract an API key from the X-API-Key header."""
    return request.headers.get("X-API-Key")


async def _resolve_user(request: Request) -> User | None:
    """Try to authenticate via Bearer token or API key.

    Returns the authenticated User on success, None otherwise.
    """
    jwt_handler: JWTHandler | None = getattr(
        request.app.state, "jwt_handler", None
    )
    api_key_manager: APIKeyManager | None = getattr(
        request.app.state, "api_key_manager", None
    )

    # --- Bearer token ---
    token = _extract_bearer(request)
    if token and jwt_handler:
        payload = jwt_handler.verify_token(token)
        if payload is not None:
            return User(
                user_id=payload.user_id,
                username=payload.username,
                role=payload.role,
            )
        # Token present but invalid — reject immediately.
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # --- API key ---
    api_key = _extract_api_key(request)
    if api_key and api_key_manager:
        user = await api_key_manager.verify_key(api_key)
        if user is not None:
            return user
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
        )

    return None


async def get_current_user(request: Request) -> User:
    """FastAPI dependency — raises 401 if the caller is not authenticated.

    When authentication is disabled (``AuthConfig.enabled = False``), a
    default admin user is returned so existing deployments are unaffected.
    """
    auth_config: AuthConfig | None = getattr(
        request.app.state, "auth_config", None
    )
    if auth_config is None or not auth_config.enabled:
        return _DEFAULT_ADMIN

    if _is_public_path(request.url.path):
        return _DEFAULT_ADMIN

    user = await _resolve_user(request)
    if user is not None:
        return user

    raise HTTPException(
        status_code=401,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def optional_auth(request: Request) -> User:
    """FastAPI dependency — returns a guest user when not authenticated.

    Useful for endpoints that behave differently for authenticated users
    but still accept anonymous access.
    """
    auth_config: AuthConfig | None = getattr(
        request.app.state, "auth_config", None
    )
    if auth_config is None or not auth_config.enabled:
        return _DEFAULT_ADMIN

    if _is_public_path(request.url.path):
        return _DEFAULT_ADMIN

    user = await _resolve_user(request)
    if user is not None:
        return user

    return User(
        user_id="guest",
        username="guest",
        role="guest",
        is_authenticated=False,
    )


async def require_admin(
    user: User = Depends(get_current_user),
) -> User:
    """FastAPI dependency — raises 403 if the user is not an admin."""
    if user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin access required",
        )
    return user


# ---------------------------------------------------------------------------
# ASGI middleware — enforces auth globally on all non-public paths
# ---------------------------------------------------------------------------


class AuthMiddleware:
    """ASGI middleware that enforces authentication on every request.

    When ``AuthConfig.enabled`` is False the middleware is a transparent
    pass-through, preserving backward compatibility for existing deployments.

    Register with ``app.add_middleware(AuthMiddleware, aurora_app=app)``
    so the middleware can access ``app.state`` directly.
    """

    def __init__(self, app: ASGIApp, aurora_app=None) -> None:
        self.app = app
        self._aurora_app = aurora_app

    def _get_app_state(self):
        """Return the FastAPI app state, or None if unavailable."""
        if self._aurora_app is not None:
            return getattr(self._aurora_app, "state", None)
        # Fallback: walk the middleware chain.
        current = self.app
        visited: set[int] = set()
        while current is not None and id(current) not in visited:
            visited.add(id(current))
            state = getattr(current, "state", None)
            if state is not None:
                return state
            current = getattr(current, "app", None)
        return None

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        path: str = scope.get("path", "")
        headers = {
            k.decode().lower(): v.decode()
            for k, v in scope.get("headers", [])
        }

        # CORS preflight — always allow.
        if scope["type"] == "http" and scope.get("method") == "OPTIONS":
            await self.app(scope, receive, send)
            return

        # Public paths never require auth.
        if _is_public_path(path):
            await self.app(scope, receive, send)
            return

        # Retrieve auth config from app.state (set by _init_auth).
        app_state = self._get_app_state()
        auth_config: AuthConfig | None = (
            getattr(app_state, "auth_config", None) if app_state else None
        )

        if auth_config is None or not auth_config.enabled:
            await self.app(scope, receive, send)
            return

        # --- Try Bearer token ---
        auth_header = headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            jwt_handler: JWTHandler | None = (
                getattr(app_state, "jwt_handler", None)
                if app_state
                else None
            )
            if jwt_handler:
                payload = jwt_handler.verify_token(token)
                if payload is not None:
                    await self.app(scope, receive, send)
                    return

            await self._send_401(send, "Invalid or expired token")
            return

        # --- Try API key ---
        api_key = headers.get("x-api-key")
        if api_key:
            api_key_manager: APIKeyManager | None = (
                getattr(app_state, "api_key_manager", None)
                if app_state
                else None
            )
            if api_key_manager:
                user = await api_key_manager.verify_key(api_key)
                if user is not None:
                    await self.app(scope, receive, send)
                    return

            await self._send_401(send, "Invalid API key")
            return

        # No credentials supplied.
        await self._send_401(send, "Authentication required")

    @staticmethod
    async def _send_401(send: Send, detail: str) -> None:
        body = json.dumps({"detail": detail}).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                    (b"www-authenticate", b"Bearer"),
                ],
            }
        )
        await send(
            {"type": "http.response.body", "body": body}
        )


# ---------------------------------------------------------------------------
# Server initialisation
# ---------------------------------------------------------------------------


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    import bcrypt

    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against a bcrypt hash."""
    import bcrypt

    return bcrypt.checkpw(password.encode(), hashed.encode())


def _init_auth(app: FastAPI) -> None:
    """Initialise authentication subsystem during app lifespan startup.

    Reads configuration from environment variables, creates JWT and API key
    handlers, and seeds a default admin user when no users exist yet.
    """
    import os

    from aurora_serve.metadata import UserCredentialEntity, UserEntity

    enabled = os.getenv("AURORA_AUTH_ENABLED", "false").lower() in (
        "true",
        "1",
        "yes",
    )
    secret = os.getenv("AURORA_JWT_SECRET", "")
    algorithm = os.getenv("AURORA_JWT_ALGORITHM", "HS256")
    expires = int(os.getenv("AURORA_JWT_EXPIRES_MINUTES", "60"))
    guest_enabled = os.getenv("AURORA_GUEST_ENABLED", "true").lower() in (
        "true",
        "1",
        "yes",
    )

    # Always ensure a secret exists so JWT creation never fails.
    if not secret:
        secret = secrets.token_urlsafe(48)
        logger.warning(
            "AURORA_JWT_SECRET not set — generated ephemeral secret. "
            "Tokens will not survive restarts. "
            "Set AURORA_JWT_SECRET for production use."
        )

    auth_config = AuthConfig(
        jwt_secret=secret,
        jwt_algorithm=algorithm,
        jwt_expires_minutes=expires,
        guest_enabled=guest_enabled,
        enabled=enabled,
    )
    app.state.auth_config = auth_config

    jwt_handler = JWTHandler(
        secret=secret,
        algorithm=algorithm,
        expires_minutes=expires,
    )
    app.state.jwt_handler = jwt_handler

    metadata_store = app.state.metadata_store
    api_key_manager = APIKeyManager(metadata_store)
    app.state.api_key_manager = api_key_manager

    # Seed a default admin user when the users table is empty.
    with metadata_store.session() as session:
        user_count = session.query(UserEntity).count()
        if user_count == 0:
            from uuid import uuid4

            admin_password = os.getenv("AURORA_ADMIN_PASSWORD", "admin")
            admin_id = str(uuid4())

            admin_user = UserEntity(
                id=admin_id,
                username="admin",
                display_name="Administrator",
                role="admin",
                enabled=True,
            )
            credential = UserCredentialEntity(
                user_id=admin_id,
                password_hash=hash_password(admin_password),
            )
            session.add(admin_user)
            session.add(credential)
            session.commit()
            logger.info(
                "Created default admin user (username: admin). "
                "Set AURORA_ADMIN_PASSWORD to customise the password."
            )

    logger.info(
        "Auth initialised: enabled=%s, guest=%s", enabled, guest_enabled
    )
