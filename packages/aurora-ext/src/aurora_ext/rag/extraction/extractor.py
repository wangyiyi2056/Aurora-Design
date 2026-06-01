"""Core entity/relationship extractor for the Aurora knowledge graph.

Migrated from LightRAG ``operate.py`` ``extract_entities()`` and the
associated ``_process_extraction_result`` / ``_process_json_extraction_result``
helpers.

The :class:`EntityRelationExtractor` wraps a :class:`BaseLLM` instance
and exposes a single async ``extract`` method that converts raw chunk
text into :class:`ExtractionResult` dataclass instances.
"""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from typing import Any

import json_repair

from aurora_core.model.base import BaseLLM
from aurora_core.rag.utils.hashing import compute_args_hash
from aurora_core.schema.message import Message

from aurora_ext.rag.extraction.prompts import PROMPTS, get_prompt
from aurora_ext.rag.extraction.types import (
    ExtractedEntity,
    ExtractedRelationship,
    ExtractionResult,
)

logger = logging.getLogger(__name__)

# ── Internal constants ────────────────────────────────────────────

_TUPLE_DELIMITER = PROMPTS["DEFAULT_TUPLE_DELIMITER"]
_COMPLETION_DELIMITER = PROMPTS["DEFAULT_COMPLETION_DELIMITER"]

_MD_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*", re.MULTILINE)


# ── Sanitisation helpers ──────────────────────────────────────────


def _sanitize(text: str, *, remove_inner_quotes: bool = False) -> str:
    """Lightly normalise an extracted text fragment.

    Strips leading/trailing whitespace, collapses repeated spaces, and
    optionally removes inner double-quote characters that LLMs sometimes
    inject around field values.
    """
    text = text.strip()
    if remove_inner_quotes:
        text = text.strip('"').strip("'")
    # Collapse runs of whitespace.
    text = re.sub(r"\s+", " ", text)
    return text


def _strip_markdown_code_fence(text: str) -> str:
    """Remove ````` ```json ```` wrappers that some LLMs add around JSON."""
    return _MD_CODE_FENCE_RE.sub("", text).rstrip("`").strip()


# ── Main extractor class ─────────────────────────────────────────


class EntityRelationExtractor:
    """Extract entities and relationships from a text chunk via LLM.

    Parameters
    ----------
    llm:
        A :class:`BaseLLM` instance used to call the language model.

    Notes
    -----
    All extraction configuration is passed through the ``**config``
    keyword arguments of :meth:`extract` so that a single extractor
    instance can serve different pipelines.
    """

    def __init__(self, llm: BaseLLM) -> None:
        self._llm = llm

    # ── Public API ────────────────────────────────────────────────

    async def extract(
        self,
        chunk_text: str,
        chunk_id: str,
        file_path: str = "",
        **config: Any,
    ) -> ExtractionResult:
        print(f"\n{'!'*80}\n[EXTRACTOR CALLED] chunk_id={chunk_id}, use_json={config.get('use_json', False)}\n{'!'*80}\n", flush=True)
        """Extract entities and relationships from *chunk_text*.

        Parameters
        ----------
        chunk_text:
            The raw text of a single chunk.
        chunk_id:
            Unique identifier for the source chunk.
        file_path:
            Source file path for provenance tracking.
        **config:
            Extraction configuration.  Supported keys:

            - ``language`` (str): Output language.  Default ``"English"``.
            - ``max_total_records`` (int): Row cap.  Default ``100``.
            - ``max_entity_records`` (int): Entity row cap.  Default ``40``.
            - ``use_json`` (bool): Use JSON structured mode.  Default ``False``.
            - ``max_gleaning`` (int): Number of gleaning passes (0 = none).
              Default ``1``.
            - ``entity_types_guidance`` (str | None): Override entity-type
              guidance.  ``None`` uses the built-in default.
            - ``enable_cache`` (bool): Whether to use LLM response caching
              (cache backend supplied externally).  Default ``True``.

        Returns
        -------
        ExtractionResult
            A dataclass containing lists of :class:`ExtractedEntity` and
            :class:`ExtractedRelationship` instances.
        """
        language: str = config.get("language", "English")
        max_total_records: int = int(config.get("max_total_records", 100))
        max_entity_records: int = int(config.get("max_entity_records", 40))
        use_json: bool = bool(config.get("use_json", False))
        max_gleaning: int = int(config.get("max_gleaning", 1))
        entity_types_guidance: str | None = config.get("entity_types_guidance")

        if entity_types_guidance is None:
            entity_types_guidance = PROMPTS["default_entity_types_guidance"]

        # ── Build prompt context ──────────────────────────────────
        if use_json:
            system_prompt, user_prompt, continue_prompt = self._build_json_prompts(
                chunk_text=chunk_text,
                language=language,
                max_total_records=max_total_records,
                max_entity_records=max_entity_records,
                entity_types_guidance=entity_types_guidance,
            )
        else:
            system_prompt, user_prompt, continue_prompt = self._build_text_prompts(
                chunk_text=chunk_text,
                language=language,
                max_total_records=max_total_records,
                max_entity_records=max_entity_records,
                entity_types_guidance=entity_types_guidance,
            )

        # ── Initial extraction ────────────────────────────────────
        llm_output = await self._call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            use_json=use_json,
        )

        print(f"\n{'='*60}\n[DEBUG] LLM raw output for chunk {chunk_id}:\n{llm_output[:800]}\n{'='*60}\n", flush=True)

        entities, relationships = self._parse_response(
            llm_output, chunk_id, file_path, use_json=use_json
        )

        print(f"[DEBUG] Parsed {len(entities)} entities and {len(relationships)} relationships from chunk {chunk_id}\n", flush=True)

        # ── Gleaning passes ──────────────────────────────────────
        for gleaning_round in range(max_gleaning):
            history_messages = self._build_history(
                user_prompt, llm_output, system_prompt
            )

            glean_output = await self._call_llm(
                system_prompt=system_prompt,
                user_prompt=continue_prompt,
                use_json=use_json,
                history_messages=history_messages,
            )

            glean_entities, glean_relationships = self._parse_response(
                glean_output, chunk_id, file_path, use_json=use_json
            )

            # Merge: keep the version with the longer description when
            # both rounds extract the same entity/relationship.
            entities = self._merge_gleaning_entities(entities, glean_entities)
            relationships = self._merge_gleaning_relationships(
                relationships, glean_relationships
            )

            # Early exit if the gleaning round returned nothing new.
            if not glean_entities and not glean_relationships:
                logger.debug(
                    "Gleaning round %d produced no new items for %s; stopping.",
                    gleaning_round + 1,
                    chunk_id,
                )
                break

        logger.info(
            "Extracted %d entities and %d relationships from chunk %s",
            len(entities),
            len(relationships),
            chunk_id,
        )

        return ExtractionResult(
            entities=entities,
            relationships=relationships,
            chunk_id=chunk_id,
        )

    # ── Prompt builders ───────────────────────────────────────────

    @staticmethod
    def _build_text_prompts(
        *,
        chunk_text: str,
        language: str,
        max_total_records: int,
        max_entity_records: int,
        entity_types_guidance: str,
    ) -> tuple[str, str, str]:
        """Build system, user, and continue prompts for text/delimiter mode."""
        example_fmt_ctx = {
            "tuple_delimiter": _TUPLE_DELIMITER,
            "completion_delimiter": _COMPLETION_DELIMITER,
        }
        examples_raw = "\n".join(PROMPTS["entity_extraction_examples"])
        examples = examples_raw.format(**example_fmt_ctx)

        ctx: dict[str, Any] = {
            "tuple_delimiter": _TUPLE_DELIMITER,
            "completion_delimiter": _COMPLETION_DELIMITER,
            "entity_types_guidance": entity_types_guidance,
            "examples": examples,
            "language": language,
            "max_total_records": max_total_records,
            "max_entity_records": max_entity_records,
        }

        system_prompt = PROMPTS["entity_extraction_system_prompt"].format(**ctx)
        user_prompt = PROMPTS["entity_extraction_user_prompt"].format(
            **{**ctx, "input_text": chunk_text}
        )
        continue_prompt = PROMPTS["entity_continue_extraction_user_prompt"].format(
            **ctx
        )

        return system_prompt, user_prompt, continue_prompt

    @staticmethod
    def _build_json_prompts(
        *,
        chunk_text: str,
        language: str,
        max_total_records: int,
        max_entity_records: int,
        entity_types_guidance: str,
    ) -> tuple[str, str, str]:
        """Build system, user, and continue prompts for JSON mode."""
        examples = "\n".join(PROMPTS["entity_extraction_json_examples"])

        ctx: dict[str, Any] = {
            "entity_types_guidance": entity_types_guidance,
            "examples": examples,
            "language": language,
            "max_total_records": max_total_records,
            "max_entity_records": max_entity_records,
        }

        system_prompt = PROMPTS["entity_extraction_json_system_prompt"].format(**ctx)
        user_prompt = PROMPTS["entity_extraction_json_user_prompt"].format(
            **{**ctx, "input_text": chunk_text}
        )
        continue_prompt = PROMPTS["entity_continue_extraction_json_user_prompt"].format(
            **ctx
        )

        return system_prompt, user_prompt, continue_prompt

    # ── LLM invocation ────────────────────────────────────────────

    async def _call_llm(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        use_json: bool,
        history_messages: list[dict[str, str]] | None = None,
    ) -> str:
        """Send messages to the LLM and return the raw text response."""
        messages: list[Message] = [
            Message(role="system", content=system_prompt),
        ]

        if history_messages:
            for msg in history_messages:
                messages.append(
                    Message(role=msg["role"], content=msg["content"])  # type: ignore[arg-type]
                )

        messages.append(Message(role="user", content=user_prompt))

        output = await self._llm.achat(messages)
        return output.text

    @staticmethod
    def _build_history(
        user_prompt: str,
        assistant_response: str,
        _system_prompt: str,
    ) -> list[dict[str, str]]:
        """Pack the previous user/assistant exchange as conversation history."""
        return [
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": assistant_response},
        ]

    # ── Response parsing ──────────────────────────────────────────

    def _parse_response(
        self,
        raw: str,
        chunk_id: str,
        file_path: str,
        *,
        use_json: bool,
    ) -> tuple[list[ExtractedEntity], list[ExtractedRelationship]]:
        """Dispatch to the appropriate parser based on *use_json*."""
        if use_json:
            return self._parse_json(raw, chunk_id, file_path)
        return self._parse_text(raw, chunk_id, file_path)

    # ── Text/delimiter parser ─────────────────────────────────────

    def _parse_text(
        self,
        raw: str,
        chunk_id: str,
        file_path: str,
    ) -> tuple[list[ExtractedEntity], list[ExtractedRelationship]]:
        """Parse the delimiter-based text output from the LLM."""
        entities: list[ExtractedEntity] = []
        relationships: list[ExtractedRelationship] = []

        if _COMPLETION_DELIMITER not in raw:
            logger.warning(
                "%s: Completion delimiter not found in extraction result.",
                chunk_id,
            )

        # Split by newlines and completion delimiters.
        records = re.split(
            rf"\n|{re.escape(_COMPLETION_DELIMITER)}|{re.escape(_COMPLETION_DELIMITER.lower())}",
            raw,
        )

        for record in records:
            record = record.strip()
            if not record:
                continue

            parts = record.split(_TUPLE_DELIMITER)
            parts = [p.strip() for p in parts]

            # Try entity first, then relationship.
            entity = self._try_parse_entity(parts, chunk_id, file_path)
            if entity is not None:
                entities.append(entity)
                continue

            rel = self._try_parse_relationship(parts, chunk_id, file_path)
            if rel is not None:
                relationships.append(rel)

        return entities, relationships

    @staticmethod
    def _try_parse_entity(
        parts: list[str],
        chunk_id: str,
        file_path: str,
    ) -> ExtractedEntity | None:
        """Attempt to parse *parts* as an entity row.

        Expected format: ``["entity", name, type, description]``
        """
        if len(parts) < 4:
            return None

        record_type = parts[0].strip().lower()
        if record_type != "entity":
            return None

        name = _sanitize(parts[1], remove_inner_quotes=True)
        if not name:
            return None

        etype = _sanitize(parts[2], remove_inner_quotes=True)
        if not etype:
            return None

        # Normalise entity type: lowercase, no spaces.
        etype = etype.replace(" ", "").lower()

        description = _sanitize(parts[3])
        if not description:
            logger.debug("%s: Empty description for entity '%s', skipping.", chunk_id, name)
            return None

        return ExtractedEntity(
            entity_name=name,
            entity_type=etype,
            entity_description=description,
            source_id=chunk_id,
            file_path=file_path,
        )

    @staticmethod
    def _try_parse_relationship(
        parts: list[str],
        chunk_id: str,
        file_path: str,
    ) -> ExtractedRelationship | None:
        """Attempt to parse *parts* as a relationship row.

        Expected format:
        ``["relation", source, target, keywords, description]``
        """
        if len(parts) < 5:
            return None

        record_type = parts[0].strip().lower()
        # Accept both "relation" and "relationship".
        if record_type not in ("relation", "relationship"):
            return None

        source = _sanitize(parts[1], remove_inner_quotes=True)
        target = _sanitize(parts[2], remove_inner_quotes=True)

        if not source or not target:
            return None
        if source == target:
            logger.debug(
                "%s: Self-referencing relationship for '%s', skipping.",
                chunk_id,
                source,
            )
            return None

        keywords = _sanitize(parts[3], remove_inner_quotes=True)
        # Normalise full-width commas from CJK models.
        keywords = keywords.replace("，", ",")

        description = _sanitize(parts[4])
        if not description:
            logger.debug(
                "%s: Empty description for relation '%s'~'%s', skipping.",
                chunk_id,
                source,
                target,
            )
            return None

        return ExtractedRelationship(
            source_entity=source,
            target_entity=target,
            relationship_keywords=keywords,
            relationship_description=description,
            source_id=chunk_id,
            file_path=file_path,
        )

    # ── JSON parser ───────────────────────────────────────────────

    def _parse_json(
        self,
        raw: str,
        chunk_id: str,
        file_path: str,
    ) -> tuple[list[ExtractedEntity], list[ExtractedRelationship]]:
        """Parse a JSON-structured extraction result."""
        entities: list[ExtractedEntity] = []
        relationships: list[ExtractedRelationship] = []

        cleaned = _strip_markdown_code_fence(raw).strip()

        try:
            parsed = json_repair.loads(cleaned)
        except Exception as exc:
            logger.warning(
                "%s: Failed to parse JSON extraction result: %s",
                chunk_id,
                exc,
            )
            return entities, relationships

        if not isinstance(parsed, dict):
            logger.warning(
                "%s: JSON extraction result is not a dict, got %s.",
                chunk_id,
                type(parsed).__name__,
            )
            return entities, relationships

        # ── Entities ──────────────────────────────────────────────
        entities_list = parsed.get("entities", [])
        if not isinstance(entities_list, list):
            logger.warning(
                "%s: 'entities' field is not a list in JSON result.",
                chunk_id,
            )
            entities_list = []

        for item in entities_list:
            if not isinstance(item, dict):
                continue

            name = _sanitize(str(item.get("name", "")), remove_inner_quotes=True)
            if not name:
                continue

            etype = _sanitize(str(item.get("type", "")), remove_inner_quotes=True)
            # Reject obviously invalid types.
            if not etype or any(c in etype for c in "'()<>|/\\"):
                logger.warning(
                    "%s: Invalid entity type '%s' for '%s'.",
                    chunk_id,
                    etype,
                    name,
                )
                continue

            etype = etype.replace(" ", "").lower()

            description = _sanitize(str(item.get("description", "")))
            if not description:
                continue

            entities.append(
                ExtractedEntity(
                    entity_name=name,
                    entity_type=etype,
                    entity_description=description,
                    source_id=chunk_id,
                    file_path=file_path,
                )
            )

        # ── Relationships ─────────────────────────────────────────
        rels_list = parsed.get("relationships", [])
        if not isinstance(rels_list, list):
            logger.warning(
                "%s: 'relationships' field is not a list in JSON result.",
                chunk_id,
            )
            rels_list = []

        for item in rels_list:
            if not isinstance(item, dict):
                continue

            source = _sanitize(str(item.get("source", "")), remove_inner_quotes=True)
            target = _sanitize(str(item.get("target", "")), remove_inner_quotes=True)

            if not source or not target:
                continue
            if source == target:
                continue

            keywords = _sanitize(
                str(item.get("keywords", "")), remove_inner_quotes=True
            )
            keywords = keywords.replace("，", ",")

            description = _sanitize(str(item.get("description", "")))
            if not description:
                continue

            relationships.append(
                ExtractedRelationship(
                    source_entity=source,
                    target_entity=target,
                    relationship_keywords=keywords,
                    relationship_description=description,
                    source_id=chunk_id,
                    file_path=file_path,
                )
            )

        return entities, relationships

    # ── Gleaning merge helpers ────────────────────────────────────

    @staticmethod
    def _merge_gleaning_entities(
        original: list[ExtractedEntity],
        gleaned: list[ExtractedEntity],
    ) -> list[ExtractedEntity]:
        """Merge gleaned entities into the original list.

        When the same entity name appears in both lists, the version
        with the longer description is kept.
        """
        if not gleaned:
            return original

        by_name: dict[str, ExtractedEntity] = {}
        for ent in original:
            by_name[ent.entity_name.lower()] = ent

        for ent in gleaned:
            key = ent.entity_name.lower()
            if key in by_name:
                existing = by_name[key]
                if len(ent.entity_description) > len(existing.entity_description):
                    by_name[key] = ent
            else:
                by_name[key] = ent

        return list(by_name.values())

    @staticmethod
    def _merge_gleaning_relationships(
        original: list[ExtractedRelationship],
        gleaned: list[ExtractedRelationship],
    ) -> list[ExtractedRelationship]:
        """Merge gleaned relationships into the original list.

        Matching uses the sorted ``(source, target)`` pair since
        relationships are undirected.
        """
        if not gleaned:
            return original

        def _pair_key(rel: ExtractedRelationship) -> str:
            return "||".join(sorted([rel.source_entity.lower(), rel.target_entity.lower()]))

        by_pair: dict[str, ExtractedRelationship] = {}
        for rel in original:
            by_pair[_pair_key(rel)] = rel

        for rel in gleaned:
            key = _pair_key(rel)
            if key in by_pair:
                existing = by_pair[key]
                if len(rel.relationship_description) > len(existing.relationship_description):
                    by_pair[key] = rel
            else:
                by_pair[key] = rel

        return list(by_pair.values())
