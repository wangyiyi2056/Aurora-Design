"""Tests for workspace service (API layer)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from aurora_serve.workspace.service import WorkspaceInfo, WorkspaceService


class TestWorkspaceService:
    @pytest.fixture
    def tmp_dir(self) -> Path:
        with tempfile.TemporaryDirectory() as d:
            yield Path(d)

    @pytest.fixture
    def service(self, tmp_dir: Path) -> WorkspaceService:
        return WorkspaceService(data_dir=tmp_dir)

    def test_default_workspace_exists(self, service: WorkspaceService) -> None:
        workspaces = service.list_workspaces()
        assert len(workspaces) >= 1
        ids = [ws.id for ws in workspaces]
        assert "default" in ids

    def test_create_workspace(self, service: WorkspaceService) -> None:
        ws = service.create_workspace("tenant_a", description="Test tenant A")
        assert ws.id == "tenant_a"
        assert ws.description == "Test tenant A"
        assert ws.isolation_mode == "prefix"

    def test_create_duplicate_workspace(self, service: WorkspaceService) -> None:
        service.create_workspace("tenant_b")
        with pytest.raises(ValueError, match="already exists"):
            service.create_workspace("tenant_b")

    def test_create_invalid_workspace(self, service: WorkspaceService) -> None:
        with pytest.raises(ValueError, match="Invalid"):
            service.create_workspace("invalid/workspace")

    def test_get_workspace(self, service: WorkspaceService) -> None:
        service.create_workspace("tenant_c")
        ws = service.get_workspace("tenant_c")
        assert ws is not None
        assert ws.id == "tenant_c"

    def test_get_nonexistent_workspace(self, service: WorkspaceService) -> None:
        assert service.get_workspace("nonexistent") is None

    def test_delete_workspace(self, service: WorkspaceService) -> None:
        service.create_workspace("tenant_d")
        service.delete_workspace("tenant_d")
        assert service.get_workspace("tenant_d") is None

    def test_delete_default_workspace_fails(self, service: WorkspaceService) -> None:
        with pytest.raises(ValueError, match="default"):
            service.delete_workspace("default")

    def test_delete_nonexistent_workspace(self, service: WorkspaceService) -> None:
        with pytest.raises(ValueError, match="not found"):
            service.delete_workspace("nonexistent")

    def test_get_stats_empty_workspace(self, service: WorkspaceService) -> None:
        service.create_workspace("tenant_e")
        stats = service.get_stats("tenant_e")
        assert stats.workspace_id == "tenant_e"
        assert stats.kv_keys == 0
        assert stats.storage_files == []

    def test_get_workspace_manager(self, service: WorkspaceService) -> None:
        service.create_workspace("tenant_f", isolation_mode="schema")
        wm = service.get_workspace_manager("tenant_f")
        assert wm.workspace_id == "tenant_f"
        assert wm.isolation_mode == "schema"

    def test_persistence(self, tmp_dir: Path) -> None:
        """Workspace registry should persist across service restarts."""
        service1 = WorkspaceService(data_dir=tmp_dir)
        service1.create_workspace("tenant_g", description="persistent")
        del service1

        service2 = WorkspaceService(data_dir=tmp_dir)
        ws = service2.get_workspace("tenant_g")
        assert ws is not None
        assert ws.description == "persistent"

    def test_list_multiple_workspaces(self, service: WorkspaceService) -> None:
        service.create_workspace("ws_1")
        service.create_workspace("ws_2")
        service.create_workspace("ws_3")
        workspaces = service.list_workspaces()
        ids = {ws.id for ws in workspaces}
        assert ids >= {"default", "ws_1", "ws_2", "ws_3"}
