from __future__ import annotations

import os
import re
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from chatbi_core.component import BaseService
from chatbi_core.model.registry import ModelRegistry
from chatbi_ext.rag import (
    ChunkManager,
    ChunkParameters,
    EmbeddingAssembler,
    KnowledgeFactory,
)
from chatbi_ext.rag.retriever.embedding_retriever import EmbeddingRetriever
from chatbi_ext.storage import ChromaVectorStore
from chatbi_serve.metadata import (
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

    async def upload(self, name: str, file: UploadFile) -> dict[str, object]:
        suffix = os.path.splitext(file.filename or "")[1] or ".txt"
        stored_name = f"{uuid4()}{suffix}"
        file_path = self.upload_dir / stored_name
        file_path.write_bytes(await file.read())

        collection_name = self._collection_name(name)
        knowledge = KnowledgeFactory.from_file_path(str(file_path))
        chunk_manager = ChunkManager(ChunkParameters(chunk_size=500, chunk_overlap=50))
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
                )
                session.add(entity)
            entity.chunk_count = (entity.chunk_count or 0) + len(ids)
            doc = KnowledgeDocumentEntity(
                id=str(uuid4()),
                knowledge_name=name,
                file_name=file.filename or stored_name,
                file_path=str(file_path),
                chunk_count=len(ids),
            )
            session.add(doc)
            session.commit()
        return {"name": name, "chunks": len(ids)}

    async def query(self, name: str, query: str) -> dict[str, object]:
        retriever = self._retrievers.get(name) or self._restore_retriever(name)
        if retriever is None:
            return {"error": f"Knowledge base '{name}' not found"}
        docs = await retriever.retrieve(query)
        return {"results": [{"content": d.content, "metadata": d.metadata} for d in docs]}

    def _restore_retriever(self, name: str):
        with self.metadata_store.session() as session:
            entity = session.get(KnowledgeBaseEntity, name)
            if entity is None:
                return None
            vector_store = ChromaVectorStore(
                collection_name=entity.collection_name,
                persist_directory=entity.persist_directory,
            )
        embeddings = self.registry.get_embeddings()
        retriever = EmbeddingRetriever(vector_store=vector_store, embeddings=embeddings, top_k=5)
        self._retrievers[name] = retriever
        return retriever

    def _collection_name(self, name: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9_-]", "-", name).strip("-_")
        if len(cleaned) < 3:
            cleaned = f"kb-{cleaned or 'default'}"
        return cleaned[:50]
