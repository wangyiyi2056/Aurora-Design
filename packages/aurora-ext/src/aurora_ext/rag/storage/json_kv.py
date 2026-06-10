"""JSON-file-based key-value storage.

Migrated from LightRAG ``kg/json_kv_impl.py``.

Each namespace is persisted as a single JSON file at
``{working_dir}/{namespace}.json``.  Suitable for development and
small-scale deployments.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

from aurora_ext.rag.storage.base import BaseKVStorage
from aurora_ext.rag.storage.workspace import get_workspace_manager

logger = logging.getLogger(__name__)


class JsonKVStorage(BaseKVStorage):
    """JSON file-backed key-value store.

    Supports workspace isolation: when a ``WorkspaceManager`` is present
    in ``global_config``, data files are placed in a workspace
    subdirectory — ``{working_dir}/{workspace_id}/{namespace}.json``.
    """

    def __init__(self, namespace: str, global_config: dict[str, Any]) -> None:
        super().__init__(namespace, global_config)
        working_dir = global_config.get("working_dir", "./rag_storage")
        wm = get_workspace_manager(global_config)
        self._workspace_manager = wm
        self._file_path = wm.get_file_path(working_dir, f"{namespace}.json")
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

    # ── BaseKVStorage interface ──────────────────────────────────

    async def all_keys(self) -> list[str]:
        await self._ensure_loaded()
        return list(self._data.keys())

    async def get_by_id(self, key: str) -> Optional[dict[str, Any]]:
        await self._ensure_loaded()
        return self._data.get(key)

    async def get_by_ids(self, keys: list[str]) -> list[Optional[dict[str, Any]]]:
        await self._ensure_loaded()
        return [self._data.get(k) for k in keys]

    async def get_by_field(self, field: str, value: Any) -> list[dict[str, Any]]:
        await self._ensure_loaded()
        return [
            record
            for record in self._data.values()
            if record.get(field) == value
        ]

    async def upsert(self, data: dict[str, dict[str, Any]]) -> None:
        await self._ensure_loaded()
        self._data.update(data)
        await self._persist()

    async def delete(self, keys: list[str]) -> None:
        await self._ensure_loaded()
        for key in keys:
            self._data.pop(key, None)
        await self._persist()

    async def drop(self) -> None:
        self._data = {}
        if os.path.exists(self._file_path):
            os.remove(self._file_path)
