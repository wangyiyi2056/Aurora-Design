"""Workspace lifecycle management service.

Manages workspace creation, deletion, listing, and statistics.
Persists workspace metadata to a JSON file in the data directory.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from aurora_ext.rag.storage.workspace import (
    MAX_WORKSPACES,
    WorkspaceManager,
    validate_workspace_id,
)

logger = logging.getLogger(__name__)


@dataclass
class WorkspaceInfo:
    """Metadata for a single workspace."""

    id: str
    isolation_mode: str = "prefix"
    created_at: str = ""
    updated_at: str = ""
    description: str = ""
    kv_count: int = 0
    vector_count: int = 0
    graph_node_count: int = 0
    graph_edge_count: int = 0
    doc_count: int = 0


@dataclass
class WorkspaceStats:
    """Aggregate statistics for a workspace."""

    workspace_id: str
    kv_keys: int = 0
    vector_items: int = 0
    graph_nodes: int = 0
    graph_edges: int = 0
    doc_statuses: int = 0
    storage_files: list[str] = field(default_factory=list)


class WorkspaceService:
    """Manages workspace lifecycle and metadata persistence.

    Workspace metadata is stored in ``{data_dir}/workspace_registry.json``.
    Actual data isolation is delegated to :class:`WorkspaceManager` which
    each storage backend consults during init.
    """

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        if data_dir is None:
            from aurora_serve.metadata import storage_dir

            data_dir = storage_dir()
        self._data_dir = data_dir
        self._registry_path = data_dir / "workspace_registry.json"
        self._workspaces: dict[str, WorkspaceInfo] = {}
        self._load_registry()

        # Ensure default workspace always exists
        if "default" not in self._workspaces:
            self._workspaces["default"] = WorkspaceInfo(
                id="default",
                isolation_mode="prefix",
                created_at=_now_iso(),
                description="Default workspace (single-tenant mode)",
            )
            self._save_registry()

    # ── Public API ────────────────────────────────────────────────

    def list_workspaces(self) -> list[WorkspaceInfo]:
        """Return all registered workspaces."""
        return list(self._workspaces.values())

    def get_workspace(self, workspace_id: str) -> Optional[WorkspaceInfo]:
        """Get a single workspace by ID."""
        return self._workspaces.get(workspace_id)

    def create_workspace(
        self,
        workspace_id: str,
        *,
        isolation_mode: str = "prefix",
        description: str = "",
    ) -> WorkspaceInfo:
        """Create a new workspace.

        Raises
        ------
        ValueError
            If workspace ID is invalid or already exists.
        RuntimeError
            If max workspace limit is reached.
        """
        validate_workspace_id(workspace_id)

        if workspace_id in self._workspaces:
            raise ValueError(f"Workspace '{workspace_id}' already exists")

        if len(self._workspaces) >= MAX_WORKSPACES:
            raise RuntimeError(
                f"Maximum workspace limit ({MAX_WORKSPACES}) reached"
            )

        now = _now_iso()
        info = WorkspaceInfo(
            id=workspace_id,
            isolation_mode=isolation_mode,
            created_at=now,
            updated_at=now,
            description=description,
        )
        self._workspaces[workspace_id] = info
        self._save_registry()
        logger.info("Created workspace '%s'", workspace_id)
        return info

    def delete_workspace(self, workspace_id: str, *, cleanup_data: bool = True) -> None:
        """Delete a workspace and optionally clean up its data.

        Raises
        ------
        ValueError
            If workspace does not exist or is the default workspace.
        """
        if workspace_id == "default":
            raise ValueError("Cannot delete the default workspace")

        if workspace_id not in self._workspaces:
            raise ValueError(f"Workspace '{workspace_id}' not found")

        if cleanup_data:
            self._cleanup_workspace_data(workspace_id)

        del self._workspaces[workspace_id]
        self._save_registry()
        logger.info(
            "Deleted workspace '%s' (cleanup=%s)", workspace_id, cleanup_data
        )

    def get_stats(self, workspace_id: str) -> WorkspaceStats:
        """Get storage statistics for a workspace.

        Inspects the file system for JSON storage files created by
        this workspace.  For remote backends (Redis, PostgreSQL, etc.)
        the counts are estimated from metadata where possible.
        """
        if workspace_id not in self._workspaces:
            raise ValueError(f"Workspace '{workspace_id}' not found")

        stats = WorkspaceStats(workspace_id=workspace_id)
        wm = WorkspaceManager(workspace_id)

        # Scan for workspace-specific files in the data directory
        ws_dir = self._data_dir / workspace_id
        if ws_dir.exists() and ws_dir.is_dir():
            for f in ws_dir.rglob("*"):
                if f.is_file():
                    stats.storage_files.append(str(f.relative_to(self._data_dir)))
                    if f.suffix == ".json":
                        try:
                            with open(f, "r", encoding="utf-8") as fh:
                                data = json.load(fh)
                            if isinstance(data, dict):
                                if "_status" in f.stem:
                                    stats.doc_statuses = len(data)
                                else:
                                    stats.kv_keys = len(data)
                        except (json.JSONDecodeError, OSError):
                            pass

        return stats

    def get_workspace_manager(self, workspace_id: str) -> WorkspaceManager:
        """Create a WorkspaceManager for the given workspace ID.

        Validates that the workspace exists before returning.
        """
        if workspace_id not in self._workspaces:
            raise ValueError(f"Workspace '{workspace_id}' not found")

        info = self._workspaces[workspace_id]
        return WorkspaceManager(
            workspace_id=workspace_id,
            isolation_mode=info.isolation_mode,
        )

    # ── Internal ──────────────────────────────────────────────────

    def _cleanup_workspace_data(self, workspace_id: str) -> None:
        """Remove all data files belonging to a workspace."""
        ws_dir = self._data_dir / workspace_id
        if ws_dir.exists() and ws_dir.is_dir():
            shutil.rmtree(ws_dir, ignore_errors=True)
            logger.info("Removed workspace data directory: %s", ws_dir)

        # Also clean up any workspace-prefixed files in parent dirs
        # (e.g., Chroma collections named {workspace_id}_{namespace})
        # These are handled by the storage backends themselves on drop()

    def _load_registry(self) -> None:
        if self._registry_path.exists():
            try:
                with open(self._registry_path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                for item in data:
                    info = WorkspaceInfo(**item)
                    self._workspaces[info.id] = info
            except (json.JSONDecodeError, OSError, TypeError) as exc:
                logger.warning("Failed to load workspace registry: %s", exc)
                self._workspaces = {}

    def _save_registry(self) -> None:
        os.makedirs(self._data_dir, exist_ok=True)
        data = [asdict(ws) for ws in self._workspaces.values()]
        with open(self._registry_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
