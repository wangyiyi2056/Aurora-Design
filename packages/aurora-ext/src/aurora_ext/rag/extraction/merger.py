"""Entity and relationship merging across chunks.

Migrated from LightRAG ``operate.py`` ``merge_nodes_and_edges()`` and
the ``_merge_nodes_then_upsert`` / ``_merge_edges_then_upsert`` helpers.

The merge logic combines newly extracted items with any previously
accumulated graph data, deduplicating by name (entities) or endpoint
pair (relationships) and accumulating descriptions, source IDs, file
paths, and weights.
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import Any

from aurora_ext.rag.extraction.types import (
    GRAPH_FIELD_SEP,
    ExtractedEntity,
    ExtractedRelationship,
    GraphEntity,
    GraphRelationship,
)

logger = logging.getLogger(__name__)

# ── Default limits ────────────────────────────────────────────────

_DEFAULT_MAX_SOURCE_IDS = 300


# ── Entity merging ────────────────────────────────────────────────


def merge_entities(
    existing: list[GraphEntity],
    new_entities: list[ExtractedEntity],
    chunk_id: str,
    file_path: str,
) -> list[GraphEntity]:
    """Merge newly extracted entities into an existing graph entity list.

    Matching is performed by **case-insensitive** entity name.  When an
    entity already exists:

    * Descriptions are concatenated using :data:`GRAPH_FIELD_SEP`.
    * Source IDs are appended (the new *chunk_id* is added once).
    * File paths are appended similarly.
    * Weight is incremented by ``+1.0`` per occurrence.

    When an entity does not yet exist a fresh :class:`GraphEntity` is
    created with ``weight=1.0``.

    Parameters
    ----------
    existing:
        The current set of graph entities (may be empty).
    new_entities:
        Entities freshly extracted from a single chunk.
    chunk_id:
        Source chunk identifier for provenance.
    file_path:
        Source file path for provenance.

    Returns
    -------
    list[GraphEntity]
        Updated entity list with merged data.
    """
    # Index existing entities by lowercased name for O(1) lookup.
    name_index: dict[str, GraphEntity] = {
        e.entity_name.lower(): e for e in existing
    }

    # Track which types have been seen per entity to pick the majority.
    type_counts: dict[str, Counter[str]] = {}

    result: dict[str, GraphEntity] = {}

    # Seed with existing entities.
    for entity in existing:
        key = entity.entity_name.lower()
        result[key] = entity
        type_counts.setdefault(key, Counter())
        type_counts[key][entity.entity_type] += 1

    # Merge new entities.
    for extracted in new_entities:
        key = extracted.entity_name.lower()
        type_counts.setdefault(key, Counter())
        type_counts[key][extracted.entity_type] += 1

        if key in result:
            merged = result[key]
            merged.description = _append_field(
                merged.description, extracted.entity_description
            )
            merged.source_id = _append_unique_id(merged.source_id, chunk_id)
            merged.file_path = _append_unique_value(merged.file_path, file_path)
            merged.weight += 1.0
        else:
            result[key] = GraphEntity(
                entity_name=extracted.entity_name,
                entity_type=extracted.entity_type,
                description=extracted.entity_description,
                source_id=chunk_id,
                file_path=file_path,
                weight=1.0,
            )

    # Resolve entity type by majority vote across all observations.
    for key, entity in result.items():
        if key in type_counts and type_counts[key]:
            most_common_type = type_counts[key].most_common(1)[0][0]
            entity.entity_type = most_common_type

    return list(result.values())


# ── Relationship merging ──────────────────────────────────────────


def merge_relationships(
    existing: list[GraphRelationship],
    new_rels: list[ExtractedRelationship],
    chunk_id: str,
    file_path: str,
) -> list[GraphRelationship]:
    """Merge newly extracted relationships into an existing graph edge list.

    Matching uses the **sorted** ``(source_entity, target_entity)`` pair
    (case-insensitive) since relationships are treated as undirected.

    When a relationship already exists:

    * Descriptions and keywords are concatenated with
      :data:`GRAPH_FIELD_SEP`.
    * Source IDs and file paths are merged (deduplicated).
    * Weight is incremented by ``+1.0`` per occurrence.

    Parameters
    ----------
    existing:
        The current set of graph relationships (may be empty).
    new_rels:
        Relationships freshly extracted from a single chunk.
    chunk_id:
        Source chunk identifier.
    file_path:
        Source file path.

    Returns
    -------
    list[GraphRelationship]
        Updated relationship list with merged data.
    """

    def _pair_key(src: str, tgt: str) -> str:
        return "||".join(sorted([src.lower(), tgt.lower()]))

    pair_index: dict[str, GraphRelationship] = {}
    for rel in existing:
        pair_index[_pair_key(rel.source_entity, rel.target_entity)] = rel

    result: dict[str, GraphRelationship] = {}

    # Seed with existing relationships.
    for rel in existing:
        key = _pair_key(rel.source_entity, rel.target_entity)
        result[key] = rel

    # Merge new relationships.
    for extracted in new_rels:
        key = _pair_key(extracted.source_entity, extracted.target_entity)

        if key in result:
            merged = result[key]
            merged.description = _append_field(
                merged.description, extracted.relationship_description
            )
            merged.keywords = _merge_keywords(
                merged.keywords, extracted.relationship_keywords
            )
            merged.source_id = _append_unique_id(merged.source_id, chunk_id)
            merged.file_path = _append_unique_value(merged.file_path, file_path)
            merged.weight += 1.0
        else:
            result[key] = GraphRelationship(
                source_entity=extracted.source_entity,
                target_entity=extracted.target_entity,
                keywords=extracted.relationship_keywords,
                description=extracted.relationship_description,
                source_id=chunk_id,
                file_path=file_path,
                weight=1.0,
            )

    return list(result.values())


# ── Source-ID trimming ────────────────────────────────────────────


def limit_source_ids(
    source_ids: str,
    max_ids: int = _DEFAULT_MAX_SOURCE_IDS,
    method: str = "FIFO",
) -> str:
    """Trim a :data:`GRAPH_FIELD_SEP`-delimited source-ID string.

    Parameters
    ----------
    source_ids:
        The delimited string of chunk IDs.
    max_ids:
        Maximum number of IDs to retain.
    method:
        Trimming strategy:

        - ``"FIFO"`` — keep the *most recent* IDs (drop from the front).
        - ``"KEEP"`` — keep the *oldest* IDs (drop from the end).

    Returns
    -------
    str
        The trimmed, re-joined source-ID string.
    """
    if not source_ids:
        return source_ids

    ids = [s for s in source_ids.split(GRAPH_FIELD_SEP) if s]
    if len(ids) <= max_ids:
        return source_ids

    if method.upper() == "KEEP":
        trimmed = ids[:max_ids]
    else:
        # FIFO — keep the newest (last N).
        trimmed = ids[-max_ids:]

    logger.debug(
        "Trimmed source_ids from %d to %d (method=%s).",
        len(ids),
        len(trimmed),
        method,
    )
    return GRAPH_FIELD_SEP.join(trimmed)


# ── Internal helpers ──────────────────────────────────────────────


def _append_field(current: str, new_value: str) -> str:
    """Append *new_value* to *current* using :data:`GRAPH_FIELD_SEP`.

    Duplicate values (exact string match) are skipped to avoid
    description bloat.
    """
    if not new_value:
        return current

    existing_parts = {p.strip() for p in current.split(GRAPH_FIELD_SEP) if p.strip()}
    if new_value.strip() in existing_parts:
        return current

    if current:
        return f"{current}{GRAPH_FIELD_SEP}{new_value}"
    return new_value


def _append_unique_id(current_ids: str, new_id: str) -> str:
    """Append *new_id* to the delimited string if not already present."""
    if not new_id:
        return current_ids

    ids = {s.strip() for s in current_ids.split(GRAPH_FIELD_SEP) if s.strip()}
    if new_id.strip() in ids:
        return current_ids

    if current_ids:
        return f"{current_ids}{GRAPH_FIELD_SEP}{new_id}"
    return new_id


def _append_unique_value(current_values: str, new_value: str) -> str:
    """Append *new_value* to the delimited string if not already present.

    Identical to :func:`_append_unique_id` but named differently for
    readability at the call site (used for file paths).
    """
    return _append_unique_id(current_values, new_value)


def _merge_keywords(current: str, new_keywords: str) -> str:
    """Merge comma-separated keyword strings, deduplicating entries."""
    all_kw: set[str] = set()

    for part in current.split(","):
        stripped = part.strip()
        if stripped:
            all_kw.add(stripped)

    for part in new_keywords.split(","):
        stripped = part.strip()
        if stripped:
            all_kw.add(stripped)

    return ",".join(sorted(all_kw))
