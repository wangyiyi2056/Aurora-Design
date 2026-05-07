from __future__ import annotations

import hashlib
import os
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from aurora_core.component import BaseService
from aurora_serve.metadata import FileEntity, MetadataStore, storage_dir


class FileService(BaseService):
    name = "file_service"

    def __init__(self, metadata_store: MetadataStore):
        self.metadata_store = metadata_store
        self.upload_dir = storage_dir() / "uploads" / "files"
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def upload(self, file: UploadFile, purpose: str = "general") -> FileEntity:
        content = await file.read()
        ext = Path(file.filename or "").suffix or ".bin"
        file_id = str(uuid4())
        stored_name = f"{file_id}{ext}"
        file_path = self.upload_dir / stored_name
        file_path.write_bytes(content)

        entity = FileEntity(
            id=file_id,
            file_name=file.filename or stored_name,
            file_path=str(file_path),
            content_type=file.content_type or "application/octet-stream",
            size=len(content),
            purpose=purpose,
            sha256=hashlib.sha256(content).hexdigest(),
        )
        with self.metadata_store.session() as session:
            session.add(entity)
            session.commit()
            return entity

    def list(self) -> list[FileEntity]:
        with self.metadata_store.session() as session:
            return list(session.query(FileEntity).order_by(FileEntity.created_at.desc()).all())

    def get(self, file_id: str) -> FileEntity:
        with self.metadata_store.session() as session:
            entity = session.get(FileEntity, file_id)
            if entity is None:
                raise KeyError(file_id)
            return entity

    def delete(self, file_id: str) -> bool:
        with self.metadata_store.session() as session:
            entity = session.get(FileEntity, file_id)
            if entity is None:
                return False
            file_path = Path(entity.file_path)
            session.delete(entity)
            session.commit()
        if file_path.exists():
            os.remove(file_path)
        return True
