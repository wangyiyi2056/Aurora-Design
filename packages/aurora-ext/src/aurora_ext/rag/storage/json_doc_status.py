"""JSON-file-based document status storage.

Migrated from LightRAG ``kg/json_doc_status_impl.py``.

Persists the document processing state machine as a JSON file at
``{working_dir}/{namespace}_status.json``.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Optional

from aurora_ext.rag.storage.base import (
    BaseDocStatusStorage,
    DocStatus,
    DocStatusInfo,
)
from aurora_ext.rag.storage.workspace import get_workspace_manager

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class JsonDocStatusStorage(BaseDocStatusStorage):
    """JSON file-backed document status storage.

    Supports workspace isolation: when a ``WorkspaceManager`` is present
    in ``global_config``, the status file is placed in a workspace
    subdirectory — ``{working_dir}/{workspace_id}/{namespace}_status.json``.
    """

    def __init__(self, namespace: str, global_config: dict[str, Any]) -> None:
        super().__init__(namespace, global_config)
        working_dir = global_config.get("working_dir", "./rag_storage")
        wm = get_workspace_manager(global_config)
        self._workspace_manager = wm
        self._file_path = wm.get_file_path(working_dir, f"{namespace}_status.json")
        self._data: dict[str, dict[str, Any]] = {}
        self._loaded = False

    async def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        if os.path.exists(self._file_path):
            try:
                with open(self._file_path, "r", encoding="utf-8") as fh:
                    self._data = json.load(fh)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to load %s: %s", self._file_path, exc)
                self._data = {}
        self._loaded = True

    async def _persist(self) -> None:
        os.makedirs(os.path.dirname(self._file_path), exist_ok=True)
        with open(self._file_path, "w", encoding="utf-8") as fh:
            json.dump(self._data, fh, ensure_ascii=False, indent=2)

    @staticmethod
    def _to_info(raw: dict[str, Any]) -> DocStatusInfo:
        return DocStatusInfo(
            id=raw.get("id", ""),
            file_path=raw.get("file_path", ""),
            status=DocStatus(raw.get("status", "PENDING")),
            content_summary=raw.get("content_summary", ""),
            content_length=raw.get("content_length", 0),
            chunks_count=raw.get("chunks_count", 0),
            error_msg=raw.get("error_msg"),
            track_id=raw.get("track_id", ""),
            metadata=raw.get("metadata", {}),
            created_at=raw.get("created_at", ""),
            updated_at=raw.get("updated_at", ""),
            kb_name=raw.get("kb_name", ""),
            content_hash=raw.get("content_hash", ""),
            duplicate_kind=raw.get("duplicate_kind", ""),
            basename=raw.get("basename", ""),
        )

    @staticmethod
    def _matches_kb(raw: dict[str, Any], kb_name: str | None) -> bool:
        """Return True if *raw* belongs to *kb_name*.

        When *kb_name* is ``None`` or empty, all documents match (no filter).
        Documents with an empty ``kb_name`` field (legacy data created before
        KB scoping was added) only match when no filter is active.
        """
        if not kb_name:
            return True
        return raw.get("kb_name", "") == kb_name

    # ── BaseDocStatusStorage interface ───────────────────────────

    async def get_status(self, doc_id: str) -> Optional[DocStatusInfo]:
        await self._ensure_loaded()
        raw = self._data.get(doc_id)
        if raw is None:
            return None
        return self._to_info(raw)

    async def get_statuses_by_ids(
        self, doc_ids: list[str]
    ) -> list[Optional[DocStatusInfo]]:
        await self._ensure_loaded()
        out: list[Optional[DocStatusInfo]] = []
        for did in doc_ids:
            raw = self._data.get(did)
            out.append(self._to_info(raw) if raw else None)
        return out

    async def get_docs_by_status(
        self, status: DocStatus, *, kb_name: str | None = None
    ) -> list[DocStatusInfo]:
        await self._ensure_loaded()
        return [
            self._to_info(raw)
            for raw in self._data.values()
            if raw.get("status") == status.value and self._matches_kb(raw, kb_name)
        ]

    async def get_all_docs(
        self,
        status_filters: Optional[list[DocStatus]] = None,
        page: int = 1,
        page_size: int = 50,
        sort_field: str = "created_at",
        sort_direction: str = "desc",
        *,
        kb_name: str | None = None,
    ) -> tuple[list[DocStatusInfo], int]:
        await self._ensure_loaded()

        all_docs = [
            self._to_info(raw)
            for raw in self._data.values()
            if self._matches_kb(raw, kb_name)
        ]

        if status_filters:
            filter_set = {s.value for s in status_filters}
            all_docs = [d for d in all_docs if d.status.value in filter_set]

        total = len(all_docs)

        reverse = sort_direction == "desc"
        all_docs.sort(key=lambda d: getattr(d, sort_field, ""), reverse=reverse)

        start = (page - 1) * page_size
        end = start + page_size
        return all_docs[start:end], total

    async def get_status_counts(self, *, kb_name: str | None = None) -> dict[str, int]:
        await self._ensure_loaded()
        counts: dict[str, int] = {}
        for raw in self._data.values():
            if not self._matches_kb(raw, kb_name):
                continue
            s = raw.get("status", "PENDING")
            counts[s] = counts.get(s, 0) + 1
        return counts

    async def upsert(self, docs: dict[str, DocStatusInfo]) -> None:
        await self._ensure_loaded()
        now = _now_iso()
        for doc_id, info in docs.items():
            existing = self._data.get(doc_id)
            record = asdict(info)
            record["status"] = info.status.value
            if existing is None:
                record["created_at"] = now
            else:
                record["created_at"] = existing.get("created_at", now)
            record["updated_at"] = now
            self._data[doc_id] = record
        await self._persist()

    async def update_status(
        self,
        doc_id: str,
        status: DocStatus,
        error_msg: Optional[str] = None,
        **extra: Any,
    ) -> None:
        await self._ensure_loaded()
        now = _now_iso()
        if doc_id not in self._data:
            self._data[doc_id] = {
                "id": doc_id,
                "file_path": "",
                "status": status.value,
                "created_at": now,
            }
        self._data[doc_id]["status"] = status.value
        self._data[doc_id]["updated_at"] = now
        if error_msg is not None:
            self._data[doc_id]["error_msg"] = error_msg
        for k, v in extra.items():
            self._data[doc_id][k] = v
        await self._persist()

    async def get_doc_by_basename(
        self, basename: str, *, kb_name: str | None = None
    ) -> Optional[DocStatusInfo]:
        """Find a document by its filename basename.

        Scans all stored documents for a matching ``basename`` field
        within the given knowledge base scope.
        """
        await self._ensure_loaded()
        for raw in self._data.values():
            if not self._matches_kb(raw, kb_name):
                continue
            if raw.get("basename", "") == basename:
                return self._to_info(raw)
        return None

    async def get_doc_by_content_hash(
        self, content_hash: str, *, kb_name: str | None = None
    ) -> Optional[DocStatusInfo]:
        """Find a document by its content hash.

        Scans all stored documents for a matching ``content_hash`` field
        within the given knowledge base scope.
        """
        await self._ensure_loaded()
        for raw in self._data.values():
            if not self._matches_kb(raw, kb_name):
                continue
            if raw.get("content_hash", "") == content_hash:
                return self._to_info(raw)
        return None

    async def delete(self, doc_ids: list[str]) -> None:
        await self._ensure_loaded()
        for doc_id in doc_ids:
            self._data.pop(doc_id, None)
        await self._persist()

    async def drop(self) -> None:
        self._data = {}
        if os.path.exists(self._file_path):
            os.remove(self._file_path)
