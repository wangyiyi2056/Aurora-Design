"""Description summarisation for merged knowledge-graph nodes and edges.

Migrated from LightRAG ``operate.py`` ``_summarize_descriptions`` and
``_handle_entity_relation_summary``.

When an entity or relationship accumulates many description fragments
across chunks, this module condenses them into a single cohesive
summary via an LLM call using the ``summarize_entity_descriptions``
prompt.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from aurora_core.model.base import BaseLLM
from aurora_core.schema.message import Message

from aurora_ext.rag.extraction.prompts import PROMPTS

logger = logging.getLogger(__name__)

# ── Defaults ──────────────────────────────────────────────────────

_DEFAULT_SUMMARY_LENGTH = 600
_DEFAULT_LANGUAGE = "English"


# ── Public API ────────────────────────────────────────────────────


async def summarize_descriptions(
    llm: BaseLLM,
    name: str,
    descriptions: list[str],
    description_type: str = "entity",
    language: str = _DEFAULT_LANGUAGE,
    summary_length: int = _DEFAULT_SUMMARY_LENGTH,
) -> str:
    """Summarise a list of description fragments into a cohesive whole.

    This is the Aurora equivalent of LightRAG's
    ``_summarize_descriptions`` helper.  It performs a single LLM call
    (map-reduce style) to merge all provided descriptions.

    Parameters
    ----------
    llm:
        A :class:`BaseLLM` instance.
    name:
        The entity or relationship name being summarised.
    descriptions:
        List of raw description strings to merge.
    description_type:
        Either ``"entity"`` or ``"relation"`` — used only for prompt
        context so the LLM understands what it is summarising.
    language:
        Output language for the summary.
    summary_length:
        Target maximum token length for the summary.

    Returns
    -------
    str
        A single merged description string.  If *descriptions* is empty
        an empty string is returned.  If only one description is
        provided it is returned as-is without an LLM call.
    """
    if not descriptions:
        return ""

    # Deduplicate while preserving order.
    seen: set[str] = set()
    unique: list[str] = []
    for desc in descriptions:
        stripped = desc.strip()
        if stripped and stripped not in seen:
            seen.add(stripped)
            unique.append(stripped)

    if not unique:
        return ""

    if len(unique) == 1:
        return unique[0]

    # ── Build the description payload in JSONL format ─────────────
    json_descriptions = [{"Description": desc} for desc in unique]
    joined_descriptions = "\n".join(
        json.dumps(item, ensure_ascii=False) for item in json_descriptions
    )

    # ── Format the prompt ─────────────────────────────────────────
    prompt = PROMPTS["summarize_entity_descriptions"].format(
        description_type=description_type.capitalize(),
        description_name=name,
        description_list=joined_descriptions,
        summary_length=summary_length,
        language=language,
    )

    # ── Call the LLM ──────────────────────────────────────────────
    messages = [Message(role="user", content=prompt)]

    try:
        output = await llm.achat(messages)
        summary = output.text.strip()
    except Exception as exc:
        logger.error(
            "LLM summarisation failed for '%s' (%s): %s",
            name,
            description_type,
            exc,
        )
        # Fallback: concatenate all descriptions with a separator.
        summary = " ".join(unique)

    if not summary:
        logger.warning(
            "Empty summary returned for '%s' (%s); falling back to join.",
            name,
            description_type,
        )
        summary = " ".join(unique)

    return summary
