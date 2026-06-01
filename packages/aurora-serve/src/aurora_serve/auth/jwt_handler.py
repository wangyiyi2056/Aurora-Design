from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TokenPayload:
    """Decoded JWT token payload."""

    user_id: str
    username: str
    role: str
    exp: float


class JWTHandler:
    """JWT token creation and verification."""

    def __init__(
        self,
        secret: str,
        algorithm: str = "HS256",
        expires_minutes: int = 60,
    ) -> None:
        self.secret = secret
        self.algorithm = algorithm
        self.expires_minutes = expires_minutes

    def create_token(
        self,
        user_id: str,
        username: str,
        role: str = "user",
    ) -> str:
        """Create a signed JWT token with standard claims."""
        now = datetime.now(timezone.utc)
        payload = {
            "sub": user_id,
            "username": username,
            "role": role,
            "iat": now,
            "exp": now + timedelta(minutes=self.expires_minutes),
        }
        return jwt.encode(payload, self.secret, algorithm=self.algorithm)

    def verify_token(self, token: str) -> TokenPayload | None:
        """Verify and decode a JWT token.

        Returns the decoded payload on success, or None if the token
        is invalid or expired.
        """
        try:
            decoded = jwt.decode(
                token, self.secret, algorithms=[self.algorithm]
            )
            return TokenPayload(
                user_id=decoded["sub"],
                username=decoded["username"],
                role=decoded["role"],
                exp=decoded["exp"],
            )
        except jwt.ExpiredSignatureError:
            logger.debug("Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.debug("Invalid token: %s", e)
            return None

    def create_guest_token(self) -> str:
        """Create a guest token with 24-hour expiry."""
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "guest",
            "username": "guest",
            "role": "guest",
            "iat": now,
            "exp": now + timedelta(hours=24),
        }
        return jwt.encode(payload, self.secret, algorithm=self.algorithm)
