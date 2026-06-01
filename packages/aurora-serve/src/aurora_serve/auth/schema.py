from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    """Authenticated user identity."""

    user_id: str
    username: str
    role: str = "user"  # "admin" | "user" | "guest"
    is_authenticated: bool = True


@dataclass(frozen=True)
class AuthConfig:
    """Authentication configuration.

    Auth is disabled by default for backward compatibility with existing
    deployments that do not require authentication.
    """

    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60
    api_key_header: str = "X-API-Key"
    guest_enabled: bool = True
    enabled: bool = False
