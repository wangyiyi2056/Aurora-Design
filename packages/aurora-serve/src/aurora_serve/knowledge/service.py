from __future__ import annotations

import os
import re
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from aurora_core.component import BaseService
from aurora_core.model.registry import ModelRegistry
from aurora_ext.rag import (
    ChunkManager,
    ChunkParameters,
    EmbeddingAssembler,
    KnowledgeFactory,
)
from aurora_ext.rag.retriever.embedding_retriever import EmbeddingRetriever
from aurora_ext.storage import ChromaVectorStore
from aurora_serve.metadata import (
    KnowledgeBaseEntity,
    KnowledgeDocumentEntity,
    MetadataStore,
    storage_dir,
)


class KnowledgeService(BaseService):
    name = "knowledge_service"

    def __init__(self, metadata_store: MetadataStore, registry: ModelRegistry):
        self.metadata_store = metadata_store
        self.registry = registry
        self._retrievers: dict[str, object] = {}
        base_dir = storage_dir()
        self.upload_dir = base_dir / "uploads" / "knowledge"
        self.chroma_dir = base_dir / "chroma"
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_dir.mkdir(parents=True, exist_ok=True)

    def list_names(self) -> list[str]:
        with self.metadata_store.session() as session:
            rows = session.query(KnowledgeBaseEntity).order_by(KnowledgeBaseEntity.created_at).all()
            return [row.name for row in rows]

    async def upload(
        self,
        name: str,
        file: UploadFile,
        chunk_strategy: str = "fixed",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ) -> dict[str, object]:
        suffix = os.path.splitext(file.filename or "")[1] or ".txt"
        stored_name = f"{uuid4()}{suffix}"
        file_path = self.upload_dir / stored_name
        file_path.write_bytes(await file.read())

        collection_name = self._collection_name(name)
        knowledge = KnowledgeFactory.from_file_path(str(file_path))
        chunk_size = max(1, chunk_size)
        chunk_overlap = max(0, min(chunk_overlap, chunk_size - 1))
        chunk_manager = ChunkManager(
            ChunkParameters(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        )
        embeddings = self.registry.get_embeddings()
        vector_store = ChromaVectorStore(
            collection_name=collection_name,
            persist_directory=str(self.chroma_dir),
        )
        assembler = EmbeddingAssembler(
            knowledge=knowledge,
            chunk_manager=chunk_manager,
            embeddings=embeddings,
            vector_store=vector_store,
        )
        ids = assembler.persist()
        self._retrievers[name] = assembler.as_retriever(top_k=5)

        with self.metadata_store.session() as session:
            entity = session.get(KnowledgeBaseEntity, name)
            if entity is None:
                entity = KnowledgeBaseEntity(
                    name=name,
                    collection_name=collection_name,
                    persist_directory=str(self.chroma_dir),
                    chunk_count=0,
                    chunk_strategy=chunk_strategy,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                )
                session.add(entity)
            entity.chunk_count = (entity.chunk_count or 0) + len(ids)
            entity.chunk_strategy = chunk_strategy
            entity.chunk_size = chunk_size
            entity.chunk_overlap = chunk_overlap
            doc = KnowledgeDocumentEntity(
                id=str(uuid4()),
                knowledge_name=name,
                file_name=file.filename or stored_name,
                file_path=str(file_path),
                chunk_count=len(ids),
            )
            session.add(doc)
            session.commit()
        return {
            "name": name,
            "chunks": len(ids),
            "chunk_strategy": chunk_strategy,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
        }

    def detail(self, name: str) -> dict[str, object] | None:
        with self.metadata_store.session() as session:
            entity = session.get(KnowledgeBaseEntity, name)
            if entity is None:
                return None
            return {
                "name": entity.name,
                "collection_name": entity.collection_name,
                "persist_directory": entity.persist_directory,
                "chunks": entity.chunk_count,
                "chunk_strategy": entity.chunk_strategy,
                "chunk_size": entity.chunk_size,
                "chunk_overlap": entity.chunk_overlap,
            }

    def list_documents(self, name: str) -> list[dict[str, object]]:
        with self.metadata_store.session() as session:
            docs = (
                session.query(KnowledgeDocumentEntity)
                .filter_by(knowledge_name=name)
                .order_by(KnowledgeDocumentEntity.created_at.desc())
                .all()
            )
            return [
                {
                    "id": doc.id,
                    "knowledge_name": doc.knowledge_name,
                    "file_name": doc.file_name,
                    "file_path": doc.file_path,
                    "chunks": doc.chunk_count,
                    "created_at": doc.created_at,
                    "updated_at": doc.updated_at,
                }
                for doc in docs
            ]

    async def query(self, name: str, query: str, top_k: int = 5) -> dict[str, object]:
        retriever = self._retrievers.get(name) or self._restore_retriever(name, top_k=top_k)
        if retriever is None:
            return {"error": f"Knowledge base '{name}' not found"}
        if hasattr(retriever, "top_k"):
            retriever.top_k = top_k
        docs = await retriever.retrieve(query)
        return {"results": [{"content": d.content, "metadata": d.metadata} for d in docs]}

    def delete_document(self, name: str, document_id: str) -> bool:
        with self.metadata_store.session() as session:
            doc = session.get(KnowledgeDocumentEntity, document_id)
            if doc is None or doc.knowledge_name != name:
                return False
            file_path = Path(doc.file_path)
            session.delete(doc)
            kb = session.get(KnowledgeBaseEntity, name)
            if kb is not None:
                kb.chunk_count = max(0, (kb.chunk_count or 0) - (doc.chunk_count or 0))
            session.commit()
        if file_path.exists():
            file_path.unlink()
        self._retrievers.pop(name, None)
        return True

    def delete_knowledge_base(self, name: str) -> bool:
        with self.metadata_store.session() as session:
            kb = session.get(KnowledgeBaseEntity, name)
            if kb is None:
                return False
            docs = session.query(KnowledgeDocumentEntity).filter_by(knowledge_name=name).all()
            file_paths = [Path(doc.file_path) for doc in docs]
            for doc in docs:
                session.delete(doc)
            session.delete(kb)
            session.commit()
        for file_path in file_paths:
            if file_path.exists():
                file_path.unlink()
        self._retrievers.pop(name, None)
        return True

    def _restore_retriever(self, name: str, top_k: int = 5):
        with self.metadata_store.session() as session:
            entity = session.get(KnowledgeBaseEntity, name)
            if entity is None:
                return None
            vector_store = ChromaVectorStore(
                collection_name=entity.collection_name,
                persist_directory=entity.persist_directory,
            )
        embeddings = self.registry.get_embeddings()
        retriever = EmbeddingRetriever(vector_store=vector_store, embeddings=embeddings, top_k=top_k)
        self._retrievers[name] = retriever
        return retriever

    def _collection_name(self, name: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9_-]", "-", name).strip("-_")
        if len(cleaned) < 3:
            cleaned = f"kb-{cleaned or 'default'}"
        return cleaned[:50]
