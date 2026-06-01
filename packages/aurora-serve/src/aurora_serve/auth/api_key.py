from __future__ import annotations

import hashlib
import logging
import secrets
import time
from typing import TYPE_CHECKING
from uuid import uuid4

from aurora_serve.auth.schema import User

if TYPE_CHECKING:
    from aurora_serve.metadata import MetadataStore

logger = logging.getLogger(__name__)


def _hash_key(key: str) -> str:
    """SHA-256 hash of an API key."""
    return hashlib.sha256(key.encode()).hexdigest()


class APIKeyManager:
    """Manages API key lifecycle: creation, verification, listing, revocation.

    Keys are stored as SHA-256 hashes in the metadata database. The plaintext
    key is returned only once at creation time and cannot be recovered later.
    """

    def __init__(self, metadata_store: MetadataStore) -> None:
        self._store = metadata_store

    async def create_key(
        self, user_id: str, name: str
    ) -> tuple[str, dict]:
        """Create a new API key.

        Returns:
            Tuple of (plaintext_key, key_record_dict). The plaintext key
            is only available at creation time.
        """
        from aurora_serve.metadata import APIKeyEntity

        key_id = str(uuid4())
        raw_key = f"aurora_{secrets.token_hex(32)}"
        key_hash = _hash_key(raw_key)

        record = APIKeyEntity(
            id=key_id,
            name=name,
            user_id=user_id,
            key_hash=key_hash,
            last_used_at=None,
        )

        with self._store.session() as session:
            session.add(record)
            session.commit()

        logger.info("API key '%s' created for user %s", name, user_id)
        return raw_key, self._entity_to_dict(record)

    async def verify_key(self, key: str) -> User | None:
        """Verify an API key and return the associated user.

        Updates the last_used_at timestamp on successful verification.
        Returns None if the key is invalid or revoked.
        """
        from aurora_serve.metadata import APIKeyEntity

        key_hash = _hash_key(key)

        with self._store.session() as session:
            record = (
                session.query(APIKeyEntity)
                .filter_by(key_hash=key_hash)
                .first()
            )
            if record is None:
                return None

            record.last_used_at = time.time()
            session.commit()

            return User(
                user_id=record.user_id,
                username=record.name,
                role="user",
            )

    async def list_keys(self, user_id: str) -> list[dict]:
        """List all API keys for a user (hashes only, never plaintext)."""
        from aurora_serve.metadata import APIKeyEntity

        with self._store.session() as session:
            records = (
                session.query(APIKeyEntity)
                .filter_by(user_id=user_id)
                .all()
            )
            return [self._entity_to_dict(r) for r in records]

    async def revoke_key(self, key_id: str) -> bool:
        """Revoke an API key by its ID. Returns True if the key was found."""
        from aurora_serve.metadata import APIKeyEntity

        with self._store.session() as session:
            record = session.get(APIKeyEntity, key_id)
            if record is None:
                return False
            session.delete(record)
            session.commit()

        logger.info("API key %s revoked", key_id)
        return True

    @staticmethod
    def _entity_to_dict(record) -> dict:
        return {
            "id": record.id,
            "name": record.name,
            "user_id": record.user_id,
            "created_at": record.created_at,
            "last_used_at": record.last_used_at,
        }
