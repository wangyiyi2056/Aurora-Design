"""Context builder — assemble entities, relations, chunks into LLM prompt.

Migrated from LightRAG ``operate.py`` ``_build_query_context()``
and ``_build_context_str()``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional

from aurora_ext.rag.extraction.prompts import PROMPTS


@dataclass
class QueryContext:
    """Assembled query context ready for LLM consumption."""

    entities: list[dict[str, Any]] = field(default_factory=list)
    relationships: list[dict[str, Any]] = field(default_factory=list)
    chunks: list[dict[str, Any]] = field(default_factory=list)
    references: list[dict[str, Any]] = field(default_factory=list)
    is_kg_mode: bool = True


class ContextBuilder:
    """Build LLM-ready context from retrieval results."""

    def build(
        self,
        entities: list[dict[str, Any]],
        relationships: list[dict[str, Any]],
        chunks: list[dict[str, Any]],
        is_kg_mode: bool = True,
        include_references: bool = True,
    ) -> QueryContext:
        """Assemble a complete query context.

        Assigns ``reference_id`` to chunks and builds the reference list.
        """
        references: list[dict[str, Any]] = []
        seen_files: set[str] = set()

        for i, chunk in enumerate(chunks):
            ref_id = str(i + 1)
            chunk["reference_id"] = ref_id
            file_path = chunk.get("file_path", "")
            if file_path and file_path not in seen_files:
                seen_files.add(file_path)
                references.append({
                    "reference_id": ref_id,
                    "file_path": file_path,
                })

        return QueryContext(
            entities=entities,
            relationships=relationships,
            chunks=chunks,
            references=references,
            is_kg_mode=is_kg_mode,
        )

    def format_context(self, ctx: QueryContext) -> str:
        """Format the context into a string for the LLM prompt."""
        if ctx.is_kg_mode:
            return self._format_kg_context(ctx)
        return self._format_naive_context(ctx)

    def _format_kg_context(self, ctx: QueryContext) -> str:
        entities_str = json.dumps(
            [
                {
                    "entity_name": e.get("entity_name", e.get("id", "")),
                    "entity_type": e.get("entity_type", ""),
                    "description": e.get("description", ""),
                }
                for e in ctx.entities
            ],
            ensure_ascii=False,
            indent=2,
        )

        relations_str = json.dumps(
            [
                {
                    "source": r.get("source_entity", r.get("src_id", "")),
                    "target": r.get("target_entity", r.get("tgt_id", "")),
                    "keywords": r.get("keywords", r.get("relationship_keywords", "")),
                    "description": r.get("description", r.get("relationship_description", "")),
                }
                for r in ctx.relationships
            ],
            ensure_ascii=False,
            indent=2,
        )

        text_chunks_str = json.dumps(
            [
                {
                    "reference_id": c.get("reference_id", ""),
                    "content": c.get("content", ""),
                }
                for c in ctx.chunks
            ],
            ensure_ascii=False,
            indent=2,
        )

        reference_list_str = "\n".join(
            f"[{r['reference_id']}] {r['file_path']}"
            for r in ctx.references
        )

        return PROMPTS["kg_query_context"].format(
            entities_str=entities_str,
            relations_str=relations_str,
            text_chunks_str=text_chunks_str,
            reference_list_str=reference_list_str,
        )

    def _format_naive_context(self, ctx: QueryContext) -> str:
        text_chunks_str = json.dumps(
            [
                {
                    "reference_id": c.get("reference_id", ""),
                    "content": c.get("content", ""),
                }
                for c in ctx.chunks
            ],
            ensure_ascii=False,
            indent=2,
        )

        reference_list_str = "\n".join(
            f"[{r['reference_id']}] {r['file_path']}"
            for r in ctx.references
        )

        return PROMPTS["naive_query_context"].format(
            text_chunks_str=text_chunks_str,
            reference_list_str=reference_list_str,
        )
