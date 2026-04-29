from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from sqlalchemy import JSON, Boolean, Float, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from chatbi_core.component import BaseComponent


def metadata_db_path() -> Path:
    configured = os.getenv("CHATBI_METADATA_DB")
    if configured:
        return Path(configured)
    return Path("data") / "chatbi.db"


def storage_dir() -> Path:
    configured = os.getenv("CHATBI_STORAGE_DIR")
    if configured:
        return Path(configured)
    return Path("data")


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[float] = mapped_column(Float, default=lambda: time.time())
    updated_at: Mapped[float] = mapped_column(
        Float, default=lambda: time.time(), onupdate=lambda: time.time()
    )


class ModelConfigEntity(TimestampMixin, Base):
    __tablename__ = "model_configs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    type: Mapped[str] = mapped_column(String(64), default="llm")
    base_url: Mapped[str] = mapped_column(String(1024), default="")
    api_key: Mapped[str] = mapped_column(String(4096), default="")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(64), default="untested")
    status_message: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    extra: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class DatasourceEntity(TimestampMixin, Base):
    __tablename__ = "datasources"

    name: Mapped[str] = mapped_column(String(255), primary_key=True)
    db_type: Mapped[str] = mapped_column(String(64))
    host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    port: Mapped[int | None] = mapped_column(nullable=True)
    user: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    database: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    extra: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class KnowledgeBaseEntity(TimestampMixin, Base):
    __tablename__ = "knowledge_bases"

    name: Mapped[str] = mapped_column(String(255), primary_key=True)
    collection_name: Mapped[str] = mapped_column(String(255), unique=True)
    persist_directory: Mapped[str] = mapped_column(String(1024))
    chunk_count: Mapped[int] = mapped_column(default=0)


class KnowledgeDocumentEntity(TimestampMixin, Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    knowledge_name: Mapped[str] = mapped_column(String(255), index=True)
    file_name: Mapped[str] = mapped_column(String(1024))
    file_path: Mapped[str] = mapped_column(String(1024))
    chunk_count: Mapped[int] = mapped_column(default=0)


class AppEntity(TimestampMixin, Base):
    __tablename__ = "apps"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str] = mapped_column(String(2048), default="")
    type: Mapped[str] = mapped_column(String(64), default="chat")
    model: Mapped[str] = mapped_column(String(255), default="")
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    knowledge_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    datasource_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    skill_names: Mapped[list[str]] = mapped_column(JSON, default=list)


class MetadataStore(BaseComponent):
    name = "metadata_store"

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or metadata_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{self.db_path}", future=True)
        self.session_factory = sessionmaker(
            bind=self.engine, expire_on_commit=False, class_=Session
        )
        Base.metadata.create_all(self.engine)

    def session(self) -> Session:
        return self.session_factory()
