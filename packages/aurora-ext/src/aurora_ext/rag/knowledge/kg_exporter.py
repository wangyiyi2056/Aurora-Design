"""Knowledge graph data export in multiple formats.

Supports CSV, Excel (xlsx), Markdown, and TXT export with optional
vector embedding inclusion and selective entity/relationship filtering.
"""

from __future__ import annotations

import csv
import enum
import io
import logging
from dataclasses import dataclass, field
from typing import Any

from aurora_ext.rag.storage.base import BaseGraphStorage, BaseVectorStorage

logger = logging.getLogger(__name__)

GRAPH_FIELD_SEP = "<SEP>"


# ── Types ────────────────────────────────────────────────────────────


class ExportFormat(str, enum.Enum):
    """Supported export file formats."""

    CSV = "csv"
    EXCEL = "excel"
    MARKDOWN = "markdown"
    TXT = "txt"


class ExportScope(str, enum.Enum):
    """What to include in the export."""

    ALL = "all"
    ENTITIES_ONLY = "entities"
    RELATIONSHIPS_ONLY = "relationships"


@dataclass(frozen=True)
class ExportOptions:
    """Configuration for a KG export operation."""

    format: ExportFormat = ExportFormat.CSV
    scope: ExportScope = ExportScope.ALL
    include_embeddings: bool = False
    entity_filter: list[str] = field(default_factory=list)
    max_entities: int = 0
    max_relationships: int = 0

    @property
    def mime_type(self) -> str:
        mapping = {
            ExportFormat.CSV: "text/csv",
            ExportFormat.EXCEL: (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
            ExportFormat.MARKDOWN: "text/markdown",
            ExportFormat.TXT: "text/plain",
        }
        return mapping[self.format]

    @property
    def file_extension(self) -> str:
        mapping = {
            ExportFormat.CSV: ".csv",
            ExportFormat.EXCEL: ".xlsx",
            ExportFormat.MARKDOWN: ".md",
            ExportFormat.TXT: ".txt",
        }
        return mapping[self.format]


@dataclass(frozen=True)
class ExportResult:
    """The result of an export operation."""

    content: bytes
    filename: str
    mime_type: str
    entity_count: int
    relationship_count: int

    @property
    def total_items(self) -> int:
        return self.entity_count + self.relationship_count


# ── Exporter ─────────────────────────────────────────────────────────


class KGExporter:
    """Export knowledge graph data in various formats.

    Parameters
    ----------
    graph_storage:
        Graph storage backend to read entities and relationships from.
    vector_storage:
        Optional vector storage for including embedding data.
    """

    def __init__(
        self,
        graph_storage: BaseGraphStorage,
        vector_storage: BaseVectorStorage | None = None,
    ) -> None:
        self._graph = graph_storage
        self._vector = vector_storage

    async def export(
        self,
        options: ExportOptions,
        kb_name: str = "",
    ) -> ExportResult:
        """Export KG data according to the given options.

        Parameters
        ----------
        options:
            Export configuration (format, scope, filters).
        kb_name:
            Knowledge base name (reserved for multi-KB scoping).

        Returns
        -------
        ExportResult
            Binary content, filename, MIME type, and counts.
        """
        nodes, edges = await self._fetch_data(options)

        # Optionally enrich with embedding data
        embeddings_map: dict[str, list[float]] = {}
        if options.include_embeddings and self._vector is not None:
            embeddings_map = await self._fetch_embeddings(nodes)

        # Generate content in the requested format
        content = await self._render(
            options.format, nodes, edges, embeddings_map
        )

        filename = f"kg_export_{kb_name or 'data'}{options.file_extension}"

        return ExportResult(
            content=content,
            filename=filename,
            mime_type=options.mime_type,
            entity_count=len(nodes),
            relationship_count=len(edges),
        )

    # ── Data fetching ─────────────────────────────────────────────

    async def _fetch_data(
        self, options: ExportOptions
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Fetch nodes and edges from graph storage, applying filters."""
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []

        include_entities = options.scope in (
            ExportScope.ALL,
            ExportScope.ENTITIES_ONLY,
        )
        include_relationships = options.scope in (
            ExportScope.ALL,
            ExportScope.RELATIONSHIPS_ONLY,
        )

        if include_entities:
            all_nodes = await self._graph.get_all_nodes()
            if options.entity_filter:
                filter_set = {f.lower() for f in options.entity_filter}
                nodes = [
                    n
                    for n in all_nodes
                    if (
                        n.get("entity_name", n.get("id", "")).lower()
                        in filter_set
                    )
                    or (n.get("id", "").lower() in filter_set)
                ]
            else:
                nodes = all_nodes

            if options.max_entities > 0:
                nodes = nodes[: options.max_entities]

        if include_relationships:
            all_edges = await self._graph.get_all_edges()

            if options.entity_filter:
                filter_set = {f.lower() for f in options.entity_filter}
                edges = [
                    e
                    for e in all_edges
                    if e.get("src_id", e.get("source_id", "")).lower()
                    in filter_set
                    or e.get("tgt_id", e.get("target_id", "")).lower()
                    in filter_set
                ]
            else:
                edges = all_edges

            if options.max_relationships > 0:
                edges = edges[: options.max_relationships]

        return nodes, edges

    async def _fetch_embeddings(
        self, nodes: list[dict[str, Any]]
    ) -> dict[str, list[float]]:
        """Fetch embedding vectors for the given nodes."""
        if self._vector is None:
            return {}

        result: dict[str, list[float]] = {}
        node_ids = [
            n.get("entity_name", n.get("id", "")) for n in nodes
        ]

        # Use query to retrieve stored vectors
        for nid in node_ids:
            if not nid:
                continue
            try:
                hits = await self._vector.query(nid, top_k=1)
                if hits and hits[0].get("__vector__"):
                    result[nid] = hits[0]["__vector__"]
            except Exception:
                # Skip nodes with no stored embeddings
                pass

        return result

    # ── Rendering ─────────────────────────────────────────────────

    async def _render(
        self,
        fmt: ExportFormat,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        embeddings_map: dict[str, list[float]],
    ) -> bytes:
        """Render nodes and edges into the target format bytes."""
        if fmt == ExportFormat.CSV:
            return self._render_csv(nodes, edges, embeddings_map)
        elif fmt == ExportFormat.EXCEL:
            return self._render_excel(nodes, edges, embeddings_map)
        elif fmt == ExportFormat.MARKDOWN:
            return self._render_markdown(nodes, edges, embeddings_map)
        elif fmt == ExportFormat.TXT:
            return self._render_txt(nodes, edges, embeddings_map)
        else:
            raise ValueError(f"Unsupported export format: {fmt}")

    def _render_csv(
        self,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        embeddings_map: dict[str, list[float]],
    ) -> bytes:
        """Render as CSV with separate entities and relationships sections."""
        output = io.StringIO()
        writer = csv.writer(output)

        if nodes:
            writer.writerow(["# ENTITIES"])
            headers = ["entity_name", "entity_type", "description", "source_id", "weight"]
            if embeddings_map:
                headers.append("embedding_dim")
            writer.writerow(headers)

            for node in nodes:
                name = node.get("entity_name", node.get("id", ""))
                row = [
                    name,
                    node.get("entity_type", ""),
                    self._clean_field(node.get("description", "")),
                    node.get("source_id", ""),
                    node.get("weight", 1.0),
                ]
                if embeddings_map:
                    vec = embeddings_map.get(name)
                    row.append(len(vec) if vec else 0)
                writer.writerow(row)

            writer.writerow([])

        if edges:
            writer.writerow(["# RELATIONSHIPS"])
            writer.writerow([
                "source", "target", "keywords", "description",
                "source_id", "weight",
            ])

            for edge in edges:
                writer.writerow([
                    edge.get("src_id", edge.get("source_id", "")),
                    edge.get("tgt_id", edge.get("target_id", "")),
                    edge.get("keywords", ""),
                    self._clean_field(edge.get("description", "")),
                    edge.get("source_id", ""),
                    edge.get("weight", 1.0),
                ])

        return output.getvalue().encode("utf-8")

    def _render_excel(
        self,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        embeddings_map: dict[str, list[float]],
    ) -> bytes:
        """Render as Excel with separate sheets for entities and relationships."""
        try:
            import openpyxl
        except ImportError:
            logger.warning(
                "openpyxl not installed; falling back to CSV for Excel export"
            )
            return self._render_csv(nodes, edges, embeddings_map)

        wb = openpyxl.Workbook()

        # Entities sheet
        ws_entities = wb.active
        ws_entities.title = "Entities"
        headers = ["Entity Name", "Type", "Description", "Source ID", "Weight"]
        if embeddings_map:
            headers.append("Embedding Dim")
        ws_entities.append(headers)

        for node in nodes:
            name = node.get("entity_name", node.get("id", ""))
            row = [
                name,
                node.get("entity_type", ""),
                self._clean_field(node.get("description", "")),
                node.get("source_id", ""),
                node.get("weight", 1.0),
            ]
            if embeddings_map:
                vec = embeddings_map.get(name)
                row.append(len(vec) if vec else 0)
            ws_entities.append(row)

        # Relationships sheet
        ws_edges = wb.create_sheet("Relationships")
        ws_edges.append([
            "Source", "Target", "Keywords", "Description",
            "Source ID", "Weight",
        ])

        for edge in edges:
            ws_edges.append([
                edge.get("src_id", edge.get("source_id", "")),
                edge.get("tgt_id", edge.get("target_id", "")),
                edge.get("keywords", ""),
                self._clean_field(edge.get("description", "")),
                edge.get("source_id", ""),
                edge.get("weight", 1.0),
            ])

        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    def _render_markdown(
        self,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        embeddings_map: dict[str, list[float]],
    ) -> bytes:
        """Render as a Markdown document with tables."""
        lines: list[str] = ["# Knowledge Graph Export\n"]

        if nodes:
            lines.append("## Entities\n")
            if embeddings_map:
                lines.append(
                    "| Name | Type | Description | Weight | Embedding |"
                )
                lines.append("|------|------|-------------|--------|-----------|")
                for node in nodes:
                    name = node.get("entity_name", node.get("id", ""))
                    vec = embeddings_map.get(name)
                    emb_str = f"{len(vec)}-dim" if vec else "N/A"
                    lines.append(
                        f"| {self._md_escape(name)} "
                        f"| {self._md_escape(node.get('entity_type', ''))} "
                        f"| {self._md_escape(self._clean_field(node.get('description', '')))} "
                        f"| {node.get('weight', 1.0)} "
                        f"| {emb_str} |"
                    )
            else:
                lines.append("| Name | Type | Description | Weight |")
                lines.append("|------|------|-------------|--------|")
                for node in nodes:
                    name = node.get("entity_name", node.get("id", ""))
                    lines.append(
                        f"| {self._md_escape(name)} "
                        f"| {self._md_escape(node.get('entity_type', ''))} "
                        f"| {self._md_escape(self._clean_field(node.get('description', '')))} "
                        f"| {node.get('weight', 1.0)} |"
                    )

            lines.append("")

        if edges:
            lines.append("## Relationships\n")
            lines.append("| Source | Target | Keywords | Description | Weight |")
            lines.append("|--------|--------|----------|-------------|--------|")

            for edge in edges:
                src = edge.get("src_id", edge.get("source_id", ""))
                tgt = edge.get("tgt_id", edge.get("target_id", ""))
                lines.append(
                    f"| {self._md_escape(src)} "
                    f"| {self._md_escape(tgt)} "
                    f"| {self._md_escape(edge.get('keywords', ''))} "
                    f"| {self._md_escape(self._clean_field(edge.get('description', '')))} "
                    f"| {edge.get('weight', 1.0)} |"
                )

            lines.append("")

        if not nodes and not edges:
            lines.append("*No data to export.*\n")

        return "\n".join(lines).encode("utf-8")

    def _render_txt(
        self,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        embeddings_map: dict[str, list[float]],
    ) -> bytes:
        """Render as plain text."""
        lines: list[str] = ["=== Knowledge Graph Export ===", ""]

        if nodes:
            lines.append(f"--- Entities ({len(nodes)}) ---")
            for node in nodes:
                name = node.get("entity_name", node.get("id", ""))
                etype = node.get("entity_type", "")
                desc = self._clean_field(node.get("description", ""))
                weight = node.get("weight", 1.0)
                lines.append(f"  [{etype}] {name} (weight={weight})")
                if desc:
                    lines.append(f"    {desc[:200]}")
                if embeddings_map:
                    vec = embeddings_map.get(name)
                    if vec:
                        lines.append(f"    embedding: {len(vec)}-dim")

            lines.append("")

        if edges:
            lines.append(f"--- Relationships ({len(edges)}) ---")
            for edge in edges:
                src = edge.get("src_id", edge.get("source_id", ""))
                tgt = edge.get("tgt_id", edge.get("target_id", ""))
                kw = edge.get("keywords", "")
                desc = self._clean_field(edge.get("description", ""))
                weight = edge.get("weight", 1.0)
                lines.append(f"  {src} --[{kw}]--> {tgt} (weight={weight})")
                if desc:
                    lines.append(f"    {desc[:200]}")

            lines.append("")

        if not nodes and not edges:
            lines.append("No data to export.")

        return "\n".join(lines).encode("utf-8")

    # ── Helpers ───────────────────────────────────────────────────

    @staticmethod
    def _clean_field(value: str) -> str:
        """Replace field separators with readable delimiters for export."""
        if not value:
            return ""
        return value.replace(GRAPH_FIELD_SEP, " | ")

    @staticmethod
    def _md_escape(text: str) -> str:
        """Escape pipe characters for Markdown tables."""
        if not text:
            return ""
        return text.replace("|", "\\|").replace("\n", " ")
