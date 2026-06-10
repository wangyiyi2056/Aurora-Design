"""Extraction configuration dataclasses.

Defines immutable configuration objects for the knowledge graph extraction
pipeline, including multi-round iteration settings, entity type customisation,
output language preferences, and addon parameters.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass, field
from typing import Any, Optional


# ── Default entity types ─────────────────────────────────────────────

_DEFAULT_ENTITY_TYPES: tuple[str, ...] = (
    "Person",
    "Organization",
    "Location",
    "Event",
    "Product",
    "Technology",
    "Concept",
)

_DEFAULT_RELATION_TYPES: tuple[str, ...] = (
    "works_for",
    "located_in",
    "uses",
    "develops",
    "related_to",
)


# ── Extraction iteration config ─────────────────────────────────────


@dataclass(frozen=True)
class ExtractionConfig:
    """Configuration for the multi-round iterative extraction pipeline.

    All fields are immutable to guarantee thread-safe configuration
    sharing across concurrent extraction workers.

    Attributes
    ----------
    entity_extract_max_gleaning:
        Maximum number of LLM gleaning (continuation) rounds for entity
        extraction.  ``0`` means a single pass with no follow-up.
    relation_extract_max_gleaning:
        Maximum number of LLM gleaning rounds for relationship extraction.
        When set independently from entity gleaning, the extractor runs
        the larger of the two values and tracks which item types are
        still being refined.
    max_parallel_extract:
        Maximum number of concurrent extraction tasks (chunks) that may
        run simultaneously.  Controls the asyncio semaphore in the
        orchestrator.
    enable_incremental_extract:
        When ``True``, the extractor supports incremental extraction —
        only processing chunks that have changed since the last run.
    max_total_records:
        Maximum total entity + relationship rows per LLM response.
    max_entity_records:
        Maximum entity rows per LLM response.
    use_json:
        Whether to use JSON structured extraction mode.
    enable_cache:
        Whether to use LLM response caching.
    """

    entity_extract_max_gleaning: int = 2
    relation_extract_max_gleaning: int = 2
    max_parallel_extract: int = 5
    enable_incremental_extract: bool = True
    max_total_records: int = 100
    max_entity_records: int = 40
    use_json: bool = False
    enable_cache: bool = True

    @property
    def max_gleaning(self) -> int:
        """The effective gleaning count (max of entity and relation rounds)."""
        return max(self.entity_extract_max_gleaning, self.relation_extract_max_gleaning)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExtractionConfig:
        """Create from a dictionary (e.g. parsed from TOML ``[kg_extraction]``)."""
        if not data:
            return cls()
        known_keys = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[union-attr]
        filtered = {k: v for k, v in data.items() if k in known_keys}
        return cls(**filtered)


# ── Entity type customisation ────────────────────────────────────────


@dataclass(frozen=True)
class EntityTypeConfig:
    """Configuration for entity and relationship type customisation.

    Attributes
    ----------
    custom_types:
        User-specified entity types that override or extend the defaults.
    type_prompt_file:
        Optional path to a plain-text prompt file that describes entity
        types and their definitions.  When provided, the file content is
        loaded and used as the ``entity_types_guidance`` string.
    default_types:
        The built-in entity types used when no custom types are supplied.
    custom_relation_types:
        User-specified relationship type keywords.
    """

    custom_types: tuple[str, ...] = ()
    type_prompt_file: Optional[str] = None
    default_types: tuple[str, ...] = _DEFAULT_ENTITY_TYPES
    custom_relation_types: tuple[str, ...] = ()

    @property
    def effective_types(self) -> tuple[str, ...]:
        """Return custom types if provided, otherwise default types."""
        return self.custom_types if self.custom_types else self.default_types

    def build_entity_types_guidance(self) -> str:
        """Build the entity-types guidance string for the LLM prompt.

        If a ``type_prompt_file`` is specified and readable, its content
        is returned verbatim.  Otherwise the guidance is assembled from
        the effective type list.
        """
        if self.type_prompt_file:
            path = pathlib.Path(self.type_prompt_file)
            if path.is_file():
                return path.read_text(encoding="utf-8").strip()

        lines = [
            "Classify each entity using one of the following types. "
            "If no type fits, use `Other`.",
            "",
        ]
        for etype in self.effective_types:
            lines.append(f"- {etype}")
        return "\n".join(lines)

    def build_relation_types_guidance(self) -> str | None:
        """Build optional relationship-type guidance, or ``None``."""
        if not self.custom_relation_types:
            return None
        lines = [
            "Prefer the following relationship keyword types where applicable:",
            "",
        ]
        for rtype in self.custom_relation_types:
            lines.append(f"- {rtype}")
        return "\n".join(lines)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EntityTypeConfig:
        """Create from a dictionary (e.g. from TOML sub-sections)."""
        if not data:
            return cls()

        entity_section = data.get("entity_types", data)
        relation_section = data.get("relation_types", {})

        custom_types = entity_section.get("custom_types", ())
        if isinstance(custom_types, list):
            custom_types = tuple(custom_types)

        custom_rel = relation_section.get("custom_types", ())
        if isinstance(custom_rel, list):
            custom_rel = tuple(custom_rel)

        return cls(
            custom_types=custom_types,
            type_prompt_file=entity_section.get("type_prompt_file"),
            custom_relation_types=custom_rel,
        )


# ── Addon / language parameters ──────────────────────────────────────


@dataclass(frozen=True)
class AddonParams:
    """Supplementary extraction parameters.

    Attributes
    ----------
    language:
        Output language for entity names, descriptions, and keywords.
        Examples: ``"English"``, ``"Chinese"``, ``"Japanese"``.
    entity_types_guidance:
        Free-form override for entity type guidance.  When set, takes
        priority over :class:`EntityTypeConfig` guidance.
    relation_types_guidance:
        Free-form override for relationship type guidance.
    """

    language: str = "English"
    entity_types_guidance: Optional[str] = None
    relation_types_guidance: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AddonParams:
        """Create from a dictionary (e.g. from TOML ``[kg_extraction.language]``)."""
        if not data:
            return cls()
        language_section = data.get("language", {})
        if isinstance(language_section, str):
            return cls(language=language_section)
        if isinstance(language_section, dict):
            return cls(
                language=language_section.get("output_language", "English"),
                entity_types_guidance=data.get("entity_types_guidance"),
                relation_types_guidance=data.get("relation_types_guidance"),
            )
        return cls()


# ── Composite configuration ─────────────────────────────────────────


@dataclass(frozen=True)
class KGExtractionFullConfig:
    """Top-level composite configuration for the KG extraction pipeline.

    Aggregates :class:`ExtractionConfig`, :class:`EntityTypeConfig`,
    and :class:`AddonParams` into a single frozen object.
    """

    extraction: ExtractionConfig = field(default_factory=ExtractionConfig)
    entity_types: EntityTypeConfig = field(default_factory=EntityTypeConfig)
    addon: AddonParams = field(default_factory=AddonParams)

    @classmethod
    def from_toml_dict(cls, data: dict[str, Any]) -> KGExtractionFullConfig:
        """Build from the ``[kg_extraction]`` TOML section as a flat dict.

        Expected TOML structure::

            [kg_extraction]
            entity_extract_max_gleaning = 2
            relation_extract_max_gleaning = 2
            max_parallel_extract = 5
            enable_incremental_extract = true

            [kg_extraction.language]
            output_language = "Chinese"

            [kg_extraction.entity_types]
            custom_types = ["Person", "Organization"]
            type_prompt_file = "prompts/entity_types.txt"

            [kg_extraction.relation_types]
            custom_types = ["works_for", "located_in"]
        """
        if not data:
            return cls()

        return cls(
            extraction=ExtractionConfig.from_dict(data),
            entity_types=EntityTypeConfig.from_dict(data),
            addon=AddonParams.from_dict(data),
        )
