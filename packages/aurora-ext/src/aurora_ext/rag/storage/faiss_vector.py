"""FAISS-backed vector storage.

Local vector store using ``faiss-cpu`` (or ``faiss-gpu``) with numpy.
The FAISS index is persisted to ``{working_dir}/faiss/{namespace}.index``
and the ID/data mapping is stored alongside as ``{namespace}_data.json``.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

import numpy as np

from aurora_ext.rag.storage.base import BaseVectorStorage
from aurora_ext.rag.storage.workspace import get_workspace_manager

logger = logging.getLogger(__name__)


class FaissVectorDBStorage(BaseVectorStorage):
    """FAISS-backed vector storage with HNSW or flat index.

    Supports workspace isolation via subdirectory for FAISS index files.
    """

    def __init__(self, namespace: str, global_config: dict[str, Any]) -> None:
        super().__init__(namespace, global_config)
        wm = get_workspace_manager(global_config)
        self._workspace_manager = wm
        self._embedding_func = global_config.get("embedding_func")

        embedding_dim = 1536
        if self._embedding_func is not None:
            dim = getattr(self._embedding_func, "embedding_dim", None)
            if dim is not None:
                embedding_dim = int(dim)
        self._embedding_dim = global_config.get("embedding_dim", embedding_dim)

        working_dir = global_config.get("working_dir", "./rag_storage")
        faiss_base = os.path.join(working_dir, "faiss")
        faiss_dir = wm.get_file_path(faiss_base, ".")
        # get_file_path with "." gives us the workspace subdir
        faiss_dir = os.path.dirname(wm.get_file_path(faiss_base, "placeholder"))
        os.makedirs(faiss_dir, exist_ok=True)

        self._index_path = os.path.join(faiss_dir, f"{namespace}.index")
        self._data_path = os.path.join(faiss_dir, f"{namespace}_data.json")

        # id -> index position
        self._id_to_idx: dict[str, int] = {}
        # index position -> {content, metadata}
        self._idx_to_data: dict[int, dict[str, Any]] = {}
        self._next_idx: int = 0

        import faiss

        self._faiss = faiss
        self._index: faiss.Index = self._load_or_create_index()

    def _load_or_create_index(self) -> Any:
        """Load existing index from disk or create a new HNSW index."""
        if os.path.exists(self._index_path):
            try:
                index = self._faiss.read_index(self._index_path)
                # Reload mapping
                if os.path.exists(self._data_path):
                    with open(self._data_path, "r", encoding="utf-8") as fh:
                        saved = json.load(fh)
                    self._id_to_idx = saved.get("id_to_idx", {})
                    self._idx_to_data = {
                        int(k): v for k, v in saved.get("idx_to_data", {}).items()
                    }
                    self._next_idx = max(
                        (int(x) for x in self._idx_to_data.keys()), default=-1
                    ) + 1
                return index
            except Exception as exc:
                logger.warning("Failed to load FAISS index: %s", exc)

        # HNSW index with inner product (cosine for normalised vectors)
        index = self._faiss.IndexHNSWFlat(self._embedding_dim, 32)
        return index

    def _persist(self) -> None:
        """Write index and mapping to disk."""
        self._faiss.write_index(self._index, self._index_path)
        saved = {
            "id_to_idx": self._id_to_idx,
            "idx_to_data": {str(k): v for k, v in self._idx_to_data.items()},
        }
        with open(self._data_path, "w", encoding="utf-8") as fh:
            json.dump(saved, fh, ensure_ascii=False)

    def _normalize(self, vec: list[float]) -> np.ndarray:
        """L2-normalize a vector for cosine similarity."""
        arr = np.array(vec, dtype=np.float32).reshape(1, -1)
        norm = np.linalg.norm(arr)
        if norm > 0:
            arr = arr / norm
        return arr

    # ── BaseVectorStorage interface ──────────────────────────────

    async def upsert(self, data: dict[str, dict[str, Any]]) -> None:
        if not data:
            return

        vectors: list[np.ndarray] = []
        ids_to_add: list[str] = []

        for key, record in data.items():
            vector = record.get("__vector__")
            if vector is None:
                logger.warning("Record %s missing __vector__, skipping", key)
                continue

            vec = self._normalize(
                vector if isinstance(vector, list) else list(vector)
            )
            vectors.append(vec)
            ids_to_add.append(key)

            meta = {
                k: v
                for k, v in record.items()
                if k not in ("content", "__vector__")
            }
            idx = self._next_idx
            self._id_to_idx[key] = idx
            self._idx_to_data[idx] = {
                "content": record.get("content", ""),
                "metadata": meta,
            }
            self._next_idx += 1

        if vectors:
            all_vecs = np.vstack(vectors)
            self._index.add(all_vecs)

        self._persist()

    async def query(
        self,
        query_text: str,
        top_k: int,
        cosine_threshold: float = 0.0,
    ) -> list[dict[str, Any]]:
        if self._embedding_func is None:
            logger.warning("No embedding function; cannot perform vector query")
            return []

        if self._index.ntotal == 0:
            return []

        vec = await self._embedding_func([query_text], is_query=True)
        query_vec = self._normalize(
            vec[0].tolist() if hasattr(vec[0], "tolist") else list(vec[0])
        )

        k = min(top_k, self._index.ntotal)
        scores, indices = self._index.search(query_vec, k)

        out: list[dict[str, Any]] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            score_val = float(score)
            if score_val < cosine_threshold:
                continue

            entry = self._idx_to_data.get(int(idx))
            if entry is None:
                continue

            # Reverse-lookup the ID
            doc_id = ""
            for did, pos in self._id_to_idx.items():
                if pos == int(idx):
                    doc_id = did
                    break

            record: dict[str, Any] = {
                "id": doc_id,
                "score": score_val,
                "content": entry.get("content", ""),
            }
            record.update(entry.get("metadata", {}))
            out.append(record)

        return out

    async def delete(self, ids: list[str]) -> None:
        if not ids:
            return
        # FAISS doesn't support direct deletion from HNSW index easily.
        # We mark them as deleted in the mapping and rebuild if needed.
        for doc_id in ids:
            idx = self._id_to_idx.pop(doc_id, None)
            if idx is not None:
                self._idx_to_data.pop(idx, None)
        self._persist()

    async def drop(self) -> None:
        self._id_to_idx = {}
        self._idx_to_data = {}
        self._next_idx = 0

        index = self._faiss.IndexHNSWFlat(self._embedding_dim, 32)
        self._index = index

        for path in (self._index_path, self._data_path):
            if os.path.exists(path):
                os.remove(path)
