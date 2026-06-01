"""Data types for knowledge graph extraction.

Migrated from LightRAG ``types.py`` and ``operate.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ExtractedEntity:
    """An entity extracted from a text chunk.

    Attributes
    ----------
    entity_name:
        The canonical name of the entity.
    entity_type:
        Classification (Person, Organization, Location, etc.).
    entity_description:
        A description of the entity as found in the source text.
    source_id:
        Chunk ID(s) that mention this entity.
    file_path:
        Source file path(s).
    """

    entity_name: str
    entity_type: str
    entity_description: str
    source_id: str = ""
    file_path: str = ""


@dataclass(frozen=True)
class ExtractedRelationship:
    """A relationship between two entities.

    Attributes
    ----------
    source_entity:
        Name of the source entity.
    target_entity:
        Name of the target entity.
    relationship_keywords:
        Keywords describing the relationship type.
    relationship_description:
        A description of the relationship.
    source_id:
        Chunk ID(s) that mention this relationship.
    file_path:
        Source file path(s).
    """

    source_entity: str
    target_entity: str
    relationship_keywords: str
    relationship_description: str
    source_id: str = ""
    file_path: str = ""


@dataclass
class ExtractionResult:
    """Result of extracting entities and relationships from a chunk."""

    entities: list[ExtractedEntity] = field(default_factory=list)
    relationships: list[ExtractedRelationship] = field(default_factory=list)
    chunk_id: str = ""


# ── Merged graph node/edge types ─────────────────────────────────

GRAPH_FIELD_SEP = "<SEP>"


@dataclass
class GraphEntity:
    """A merged entity node in the knowledge graph."""

    entity_name: str
    entity_type: str
    description: str
    source_id: str = ""
    file_path: str = ""
    weight: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_name": self.entity_name,
            "entity_type": self.entity_type,
            "description": self.description,
            "source_id": self.source_id,
            "file_path": self.file_path,
            "weight": self.weight,
        }


@dataclass
class GraphRelationship:
    """A merged relationship edge in the knowledge graph."""

    source_entity: str
    target_entity: str
    keywords: str
    description: str
    source_id: str = ""
    file_path: str = ""
    weight: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_entity": self.source_entity,
            "target_entity": self.target_entity,
            "keywords": self.keywords,
            "description": self.description,
            "source_id": self.source_id,
            "file_path": self.file_path,
            "weight": self.weight,
        }
