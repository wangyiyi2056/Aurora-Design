from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from sqlalchemy import JSON, Boolean, Float, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from aurora_core.component import BaseComponent


def metadata_db_path() -> Path:
    configured = os.getenv("AURORA_METADATA_DB")
    if configured:
        return Path(configured)
    return Path("data") / "aurora.db"


def storage_dir() -> Path:
    configured = os.getenv("AURORA_STORAGE_DIR")
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
    chunk_strategy: Mapped[str] = mapped_column(String(64), default="fixed")
    chunk_size: Mapped[int] = mapped_column(default=500)
    chunk_overlap: Mapped[int] = mapped_column(default=50)


class KnowledgeDocumentEntity(TimestampMixin, Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    knowledge_name: Mapped[str] = mapped_column(String(255), index=True)
    file_name: Mapped[str] = mapped_column(String(1024))
    file_path: Mapped[str] = mapped_column(String(1024))
    chunk_count: Mapped[int] = mapped_column(default=0)


class FileEntity(TimestampMixin, Base):
    __tablename__ = "files"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    file_name: Mapped[str] = mapped_column(String(1024))
    file_path: Mapped[str] = mapped_column(String(2048))
    content_type: Mapped[str] = mapped_column(String(255), default="application/octet-stream")
    size: Mapped[int] = mapped_column(default=0)
    purpose: Mapped[str] = mapped_column(String(64), default="general")
    owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sha256: Mapped[str] = mapped_column(String(64), default="")
    extra: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class PromptTemplateEntity(TimestampMixin, Base):
    __tablename__ = "prompt_templates"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    category: Mapped[str] = mapped_column(String(128), default="general", index=True)
    template: Mapped[str] = mapped_column(String)
    variables: Mapped[list[str]] = mapped_column(JSON, default=list)
    version: Mapped[int] = mapped_column(default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[str] = mapped_column(String(2048), default="")
    extra: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class FlowEntity(TimestampMixin, Base):
    __tablename__ = "flows"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str] = mapped_column(String(2048), default="")
    nodes: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    edges: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    variables: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class FlowRunEntity(TimestampMixin, Base):
    __tablename__ = "flow_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    flow_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(64), default="completed")
    input: Mapped[Any] = mapped_column(JSON, nullable=True)
    output: Mapped[Any] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(String(2048), nullable=True)


class PluginEntity(TimestampMixin, Base):
    __tablename__ = "plugins"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str] = mapped_column(String(2048), default="")
    entrypoint: Mapped[str] = mapped_column(String(1024), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class EvaluationDatasetEntity(TimestampMixin, Base):
    __tablename__ = "evaluation_datasets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str] = mapped_column(String(2048), default="")
    data: Mapped[Any] = mapped_column(JSON, nullable=True)


class EvaluationTaskEntity(TimestampMixin, Base):
    __tablename__ = "evaluation_tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    model: Mapped[str] = mapped_column(String(255), default="")
    dataset_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(64), default="pending")
    result: Mapped[Any] = mapped_column(JSON, nullable=True)


class FeedbackEntity(TimestampMixin, Base):
    __tablename__ = "feedback"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    target_type: Mapped[str] = mapped_column(String(128), index=True)
    target_id: Mapped[str] = mapped_column(String(255), index=True)
    rating: Mapped[int] = mapped_column(default=0)
    comment: Mapped[str] = mapped_column(String(4096), default="")
    extra: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class TraceEventEntity(TimestampMixin, Base):
    __tablename__ = "trace_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    span_type: Mapped[str] = mapped_column(String(128), default="event")
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)


class UserEntity(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    username: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255), default="")
    role: Mapped[str] = mapped_column(String(64), default="admin")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


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
