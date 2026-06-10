"""Multi-tenant workspace isolation for RAG storage backends.

Provides ``WorkspaceConfig`` and ``WorkspaceManager`` to namespace all
storage operations (keys, collections, tables, labels, file paths) by
workspace, enabling data isolation across tenants.

Three isolation modes are supported:

* ``prefix``     — prepend workspace ID to keys/collections/labels (default)
* ``schema``     — use a dedicated database schema per workspace (PostgreSQL)
* ``collection`` — use a dedicated collection per workspace (MongoDB, Chroma)

Usage::

    wm = WorkspaceManager("tenant_a")
    wm.get_namespaced_key("my_key")          # "tenant_a:my_key"
    wm.get_collection_name("chunks")         # "tenant_a_chunks"
    wm.get_file_path("/data", "kv.json")     # "/data/tenant_a/kv.json"
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


# ── Validation ──────────────────────────────────────────────────────

_WORKSPACE_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\-]{0,62}$")

# Hard cap on the number of workspaces to prevent abuse
MAX_WORKSPACES = 1024


def validate_workspace_id(workspace_id: str) -> str:
    """Validate and return a workspace ID, raising on invalid input."""
    if not workspace_id:
        raise ValueError("workspace_id must not be empty")
    if not _WORKSPACE_ID_RE.match(workspace_id):
        raise ValueError(
            f"Invalid workspace_id '{workspace_id}'. "
            "Must start with alphanumeric, contain only [a-zA-Z0-9_-], "
            "and be 1-63 characters."
        )
    return workspace_id


# ── Configuration ───────────────────────────────────────────────────


@dataclass(frozen=True)
class WorkspaceConfig:
    """Configuration for workspace isolation behaviour.

    Attributes
    ----------
    workspace_id:
        Unique identifier for this workspace.
    isolation_mode:
        One of ``"prefix"``, ``"schema"``, ``"collection"``.
    enabled:
        When ``False``, the workspace manager acts as a pass-through
        (no prefixing applied).  Useful for single-tenant mode.
    """

    workspace_id: str = "default"
    isolation_mode: str = "prefix"
    enabled: bool = True

    def __post_init__(self) -> None:
        if self.enabled:
            validate_workspace_id(self.workspace_id)
        valid_modes = ("prefix", "schema", "collection")
        if self.isolation_mode not in valid_modes:
            raise ValueError(
                f"isolation_mode must be one of {valid_modes}, "
                f"got '{self.isolation_mode}'"
            )


# ── Manager ─────────────────────────────────────────────────────────


class WorkspaceManager:
    """Applies workspace isolation to storage identifiers.

    All storage backends receive a ``WorkspaceManager`` through
    ``global_config["workspace_manager"]`` and call these methods to
    namespace their resources.

    When ``enabled`` is ``False`` (or the workspace is ``"default"``
    with ``enabled=True``), identifiers pass through unchanged — this
    preserves backward compatibility with single-tenant deployments.
    """

    def __init__(self, workspace_id: str, *, enabled: bool = True, isolation_mode: str = "prefix") -> None:
        self.config = WorkspaceConfig(
            workspace_id=workspace_id,
            isolation_mode=isolation_mode,
            enabled=enabled,
        )
        self.workspace_id = workspace_id
        self.enabled = enabled and workspace_id != "default"
        self.isolation_mode = isolation_mode

    def __repr__(self) -> str:
        return (
            f"WorkspaceManager(workspace_id={self.workspace_id!r}, "
            f"enabled={self.enabled}, mode={self.isolation_mode!r})"
        )

    # ── Key / Identifier namespacing ─────────────────────────────

    def get_namespaced_key(self, key: str) -> str:
        """Add workspace prefix to a key.

        Example::

            wm = WorkspaceManager("tenant_a")
            wm.get_namespaced_key("my_key")  # "tenant_a:my_key"
        """
        if not self.enabled:
            return key
        return f"{self.workspace_id}:{key}"

    def get_redis_key(self, prefix: str, key: str) -> str:
        """Build a Redis key with workspace isolation.

        Example::

            wm.get_redis_key("aurora_kv:chunks", "doc_1")
            # "tenant_a:aurora_kv:chunks:doc_1"
        """
        if not self.enabled:
            return f"{prefix}:{key}"
        return f"{self.workspace_id}:{prefix}:{key}"

    # ── Collection / Table namespacing ───────────────────────────

    def get_collection_name(self, base_name: str) -> str:
        """Add workspace prefix to a collection/table name.

        Uses underscore separator since collection names typically
        disallow colons.

        Example::

            wm.get_collection_name("chunks")  # "tenant_a_chunks"
        """
        if not self.enabled:
            return base_name
        return f"{self.workspace_id}_{base_name}"

    def get_table_name(self, base_name: str) -> str:
        """Alias for :meth:`get_collection_name`."""
        return self.get_collection_name(base_name)

    # ── Schema namespacing (PostgreSQL) ──────────────────────────

    def get_schema_name(self) -> str:
        """Return the workspace schema name (for schema isolation mode).

        Example::

            wm.get_schema_name()  # "ws_tenant_a"
        """
        return f"ws_{self.workspace_id}"

    # ── File path namespacing ────────────────────────────────────

    def get_file_path(self, base_dir: str, filename: str) -> str:
        """Nest a file under a workspace subdirectory.

        Example::

            wm.get_file_path("/data/rag", "kv.json")
            # "/data/rag/tenant_a/kv.json"
        """
        import os

        if not self.enabled:
            return os.path.join(base_dir, filename)
        return os.path.join(base_dir, self.workspace_id, filename)

    # ── Neo4j label namespacing ──────────────────────────────────

    def get_node_label(self, base_label: str = "Entity") -> str:
        """Build a workspace-scoped Neo4j node label.

        Example::

            wm.get_node_label("Entity")  # "tenant_a_Entity"
        """
        if not self.enabled:
            return base_label
        return f"{self.workspace_id}_{base_label}"

    def get_edge_type(self, base_type: str = "RELATED") -> str:
        """Build a workspace-scoped Neo4j edge type.

        Example::

            wm.get_edge_type("RELATED")  # "tenant_a_RELATED"
        """
        if not self.enabled:
            return base_type
        return f"{self.workspace_id}_{base_type}"

    # ── Namespace prefix for graph storage ───────────────────────

    def get_namespace_prefix(self, namespace: str) -> str:
        """Build a prefixed namespace for graph backends.

        Example::

            wm.get_namespace_prefix("my_kg")  # "tenant_a__my_kg__"
        """
        if not self.enabled:
            return f"{namespace}__"
        return f"{self.workspace_id}__{namespace}__"

    # ── Utility ──────────────────────────────────────────────────

    def strip_prefix(self, namespaced_key: str) -> str:
        """Remove the workspace prefix from a key (reverse of get_namespaced_key)."""
        if not self.enabled:
            return namespaced_key
        prefix = f"{self.workspace_id}:"
        if namespaced_key.startswith(prefix):
            return namespaced_key[len(prefix):]
        return namespaced_key

    def to_config_dict(self) -> dict[str, Any]:
        """Serialize workspace config for embedding in global_config."""
        return {
            "workspace_id": self.workspace_id,
            "workspace_enabled": self.enabled,
            "workspace_isolation_mode": self.isolation_mode,
        }


# ── Convenience ─────────────────────────────────────────────────────


def get_workspace_manager(global_config: dict[str, Any]) -> WorkspaceManager:
    """Extract or create a WorkspaceManager from a global_config dict.

    If ``global_config`` already contains a ``workspace_manager`` key,
    that instance is returned.  Otherwise, a new manager is created
    from ``workspace_id`` / ``workspace_enabled`` keys.
    """
    existing = global_config.get("workspace_manager")
    if existing is not None and isinstance(existing, WorkspaceManager):
        return existing

    workspace_id = global_config.get("workspace_id", "default")
    enabled = global_config.get("workspace_enabled", True)
    isolation_mode = global_config.get("workspace_isolation_mode", "prefix")
    return WorkspaceManager(
        workspace_id=workspace_id,
        enabled=enabled,
        isolation_mode=isolation_mode,
    )


def default_workspace_manager() -> WorkspaceManager:
    """Return a no-op workspace manager (single-tenant default)."""
    return WorkspaceManager(workspace_id="default", enabled=True)
