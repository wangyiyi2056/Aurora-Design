"""ChromaDB-backed vector storage.

Migrated from LightRAG vector storage interface, adapting Aurora's
existing ``ChromaVectorStore`` to the new ``BaseVectorStorage`` contract.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from aurora_ext.rag.storage.base import BaseVectorStorage
from aurora_ext.rag.storage.workspace import get_workspace_manager

logger = logging.getLogger(__name__)


class ChromaVectorStorage(BaseVectorStorage):
    """ChromaDB persistent vector storage.

    Supports workspace isolation: when a ``WorkspaceManager`` is present
    in ``global_config``, the ChromaDB collection name is prefixed with
    the workspace ID — ``{workspace_id}_{namespace}`` — to isolate
    vector data per tenant.
    """

    def __init__(self, namespace: str, global_config: dict[str, Any]) -> None:
        super().__init__(namespace, global_config)
        working_dir = global_config.get("working_dir", "./rag_storage")
        wm = get_workspace_manager(global_config)
        self._workspace_manager = wm
        persist_dir = os.path.join(working_dir, "chroma")
        self._embedding_func = global_config.get("embedding_func")
        self._collection_name = wm.get_collection_name(namespace)

        import chromadb

        self._client = chromadb.PersistentClient(path=persist_dir)
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    # ── BaseVectorStorage interface ──────────────────────────────

    async def upsert(self, data: dict[str, dict[str, Any]]) -> None:
        if not data:
            return

        ids = list(data.keys())
        documents: list[str] = []
        metadatas: list[dict[str, Any]] = []
        embeddings: list[list[float]] = []

        for key, record in data.items():
            content = record.get("content", "")
            vector = record.get("__vector__")
            meta = {k: v for k, v in record.items(
            ) if k not in ("content", "__vector__")}
            documents.append(content)
            metadatas.append(meta)
            if vector is not None:
                embeddings.append(vector)

        add_kwargs: dict[str, Any] = {
            "ids": ids,
            "documents": documents,
            "metadatas": metadatas,
        }
        if embeddings:
            add_kwargs["embeddings"] = embeddings

        self._collection.upsert(**add_kwargs)

    async def query(
        self,
        query_text: str,
        top_k: int,
        cosine_threshold: float = 0.0,
        where: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        query_embedding = None
        has_embed = self._embedding_func is not None
        if has_embed:
            try:
                vec = await self._embedding_func([query_text], is_query=True)
                query_embedding = vec[0].tolist()
                logger.debug(
                    "[chroma_query] Embedding OK dim=%d collection=%s",
                    len(query_embedding), self._collection_name,
                )
            except Exception as exc:
                logger.error(
                    "[chroma_query] EMBEDDING FAILED for collection=%s: %s. "
                    "Will fall back to ChromaDB default embedding (may cause "
                    "dimension mismatch). Check Ollama is running.",
                    self._collection_name, exc,
                )
                has_embed = False

        kwargs: dict[str, Any] = {"n_results": top_k}
        if where:
            kwargs["where"] = where
        if query_embedding is not None:
            kwargs["query_embeddings"] = [query_embedding]
        else:
            logger.warning(
                "[chroma_query] No embedding func! Using ChromaDB default "
                "embedding for collection=%s where=%s. Stored vectors may have "
                "different dimensions.",
                self._collection_name, where,
            )
            kwargs["query_texts"] = [query_text]

        try:
            results = self._collection.query(**kwargs)
        except Exception as exc:
            logger.error(
                "[chroma_query] ChromaDB query FAILED collection=%s where=%s: %s",
                self._collection_name, where, exc,
            )
            return []

        out: list[dict[str, Any]] = []
        if results and results["ids"]:
            for i, doc_id in enumerate(results["ids"][0]):
                score = 1.0
                if results.get("distances") and results["distances"][0]:
                    distance = results["distances"][0][i]
                    score = 1.0 - distance

                if score < cosine_threshold:
                    continue

                record: dict[str, Any] = {"id": doc_id, "score": score}
                if results.get("documents") and results["documents"][0]:
                    record["content"] = results["documents"][0][i]
                if results.get("metadatas") and results["metadatas"][0]:
                    record.update(results["metadatas"][0][i])
                out.append(record)

        logger.info(
            "[chroma_query] collection=%s where=%s has_embed=%s "
            "raw_results=%d after_threshold=%.2f final=%d",
            self._collection_name, where, has_embed,
            len(results["ids"][0]) if results and results["ids"] else 0,
            cosine_threshold, len(out),
        )

        return out

    async def delete(self, ids: list[str]) -> None:
        if ids:
            self._collection.delete(ids=ids)

    async def drop(self) -> None:
        try:
            self._client.delete_collection(self._collection.name)
            self._collection = self._client.get_or_create_collection(
                name=self._collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as exc:
            logger.warning("Failed to drop collection %s: %s",
                           self._collection_name, exc)
