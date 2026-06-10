"""Tests for workspace isolation module.

Covers WorkspaceConfig, WorkspaceManager, and storage backend integration.
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aurora_ext.rag.storage.workspace import (
    WorkspaceConfig,
    WorkspaceManager,
    default_workspace_manager,
    get_workspace_manager,
    validate_workspace_id,
)


# ── WorkspaceConfig Tests ──────────────────────────────────────────


class TestWorkspaceConfig:
    def test_default_config(self) -> None:
        config = WorkspaceConfig()
        assert config.workspace_id == "default"
        assert config.isolation_mode == "prefix"
        assert config.enabled is True

    def test_custom_config(self) -> None:
        config = WorkspaceConfig(
            workspace_id="tenant_a",
            isolation_mode="schema",
            enabled=True,
        )
        assert config.workspace_id == "tenant_a"
        assert config.isolation_mode == "schema"

    def test_frozen_dataclass(self) -> None:
        config = WorkspaceConfig()
        with pytest.raises(AttributeError):
            config.workspace_id = "other"  # type: ignore[misc]

    def test_invalid_isolation_mode(self) -> None:
        with pytest.raises(ValueError, match="isolation_mode"):
            WorkspaceConfig(isolation_mode="invalid")

    def test_invalid_workspace_id_when_enabled(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            WorkspaceConfig(workspace_id="")

    def test_disabled_skips_validation(self) -> None:
        config = WorkspaceConfig(workspace_id="", enabled=False)
        assert config.enabled is False


# ── validate_workspace_id Tests ────────────────────────────────────


class TestValidateWorkspaceId:
    def test_valid_ids(self) -> None:
        assert validate_workspace_id("default") == "default"
        assert validate_workspace_id("tenant_a") == "tenant_a"
        assert validate_workspace_id("tenant-b") == "tenant-b"
        assert validate_workspace_id("T1") == "T1"
        assert validate_workspace_id("a" * 63) == "a" * 63

    def test_empty_id(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            validate_workspace_id("")

    def test_starts_with_underscore(self) -> None:
        with pytest.raises(ValueError, match="Invalid workspace_id"):
            validate_workspace_id("_invalid")

    def test_starts_with_dash(self) -> None:
        with pytest.raises(ValueError, match="Invalid workspace_id"):
            validate_workspace_id("-invalid")

    def test_special_characters(self) -> None:
        with pytest.raises(ValueError, match="Invalid workspace_id"):
            validate_workspace_id("tenant.a")
        with pytest.raises(ValueError, match="Invalid workspace_id"):
            validate_workspace_id("tenant/a")
        with pytest.raises(ValueError, match="Invalid workspace_id"):
            validate_workspace_id("tenant a")

    def test_too_long(self) -> None:
        with pytest.raises(ValueError, match="Invalid workspace_id"):
            validate_workspace_id("a" * 64)


# ── WorkspaceManager Tests ─────────────────────────────────────────


class TestWorkspaceManager:
    def test_default_workspace_no_prefixing(self) -> None:
        """Default workspace should not add prefixes (backward compat)."""
        wm = WorkspaceManager("default")
        assert wm.enabled is False
        assert wm.get_namespaced_key("my_key") == "my_key"
        assert wm.get_collection_name("chunks") == "chunks"
        assert wm.get_file_path("/data", "kv.json") == "/data/kv.json"

    def test_tenant_workspace_adds_prefix(self) -> None:
        wm = WorkspaceManager("tenant_a")
        assert wm.enabled is True
        assert wm.get_namespaced_key("my_key") == "tenant_a:my_key"
        assert wm.get_collection_name("chunks") == "tenant_a_chunks"

    def test_disabled_workspace_no_prefix(self) -> None:
        wm = WorkspaceManager("tenant_a", enabled=False)
        assert wm.enabled is False
        assert wm.get_namespaced_key("key") == "key"

    def test_get_redis_key(self) -> None:
        wm = WorkspaceManager("tenant_a")
        assert wm.get_redis_key("aurora_kv:chunks", "doc_1") == (
            "tenant_a:aurora_kv:chunks:doc_1"
        )

    def test_get_redis_key_default(self) -> None:
        wm = WorkspaceManager("default")
        assert wm.get_redis_key("aurora_kv:chunks", "doc_1") == (
            "aurora_kv:chunks:doc_1"
        )

    def test_get_table_name(self) -> None:
        wm = WorkspaceManager("tenant_b")
        assert wm.get_table_name("aurora_kv") == "tenant_b_aurora_kv"

    def test_get_schema_name(self) -> None:
        wm = WorkspaceManager("tenant_a")
        assert wm.get_schema_name() == "ws_tenant_a"

    def test_get_file_path_with_workspace(self) -> None:
        wm = WorkspaceManager("tenant_a")
        path = wm.get_file_path("/data/rag", "kv.json")
        assert path == "/data/rag/tenant_a/kv.json"

    def test_get_file_path_default(self) -> None:
        wm = WorkspaceManager("default")
        path = wm.get_file_path("/data/rag", "kv.json")
        assert path == "/data/rag/kv.json"

    def test_get_node_label(self) -> None:
        wm = WorkspaceManager("tenant_a")
        assert wm.get_node_label("Entity") == "tenant_a_Entity"

    def test_get_node_label_default(self) -> None:
        wm = WorkspaceManager("default")
        assert wm.get_node_label("Entity") == "Entity"

    def test_get_edge_type(self) -> None:
        wm = WorkspaceManager("tenant_a")
        assert wm.get_edge_type("RELATED") == "tenant_a_RELATED"

    def test_get_edge_type_default(self) -> None:
        wm = WorkspaceManager("default")
        assert wm.get_edge_type("RELATED") == "RELATED"

    def test_get_namespace_prefix(self) -> None:
        wm = WorkspaceManager("tenant_a")
        assert wm.get_namespace_prefix("my_kg") == "tenant_a__my_kg__"

    def test_get_namespace_prefix_default(self) -> None:
        wm = WorkspaceManager("default")
        assert wm.get_namespace_prefix("my_kg") == "my_kg__"

    def test_strip_prefix(self) -> None:
        wm = WorkspaceManager("tenant_a")
        assert wm.strip_prefix("tenant_a:my_key") == "my_key"
        assert wm.strip_prefix("other:key") == "other:key"

    def test_strip_prefix_default(self) -> None:
        wm = WorkspaceManager("default")
        assert wm.strip_prefix("my_key") == "my_key"

    def test_to_config_dict(self) -> None:
        wm = WorkspaceManager("tenant_a")
        d = wm.to_config_dict()
        assert d["workspace_id"] == "tenant_a"
        assert d["workspace_enabled"] is True
        assert d["workspace_isolation_mode"] == "prefix"

    def test_repr(self) -> None:
        wm = WorkspaceManager("tenant_a")
        r = repr(wm)
        assert "tenant_a" in r
        assert "WorkspaceManager" in r


# ── Convenience Function Tests ─────────────────────────────────────


class TestConvenienceFunctions:
    def test_get_workspace_manager_from_config(self) -> None:
        wm = WorkspaceManager("tenant_x")
        config = {"workspace_manager": wm}
        result = get_workspace_manager(config)
        assert result is wm

    def test_get_workspace_manager_from_keys(self) -> None:
        config = {
            "workspace_id": "tenant_b",
            "workspace_enabled": True,
            "workspace_isolation_mode": "schema",
        }
        wm = get_workspace_manager(config)
        assert wm.workspace_id == "tenant_b"
        assert wm.isolation_mode == "schema"

    def test_get_workspace_manager_defaults(self) -> None:
        wm = get_workspace_manager({})
        assert wm.workspace_id == "default"

    def test_default_workspace_manager(self) -> None:
        wm = default_workspace_manager()
        assert wm.workspace_id == "default"
        assert wm.enabled is False  # default workspace is always disabled


# ── JsonKVStorage Integration Tests ────────────────────────────────


class TestJsonKVStorageWorkspace:
    @pytest.fixture
    def tmp_dir(self) -> str:
        with tempfile.TemporaryDirectory() as d:
            yield d

    def test_json_kv_workspace_isolation(self, tmp_dir: str) -> None:
        """Two workspaces should have separate data files."""
        from aurora_ext.rag.storage.json_kv import JsonKVStorage

        config_a = {
            "working_dir": tmp_dir,
            "workspace_manager": WorkspaceManager("tenant_a"),
        }
        config_b = {
            "working_dir": tmp_dir,
            "workspace_manager": WorkspaceManager("tenant_b"),
        }

        store_a = JsonKVStorage("test_ns", config_a)
        store_b = JsonKVStorage("test_ns", config_b)

        # Different file paths
        assert store_a._file_path != store_b._file_path
        assert "tenant_a" in store_a._file_path
        assert "tenant_b" in store_b._file_path

    def test_json_kv_default_workspace(self, tmp_dir: str) -> None:
        from aurora_ext.rag.storage.json_kv import JsonKVStorage

        config = {
            "working_dir": tmp_dir,
            "workspace_manager": WorkspaceManager("default"),
        }
        store = JsonKVStorage("test_ns", config)
        # Default workspace should not add subdirectory
        assert store._file_path == os.path.join(tmp_dir, "test_ns.json")

    @pytest.mark.asyncio
    async def test_json_kv_data_isolation(self, tmp_dir: str) -> None:
        """Data written by one workspace should not be visible to another."""
        from aurora_ext.rag.storage.json_kv import JsonKVStorage

        config_a = {
            "working_dir": tmp_dir,
            "workspace_manager": WorkspaceManager("tenant_a"),
        }
        config_b = {
            "working_dir": tmp_dir,
            "workspace_manager": WorkspaceManager("tenant_b"),
        }

        store_a = JsonKVStorage("test_ns", config_a)
        store_b = JsonKVStorage("test_ns", config_b)

        await store_a.upsert({"key1": {"value": "from_a"}})
        await store_b.upsert({"key1": {"value": "from_b"}})

        result_a = await store_a.get_by_id("key1")
        result_b = await store_b.get_by_id("key1")

        assert result_a is not None
        assert result_b is not None
        assert result_a["value"] == "from_a"
        assert result_b["value"] == "from_b"

        # Verify keys are isolated
        keys_a = await store_a.all_keys()
        keys_b = await store_b.all_keys()
        assert "key1" in keys_a
        assert "key1" in keys_b


# ── RedisKVStorage Unit Tests (mocked) ────────────────────────────


class TestRedisKVStorageWorkspace:
    def test_redis_key_prefix_with_workspace(self) -> None:
        """Verify Redis key includes workspace prefix."""
        wm = WorkspaceManager("tenant_a")
        # Simulate what RedisKVStorage does
        prefix = f"aurora_kv:my_ns:"
        key = wm.get_redis_key("aurora_kv:my_ns", "doc_1")
        assert key.startswith("tenant_a:")
        assert "doc_1" in key

    def test_redis_key_prefix_default_workspace(self) -> None:
        wm = WorkspaceManager("default")
        key = wm.get_redis_key("aurora_kv:my_ns", "doc_1")
        assert key == "aurora_kv:my_ns:doc_1"
        assert "default:" not in key


# ── ChromaVectorStorage Unit Tests (mocked) ───────────────────────


class TestChromaVectorStorageWorkspace:
    def test_chroma_collection_name_with_workspace(self) -> None:
        wm = WorkspaceManager("tenant_a")
        collection_name = wm.get_collection_name("chunks")
        assert collection_name == "tenant_a_chunks"

    def test_chroma_collection_name_default(self) -> None:
        wm = WorkspaceManager("default")
        collection_name = wm.get_collection_name("chunks")
        assert collection_name == "chunks"


# ── Neo4jGraphStorage Unit Tests (mocked) ─────────────────────────


class TestNeo4jWorkspace:
    def test_neo4j_labels_with_workspace(self) -> None:
        wm = WorkspaceManager("tenant_a")
        assert wm.get_node_label("Entity") == "tenant_a_Entity"
        assert wm.get_edge_type("RELATED") == "tenant_a_RELATED"

    def test_neo4j_namespace_prefix(self) -> None:
        wm = WorkspaceManager("tenant_a")
        prefix = wm.get_namespace_prefix("my_graph")
        assert prefix == "tenant_a__my_graph__"

    def test_neo4j_labels_default(self) -> None:
        wm = WorkspaceManager("default")
        assert wm.get_node_label("Entity") == "Entity"
        assert wm.get_edge_type("RELATED") == "RELATED"


# ── StorageFactory Integration Tests ───────────────────────────────


class TestStorageFactoryWorkspace:
    def test_factory_passes_workspace(self) -> None:
        """StorageFactory.create should pass workspace in config."""
        from aurora_ext.rag.storage.factory import StorageFactory
        from aurora_ext.rag.storage.workspace import WorkspaceManager

        wm = WorkspaceManager("tenant_a")
        config = {
            "working_dir": "/tmp/test_ws_factory",
            "workspace_manager": wm,
        }

        store = StorageFactory.create("kv", "json", "test_ns", config)
        assert "tenant_a" in store._file_path

    def test_factory_without_workspace(self) -> None:
        from aurora_ext.rag.storage.factory import StorageFactory

        config = {"working_dir": "/tmp/test_no_ws"}
        store = StorageFactory.create("kv", "json", "test_ns", config)
        assert "tenant_a" not in store._file_path
        assert store._file_path == "/tmp/test_no_ws/test_ns.json"


# ── Cross-Workspace Isolation Test ─────────────────────────────────


class TestCrossWorkspaceIsolation:
    @pytest.fixture
    def tmp_dir(self) -> str:
        with tempfile.TemporaryDirectory() as d:
            yield d

    @pytest.mark.asyncio
    async def test_workspace_switch(self, tmp_dir: str) -> None:
        """Switching workspace should give a clean slate."""
        from aurora_ext.rag.storage.json_kv import JsonKVStorage

        config_1 = {
            "working_dir": tmp_dir,
            "workspace_manager": WorkspaceManager("ws_one"),
        }
        config_2 = {
            "working_dir": tmp_dir,
            "workspace_manager": WorkspaceManager("ws_two"),
        }

        store_1 = JsonKVStorage("shared_ns", config_1)
        store_2 = JsonKVStorage("shared_ns", config_2)

        await store_1.upsert({"doc": {"content": "workspace 1 data"}})
        await store_2.upsert({"doc": {"content": "workspace 2 data"}})

        r1 = await store_1.get_by_id("doc")
        r2 = await store_2.get_by_id("doc")

        assert r1 is not None and r1["content"] == "workspace 1 data"
        assert r2 is not None and r2["content"] == "workspace 2 data"

    @pytest.mark.asyncio
    async def test_workspace_delete_cleanup(self, tmp_dir: str) -> None:
        """Deleting workspace data should not affect other workspaces."""
        from aurora_ext.rag.storage.json_kv import JsonKVStorage

        config_a = {
            "working_dir": tmp_dir,
            "workspace_manager": WorkspaceManager("ws_alpha"),
        }
        config_b = {
            "working_dir": tmp_dir,
            "workspace_manager": WorkspaceManager("ws_beta"),
        }

        store_a = JsonKVStorage("ns", config_a)
        store_b = JsonKVStorage("ns", config_b)

        await store_a.upsert({"k": {"v": "alpha"}})
        await store_b.upsert({"k": {"v": "beta"}})

        # Drop workspace A
        await store_a.drop()

        # A should be empty, B should be intact
        assert await store_a.all_keys() == []
        result_b = await store_b.get_by_id("k")
        assert result_b is not None
        assert result_b["v"] == "beta"


# ── NetworkXGraphStorage Workspace Test ────────────────────────────


class TestNetworkXWorkspace:
    def test_networkx_file_path_with_workspace(self) -> None:
        """NetworkX should save to workspace subdirectory."""
        wm = WorkspaceManager("tenant_a")
        path = wm.get_file_path("/data/rag", "graph.graphml")
        assert path == "/data/rag/tenant_a/graph.graphml"

    def test_networkx_file_path_default(self) -> None:
        wm = WorkspaceManager("default")
        path = wm.get_file_path("/data/rag", "graph.graphml")
        assert path == "/data/rag/graph.graphml"


# ── Milvus Collection Name Test ────────────────────────────────────


class TestMilvusWorkspace:
    def test_milvus_collection_name(self) -> None:
        wm = WorkspaceManager("tenant_a")
        name = wm.get_collection_name("aurora_chunks")
        assert name == "tenant_a_aurora_chunks"

    def test_milvus_collection_name_default(self) -> None:
        wm = WorkspaceManager("default")
        name = wm.get_collection_name("aurora_chunks")
        assert name == "aurora_chunks"


# ── PostgreSQL Workspace Tests ─────────────────────────────────────


class TestPostgresWorkspace:
    def test_postgres_namespace_prefix(self) -> None:
        """PostgreSQL KV uses workspace-prefixed namespace."""
        wm = WorkspaceManager("tenant_a")
        namespaced = wm.get_namespaced_key("my_namespace")
        assert namespaced == "tenant_a:my_namespace"

    def test_postgres_schema_mode(self) -> None:
        wm = WorkspaceManager("tenant_a", isolation_mode="schema")
        schema = wm.get_schema_name()
        assert schema == "ws_tenant_a"

    def test_postgres_table_prefix(self) -> None:
        wm = WorkspaceManager("tenant_a")
        table = wm.get_table_name("aurora_kv")
        assert table == "tenant_a_aurora_kv"
