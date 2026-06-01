"""Multi-tenant workspace management for data isolation.

This package provides the API and service layer for managing workspaces
(tenants) that isolate storage across all RAG backends.
"""

from aurora_serve.workspace.api import router
from aurora_serve.workspace.service import WorkspaceService

__all__ = ["WorkspaceService", "router"]
