"""Unit tests for advanced knowledge graph management features.

Tests cover:
- GraphManager: entity merge with concatenate, keep_first, join_unique strategies
- KnowledgeKGInjector: full import with chunks, entities, relationships
- KGExporter: CSV, Excel, Markdown, TXT formats with filters
"""

from __future__ import annotations

from typing import Any, Optional
from unittest.mock import AsyncMock

import pytest

from aurora_ext.rag.knowledge.graph_manager import (
    GraphManager,
    MergeResult,
    MergeStrategy,
)
from aurora_ext.rag.knowledge.custom_kg_injector import (
    FullImportData,
    FullInjectionStats,
    ImportChunk,
    KnowledgeKGInjector,
)
from aurora_ext.rag.knowledge.kg_exporter import (
    ExportFormat,
    ExportOptions,
    ExportResult,
    ExportScope,
    KGExporter,
)
from aurora_ext.rag.injection.custom_kg_injector import (
    ImportEntity,
    ImportRelationship,
)


# ── Fake graph storage ───────────────────────────────────────────────


class FakeGraphStorage:
    """In-memory graph storage for testing."""

    def __init__(self) -> None:
        self.nodes: dict[str, dict[str, Any]] = {}
        self.edges: dict[tuple[str, str], dict[str, Any]] = {}

    async def has_node(self, node_id: str) -> bool:
        return node_id in self.nodes

    async def get_node(self, node_id: str) -> Optional[dict[str, Any]]:
        return self.nodes.get(node_id)

    async def upsert_node(self, node_id: str, node_data: dict[str, Any]) -> None:
        self.nodes[node_id] = node_data

    async def delete_node(self, node_id: str) -> None:
        self.nodes.pop(node_id, None)
        # Remove associated edges
        to_remove = [
            (s, t) for s, t in self.edges if s == node_id or t == node_id
        ]
        for key in to_remove:
            del self.edges[key]

    async def get_node_edges(self, node_id: str) -> list[tuple[str, str]]:
        return [
            (s, t) for s, t in self.edges if s == node_id or t == node_id
        ]

    async def has_edge(self, source_id: str, target_id: str) -> bool:
        return (source_id, target_id) in self.edges

    async def get_edge(
        self, source_id: str, target_id: str
    ) -> Optional[dict[str, Any]]:
        return self.edges.get((source_id, target_id))

    async def upsert_edge(
        self, source_id: str, target_id: str, edge_data: dict[str, Any]
    ) -> None:
        self.edges[(source_id, target_id)] = edge_data

    async def delete_edge(self, source_id: str, target_id: str) -> None:
        self.edges.pop((source_id, target_id), None)

    async def get_all_nodes(self) -> list[dict[str, Any]]:
        result = []
        for nid, data in self.nodes.items():
            node = dict(data)
            node["id"] = nid
            result.append(node)
        return result

    async def get_all_edges(self) -> list[dict[str, Any]]:
        result = []
        for (src, tgt), data in self.edges.items():
            edge = dict(data)
            edge["src_id"] = src
            edge["tgt_id"] = tgt
            result.append(edge)
        return result

    async def get_neighbors(self, node_id: str) -> list[str]:
        result = []
        for s, t in self.edges:
            if s == node_id:
                result.append(t)
            elif t == node_id:
                result.append(s)
        return result


class FakeVectorStorage:
    """In-memory vector storage for testing."""

    def __init__(self) -> None:
        self.data: dict[str, dict[str, Any]] = {}

    async def upsert(self, data: dict[str, dict[str, Any]]) -> None:
        self.data.update(data)

    async def query(
        self, query: str, top_k: int, cosine_threshold: float = 0.0
    ) -> list[dict[str, Any]]:
        return []

    async def delete(self, ids: list[str]) -> None:
        for i in ids:
            self.data.pop(i, None)


class FakeKVStorage:
    """In-memory KV storage for testing."""

    def __init__(self) -> None:
        self.data: dict[str, dict[str, Any]] = {}

    async def all_keys(self) -> list[str]:
        return list(self.data.keys())

    async def get_by_id(self, key: str) -> Optional[dict[str, Any]]:
        return self.data.get(key)

    async def get_by_ids(
        self, keys: list[str]
    ) -> list[Optional[dict[str, Any]]]:
        return [self.data.get(k) for k in keys]

    async def upsert(self, data: dict[str, dict[str, Any]]) -> None:
        self.data.update(data)

    async def delete(self, keys: list[str]) -> None:
        for k in keys:
            self.data.pop(k, None)


# ── Helpers ──────────────────────────────────────────────────────────


def _make_graph_with_entities() -> FakeGraphStorage:
    """Create a graph with three entities and two edges."""
    g = FakeGraphStorage()
    g.nodes["Alice"] = {
        "entity_name": "Alice",
        "entity_type": "Person",
        "description": "Software engineer",
        "source_id": "doc1",
        "weight": 1.0,
    }
    g.nodes["Bob"] = {
        "entity_name": "Bob",
        "entity_type": "Person",
        "description": "Data scientist",
        "source_id": "doc2",
        "weight": 1.0,
    }
    g.nodes["Carol"] = {
        "entity_name": "Carol",
        "entity_type": "Person",
        "description": "Product manager",
        "source_id": "doc3",
        "weight": 1.0,
    }
    g.edges[("Alice", "Bob")] = {
        "src_id": "Alice",
        "tgt_id": "Bob",
        "keywords": "colleague",
        "description": "Work together",
        "source_id": "doc1",
        "weight": 1.0,
    }
    g.edges[("Bob", "Carol")] = {
        "src_id": "Bob",
        "tgt_id": "Carol",
        "keywords": "friend",
        "description": "Friends outside work",
        "source_id": "doc2",
        "weight": 1.0,
    }
    return g


# ═══════════════════════════════════════════════════════════════════════
# GraphManager Tests
# ═══════════════════════════════════════════════════════════════════════


class TestGraphManager:
    """Tests for entity merge operations."""

    # ── Merge with JOIN_UNIQUE ──────────────────────────────────────

    @pytest.mark.asyncio
    async def test_merge_join_unique_combines_descriptions(self):
        """Join unique should add new description parts without duplicates."""
        graph = _make_graph_with_entities()
        # Give Alice a description that partially overlaps with Bob
        graph.nodes["Alice"]["description"] = "Software engineer<SEP>Team lead"
        graph.nodes["Bob"]["description"] = "Data scientist<SEP>Software engineer"

        manager = GraphManager(graph_storage=graph)
        result = await manager.merge_entities(
            target_entity="Alice",
            source_entities=["Bob"],
            strategy=MergeStrategy.JOIN_UNIQUE,
        )

        assert result.success
        assert result.merged_count == 1
        assert "Bob" in result.deleted_entities
        assert "Bob" not in graph.nodes

        alice_desc = graph.nodes["Alice"]["description"]
        assert "Software engineer" in alice_desc
        assert "Team lead" in alice_desc
        assert "Data scientist" in alice_desc
        # "Software engineer" should NOT be duplicated
        assert alice_desc.count("Software engineer") == 1

    @pytest.mark.asyncio
    async def test_merge_join_unique_migrates_edges(self):
        """Edges from source entity should be re-wired to target."""
        graph = _make_graph_with_entities()
        manager = GraphManager(graph_storage=graph)

        result = await manager.merge_entities(
            target_entity="Alice",
            source_entities=["Bob"],
            strategy=MergeStrategy.JOIN_UNIQUE,
        )

        assert result.migrated_edges > 0
        # Bob->Carol edge should become Alice->Carol
        assert ("Alice", "Carol") in graph.edges
        assert ("Bob", "Carol") not in graph.edges

    @pytest.mark.asyncio
    async def test_merge_skips_self_loop(self):
        """If merging creates a self-loop, the edge should be dropped."""
        graph = _make_graph_with_entities()
        manager = GraphManager(graph_storage=graph)

        # Alice->Bob would become Alice->Alice (self-loop)
        result = await manager.merge_entities(
            target_entity="Alice",
            source_entities=["Bob"],
            strategy=MergeStrategy.JOIN_UNIQUE,
        )

        assert result.success
        assert ("Alice", "Alice") not in graph.edges

    # ── Merge with CONCATENATE ──────────────────────────────────────

    @pytest.mark.asyncio
    async def test_merge_concatenate_joins_all_values(self):
        """Concatenate should join all description parts unconditionally."""
        graph = _make_graph_with_entities()
        graph.nodes["Alice"]["description"] = "Engineer"
        graph.nodes["Bob"]["description"] = "Engineer"

        manager = GraphManager(graph_storage=graph)
        result = await manager.merge_entities(
            target_entity="Alice",
            source_entities=["Bob"],
            strategy=MergeStrategy.CONCATENATE,
        )

        assert result.success
        alice_desc = graph.nodes["Alice"]["description"]
        # Both "Engineer" values should be present (duplicated)
        assert alice_desc.count("Engineer") == 2

    # ── Merge with KEEP_FIRST ───────────────────────────────────────

    @pytest.mark.asyncio
    async def test_merge_keep_first_preserves_target(self):
        """Keep first should preserve the target entity's existing values."""
        graph = _make_graph_with_entities()
        graph.nodes["Alice"]["description"] = "Original description"
        graph.nodes["Bob"]["description"] = "New description"

        manager = GraphManager(graph_storage=graph)
        result = await manager.merge_entities(
            target_entity="Alice",
            source_entities=["Bob"],
            strategy=MergeStrategy.KEEP_FIRST,
        )

        assert result.success
        alice_desc = graph.nodes["Alice"]["description"]
        assert alice_desc == "Original description"
        assert "New description" not in alice_desc

    @pytest.mark.asyncio
    async def test_merge_keep_first_fills_empty_fields(self):
        """Keep first should fill in target fields that are empty."""
        graph = _make_graph_with_entities()
        graph.nodes["Alice"]["description"] = ""
        graph.nodes["Bob"]["description"] = "Bob's description"

        manager = GraphManager(graph_storage=graph)
        result = await manager.merge_entities(
            target_entity="Alice",
            source_entities=["Bob"],
            strategy=MergeStrategy.KEEP_FIRST,
        )

        assert result.success
        assert graph.nodes["Alice"]["description"] == "Bob's description"

    # ── Error handling ──────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_merge_nonexistent_target_raises(self):
        """Merging into a nonexistent target should raise ValueError."""
        graph = FakeGraphStorage()
        manager = GraphManager(graph_storage=graph)

        with pytest.raises(ValueError, match="does not exist"):
            await manager.merge_entities(
                target_entity="NonExistent",
                source_entities=["Alice"],
            )

    @pytest.mark.asyncio
    async def test_merge_nonexistent_source_is_skipped(self):
        """Nonexistent source entities should be skipped, not error."""
        graph = _make_graph_with_entities()
        manager = GraphManager(graph_storage=graph)

        result = await manager.merge_entities(
            target_entity="Alice",
            source_entities=["Ghost"],
            strategy=MergeStrategy.JOIN_UNIQUE,
        )

        assert result.success
        assert "Ghost" in result.skipped_entities
        assert result.merged_count == 0

    @pytest.mark.asyncio
    async def test_merge_multiple_sources(self):
        """Merging multiple sources into one target."""
        graph = _make_graph_with_entities()
        manager = GraphManager(graph_storage=graph)

        result = await manager.merge_entities(
            target_entity="Alice",
            source_entities=["Bob", "Carol"],
            strategy=MergeStrategy.JOIN_UNIQUE,
        )

        assert result.success
        assert result.merged_count == 2
        assert "Bob" not in graph.nodes
        assert "Carol" not in graph.nodes
        assert "Alice" in graph.nodes

    @pytest.mark.asyncio
    async def test_merge_increments_weight(self):
        """Merging should accumulate weight values."""
        graph = _make_graph_with_entities()
        manager = GraphManager(graph_storage=graph)

        await manager.merge_entities(
            target_entity="Alice",
            source_entities=["Bob"],
            strategy=MergeStrategy.JOIN_UNIQUE,
        )

        # Alice(1.0) + Bob(1.0) = 2.0
        assert graph.nodes["Alice"]["weight"] == 2.0

    @pytest.mark.asyncio
    async def test_merge_result_to_dict(self):
        """MergeResult.to_dict() should produce a serialisable dict."""
        result = MergeResult(
            target_entity="Alice",
            merged_count=2,
            deleted_entities=["Bob", "Carol"],
            migrated_edges=3,
        )
        d = result.to_dict()
        assert d["target_entity"] == "Alice"
        assert d["merged_count"] == 2
        assert d["success"] is True


# ═══════════════════════════════════════════════════════════════════════
# KnowledgeKGInjector Tests
# ═══════════════════════════════════════════════════════════════════════


class TestKnowledgeKGInjector:
    """Tests for full KG injection with chunks, entities, and relationships."""

    @pytest.mark.asyncio
    async def test_inject_entities_only(self):
        """Inject entities without relationships."""
        graph = FakeGraphStorage()
        injector = KnowledgeKGInjector(graph_storage=graph)

        data = FullImportData(
            entities=[
                ImportEntity(
                    entity_name="Python",
                    entity_type="Language",
                    description="Programming language",
                ),
            ],
        )

        stats = await injector.inject_full(data)
        assert stats.entity_stats.entities_created == 1
        assert "Python" in graph.nodes

    @pytest.mark.asyncio
    async def test_inject_chunks(self):
        """Inject text chunks into KV storage."""
        graph = FakeGraphStorage()
        kv = FakeKVStorage()
        injector = KnowledgeKGInjector(
            graph_storage=graph, chunk_kv=kv
        )

        data = FullImportData(
            chunks=[
                ImportChunk(
                    chunk_id="chunk-1",
                    content="First chunk content",
                    source_id="doc1",
                ),
                ImportChunk(
                    chunk_id="chunk-2",
                    content="Second chunk content",
                    source_id="doc1",
                ),
            ],
        )

        stats = await injector.inject_full(data)
        assert stats.chunks_created == 2
        assert "chunk-1" in kv.data
        assert "chunk-2" in kv.data

    @pytest.mark.asyncio
    async def test_inject_chunks_skip_existing(self):
        """Skip strategy should not overwrite existing chunks."""
        graph = FakeGraphStorage()
        kv = FakeKVStorage()
        kv.data["chunk-1"] = {"content": "Existing content", "source_id": "doc0"}

        injector = KnowledgeKGInjector(graph_storage=graph, chunk_kv=kv)

        from aurora_ext.rag.injection.custom_kg_injector import MergeStrategy

        data = FullImportData(
            chunks=[
                ImportChunk(
                    chunk_id="chunk-1",
                    content="New content",
                    source_id="doc1",
                ),
            ],
        )

        stats = await injector.inject_full(data, strategy=MergeStrategy.SKIP)
        assert stats.chunks_skipped == 1
        assert kv.data["chunk-1"]["content"] == "Existing content"

    @pytest.mark.asyncio
    async def test_inject_full_combined(self):
        """Inject chunks, entities, and relationships together."""
        graph = FakeGraphStorage()
        kv = FakeKVStorage()
        injector = KnowledgeKGInjector(
            graph_storage=graph, chunk_kv=kv
        )

        data = FullImportData(
            chunks=[
                ImportChunk(
                    chunk_id="c1", content="Chunk text", source_id="s1"
                ),
            ],
            entities=[
                ImportEntity(
                    entity_name="Entity1",
                    entity_type="Type1",
                    description="Desc1",
                ),
            ],
            relationships=[
                ImportRelationship(
                    source_entity="Entity1",
                    target_entity="Entity2",
                    description="relates to",
                ),
            ],
        )

        stats = await injector.inject_full(data)
        assert stats.chunks_created == 1
        assert stats.entity_stats.entities_created >= 1
        assert "Entity1" in graph.nodes
        assert "Entity2" in graph.nodes  # Auto-created by relationship

    # ── Parsing ─────────────────────────────────────────────────────

    def test_parse_import_data_full(self):
        """Parse a complete import dict with chunks, entities, relationships."""
        raw = {
            "chunks": [
                {"chunk_id": "c1", "content": "Hello world", "source_id": "doc1"},
            ],
            "entities": [
                {"entity_name": "Python", "entity_type": "Language", "description": "PL"},
            ],
            "relationships": [
                {"source_entity": "Python", "target_entity": "JS", "description": "rival"},
            ],
        }

        data = KnowledgeKGInjector.parse_import_data(raw)
        assert len(data.chunks) == 1
        assert len(data.entities) == 1
        assert len(data.relationships) == 1
        assert not data.is_empty

    def test_parse_import_data_empty(self):
        """Parse an empty import dict."""
        data = KnowledgeKGInjector.parse_import_data({})
        assert data.is_empty

    def test_parse_chunks_skips_invalid(self):
        """Chunks without id or content should be skipped."""
        raw = [
            {"chunk_id": "c1", "content": "Valid"},
            {"chunk_id": "", "content": "No ID"},
            {"chunk_id": "c3", "content": ""},
            {"chunk_id": "c4", "content": "Also valid"},
        ]
        chunks = KnowledgeKGInjector.parse_chunks(raw)
        assert len(chunks) == 2

    def test_parse_yaml_content(self):
        """Parse valid YAML content."""
        yaml_str = """
entities:
  - entity_name: Python
    entity_type: Language
relationships:
  - source_entity: Python
    target_entity: Rust
"""
        raw = KnowledgeKGInjector.parse_yaml_content(yaml_str)
        assert isinstance(raw, dict)
        assert "entities" in raw


# ═══════════════════════════════════════════════════════════════════════
# KGExporter Tests
# ═══════════════════════════════════════════════════════════════════════


class TestKGExporter:
    """Tests for KG data export in multiple formats."""

    @pytest.mark.asyncio
    async def test_export_csv_all(self):
        """Export entities and relationships as CSV."""
        graph = _make_graph_with_entities()
        exporter = KGExporter(graph_storage=graph)

        options = ExportOptions(format=ExportFormat.CSV, scope=ExportScope.ALL)
        result = await exporter.export(options, kb_name="test")

        assert result.mime_type == "text/csv"
        assert result.filename.endswith(".csv")
        assert result.entity_count == 3
        assert result.relationship_count == 2

        content = result.content.decode("utf-8")
        assert "# ENTITIES" in content
        assert "# RELATIONSHIPS" in content
        assert "Alice" in content
        assert "Bob" in content

    @pytest.mark.asyncio
    async def test_export_csv_entities_only(self):
        """Export only entities as CSV."""
        graph = _make_graph_with_entities()
        exporter = KGExporter(graph_storage=graph)

        options = ExportOptions(
            format=ExportFormat.CSV, scope=ExportScope.ENTITIES_ONLY
        )
        result = await exporter.export(options)

        assert result.entity_count == 3
        assert result.relationship_count == 0
        content = result.content.decode("utf-8")
        assert "# ENTITIES" in content
        assert "# RELATIONSHIPS" not in content

    @pytest.mark.asyncio
    async def test_export_csv_relationships_only(self):
        """Export only relationships as CSV."""
        graph = _make_graph_with_entities()
        exporter = KGExporter(graph_storage=graph)

        options = ExportOptions(
            format=ExportFormat.CSV, scope=ExportScope.RELATIONSHIPS_ONLY
        )
        result = await exporter.export(options)

        assert result.entity_count == 0
        assert result.relationship_count == 2

    @pytest.mark.asyncio
    async def test_export_markdown(self):
        """Export as Markdown with tables."""
        graph = _make_graph_with_entities()
        exporter = KGExporter(graph_storage=graph)

        options = ExportOptions(
            format=ExportFormat.MARKDOWN, scope=ExportScope.ALL
        )
        result = await exporter.export(options, kb_name="test")

        assert result.mime_type == "text/markdown"
        assert result.filename.endswith(".md")

        content = result.content.decode("utf-8")
        assert "# Knowledge Graph Export" in content
        assert "## Entities" in content
        assert "## Relationships" in content
        assert "| Alice" in content

    @pytest.mark.asyncio
    async def test_export_txt(self):
        """Export as plain text."""
        graph = _make_graph_with_entities()
        exporter = KGExporter(graph_storage=graph)

        options = ExportOptions(
            format=ExportFormat.TXT, scope=ExportScope.ALL
        )
        result = await exporter.export(options)

        assert result.mime_type == "text/plain"
        assert result.filename.endswith(".txt")

        content = result.content.decode("utf-8")
        assert "=== Knowledge Graph Export ===" in content
        assert "Alice" in content
        assert "Bob" in content

    @pytest.mark.asyncio
    async def test_export_with_entity_filter(self):
        """Export should respect entity filter."""
        graph = _make_graph_with_entities()
        exporter = KGExporter(graph_storage=graph)

        options = ExportOptions(
            format=ExportFormat.CSV,
            scope=ExportScope.ALL,
            entity_filter=["Alice"],
        )
        result = await exporter.export(options)

        assert result.entity_count == 1
        # Alice is in one edge (Alice->Bob), so 1 relationship
        assert result.relationship_count == 1

    @pytest.mark.asyncio
    async def test_export_with_max_limits(self):
        """Export should respect max_entities and max_relationships."""
        graph = _make_graph_with_entities()
        exporter = KGExporter(graph_storage=graph)

        options = ExportOptions(
            format=ExportFormat.CSV,
            scope=ExportScope.ALL,
            max_entities=1,
            max_relationships=1,
        )
        result = await exporter.export(options)

        assert result.entity_count == 1
        assert result.relationship_count == 1

    @pytest.mark.asyncio
    async def test_export_empty_graph(self):
        """Exporting an empty graph should produce valid output."""
        graph = FakeGraphStorage()
        exporter = KGExporter(graph_storage=graph)

        options = ExportOptions(format=ExportFormat.TXT)
        result = await exporter.export(options)

        assert result.entity_count == 0
        assert result.relationship_count == 0
        content = result.content.decode("utf-8")
        assert "No data to export" in content

    @pytest.mark.asyncio
    async def test_export_markdown_empty(self):
        """Markdown export of empty graph should show placeholder."""
        graph = FakeGraphStorage()
        exporter = KGExporter(graph_storage=graph)

        options = ExportOptions(format=ExportFormat.MARKDOWN)
        result = await exporter.export(options)

        content = result.content.decode("utf-8")
        assert "No data to export" in content

    @pytest.mark.asyncio
    async def test_export_options_mime_types(self):
        """ExportOptions should return correct MIME types."""
        assert ExportOptions(format=ExportFormat.CSV).mime_type == "text/csv"
        assert (
            ExportOptions(format=ExportFormat.EXCEL).mime_type
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        assert (
            ExportOptions(format=ExportFormat.MARKDOWN).mime_type
            == "text/markdown"
        )
        assert ExportOptions(format=ExportFormat.TXT).mime_type == "text/plain"

    @pytest.mark.asyncio
    async def test_export_options_file_extensions(self):
        """ExportOptions should return correct file extensions."""
        assert ExportOptions(format=ExportFormat.CSV).file_extension == ".csv"
        assert ExportOptions(format=ExportFormat.EXCEL).file_extension == ".xlsx"
        assert ExportOptions(format=ExportFormat.MARKDOWN).file_extension == ".md"
        assert ExportOptions(format=ExportFormat.TXT).file_extension == ".txt"

    @pytest.mark.asyncio
    async def test_export_cleans_field_separators(self):
        """Export should replace <SEP> with readable delimiters."""
        graph = FakeGraphStorage()
        graph.nodes["TestEntity"] = {
            "entity_name": "TestEntity",
            "entity_type": "Type",
            "description": "Part1<SEP>Part2<SEP>Part3",
            "weight": 1.0,
        }

        exporter = KGExporter(graph_storage=graph)
        options = ExportOptions(format=ExportFormat.TXT)
        result = await exporter.export(options)

        content = result.content.decode("utf-8")
        assert "Part1 | Part2 | Part3" in content
        assert "<SEP>" not in content

    @pytest.mark.asyncio
    async def test_export_result_total_items(self):
        """ExportResult.total_items should sum entities and relationships."""
        result = ExportResult(
            content=b"",
            filename="test.csv",
            mime_type="text/csv",
            entity_count=5,
            relationship_count=3,
        )
        assert result.total_items == 8
