"""Workspace management API endpoints.

Provides CRUD operations for managing tenant workspaces that isolate
storage data across all RAG backends (KV, vector, graph, doc status).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from aurora_serve.workspace.service import WorkspaceService

router = APIRouter(prefix="/tenants", tags=["tenants"])


# ── Request / Response schemas ─────────────────────────────────────


class CreateWorkspaceRequest(BaseModel):
    workspace_id: str = Field(
        ...,
        min_length=1,
        max_length=63,
        pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_\-]*$",
        description="Unique workspace identifier (alphanumeric, underscore, dash)",
    )
    isolation_mode: str = Field(
        default="prefix",
        description="Isolation mode: prefix, schema, or collection",
    )
    description: str = Field(default="", description="Human-readable description")


class WorkspaceInfoResponse(BaseModel):
    id: str
    isolation_mode: str
    created_at: str
    updated_at: str
    description: str


class WorkspaceStatsResponse(BaseModel):
    workspace_id: str
    kv_keys: int
    vector_items: int
    graph_nodes: int
    graph_edges: int
    doc_statuses: int
    storage_files: list[str]


class DeleteWorkspaceRequest(BaseModel):
    cleanup_data: bool = Field(
        default=True,
        description="Whether to remove all data belonging to the workspace",
    )


# ── Dependency ─────────────────────────────────────────────────────


_workspace_service: WorkspaceService | None = None


def get_workspace_service() -> WorkspaceService:
    global _workspace_service
    if _workspace_service is None:
        _workspace_service = WorkspaceService()
    return _workspace_service


# ── Endpoints ──────────────────────────────────────────────────────


@router.get("", summary="List all workspaces")
async def list_workspaces(
    service: WorkspaceService = Depends(get_workspace_service),
) -> list[WorkspaceInfoResponse]:
    """Return all registered tenant workspaces."""
    workspaces = service.list_workspaces()
    return [
        WorkspaceInfoResponse(
            id=ws.id,
            isolation_mode=ws.isolation_mode,
            created_at=ws.created_at,
            updated_at=ws.updated_at,
            description=ws.description,
        )
        for ws in workspaces
    ]


@router.post("", summary="Create a new workspace", status_code=201)
async def create_workspace(
    req: CreateWorkspaceRequest,
    service: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceInfoResponse:
    """Create a new tenant workspace for data isolation."""
    try:
        ws = service.create_workspace(
            req.workspace_id,
            isolation_mode=req.isolation_mode,
            description=req.description,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=507, detail=str(exc))

    return WorkspaceInfoResponse(
        id=ws.id,
        isolation_mode=ws.isolation_mode,
        created_at=ws.created_at,
        updated_at=ws.updated_at,
        description=ws.description,
    )


@router.get("/{workspace_id}", summary="Get workspace details")
async def get_workspace(
    workspace_id: str,
    service: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceInfoResponse:
    """Get details for a specific workspace."""
    ws = service.get_workspace(workspace_id)
    if ws is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return WorkspaceInfoResponse(
        id=ws.id,
        isolation_mode=ws.isolation_mode,
        created_at=ws.created_at,
        updated_at=ws.updated_at,
        description=ws.description,
    )


@router.delete("/{workspace_id}", summary="Delete a workspace")
async def delete_workspace(
    workspace_id: str,
    req: DeleteWorkspaceRequest | None = None,
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, Any]:
    """Delete a workspace and optionally clean up its data."""
    cleanup = req.cleanup_data if req else True
    try:
        service.delete_workspace(workspace_id, cleanup_data=cleanup)
    except ValueError as exc:
        status = 400 if "default" in str(exc) else 404
        raise HTTPException(status_code=status, detail=str(exc))

    return {
        "status": "deleted",
        "workspace_id": workspace_id,
        "cleanup_data": cleanup,
    }


@router.get("/{workspace_id}/stats", summary="Get workspace statistics")
async def get_workspace_stats(
    workspace_id: str,
    service: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceStatsResponse:
    """Get storage usage statistics for a workspace."""
    try:
        stats = service.get_stats(workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return WorkspaceStatsResponse(
        workspace_id=stats.workspace_id,
        kv_keys=stats.kv_keys,
        vector_items=stats.vector_items,
        graph_nodes=stats.graph_nodes,
        graph_edges=stats.graph_edges,
        doc_statuses=stats.doc_statuses,
        storage_files=stats.storage_files,
    )


# ── Workspace extraction header ────────────────────────────────────


def extract_workspace_id(
    x_workspace_id: str = Header(default="default"),
) -> str:
    """FastAPI dependency to extract workspace ID from request header.

    Usage in route handlers::

        @router.get("/knowledge/{name}/query")
        async def query(
            name: str,
            workspace_id: str = Depends(extract_workspace_id),
        ):
            ...
    """
    return x_workspace_id
