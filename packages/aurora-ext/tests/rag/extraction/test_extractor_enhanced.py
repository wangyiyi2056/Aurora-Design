"""Tests for enhanced EntityRelationExtractor behaviour.

Covers:
- Separate entity / relation gleaning round budgets
- Relation types guidance injection
- Language configuration pass-through
- Custom entity types guidance override
"""

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest

from aurora_core.schema.message import Message
from aurora_ext.rag.extraction.extractor import EntityRelationExtractor
from aurora_ext.rag.extraction.prompts import PROMPTS


# ── Helpers ─────────────────────────────────────────────────────────


def _text_entity(name: str, etype: str = "Person") -> str:
    td = PROMPTS["DEFAULT_TUPLE_DELIMITER"]
    return f"entity{td}{name}{td}{etype}{td}Description of {name}"


def _text_relation(src: str, tgt: str, kw: str = "knows") -> str:
    td = PROMPTS["DEFAULT_TUPLE_DELIMITER"]
    return (
        f"relation{td}{src}{td}{tgt}{td}{kw}{td}"
        f"{src} and {tgt} are related via {kw}"
    )


def _complete() -> str:
    return PROMPTS["DEFAULT_COMPLETION_DELIMITER"]


class RecordingLLM:
    """An LLM stub that records every call and replays scripted outputs."""

    def __init__(self, outputs: list[str]) -> None:
        self._outputs = list(outputs)
        self.calls: list[list[Message]] = []

    async def achat(self, messages: list[Message]) -> Any:
        self.calls.append(messages)
        text = self._outputs.pop(0) if self._outputs else _complete()

        class _Out:
            pass

        out = _Out()
        out.text = text  # type: ignore[attr-defined]
        return out


# ── Tests ───────────────────────────────────────────────────────────


class TestExtractorEnhancements:
    @pytest.mark.asyncio
    async def test_separate_entity_relation_gleaning_rounds(self) -> None:
        """Entity and relation gleaning budgets are honoured independently."""
        td = PROMPTS["DEFAULT_TUPLE_DELIMITER"]
        cd = PROMPTS["DEFAULT_COMPLETION_DELIMITER"]

        # Round 0 (initial): 1 entity, 1 relation
        initial = (
            f"{_text_entity('Alice')}\n"
            f"{_text_relation('Alice', 'Bob')}\n"
            f"{cd}"
        )
        # Round 1 (glean): 1 new entity, 1 new relation
        glean1 = (
            f"{_text_entity('Bob')}\n"
            f"{_text_relation('Alice', 'Charlie')}\n"
            f"{cd}"
        )
        # Round 2 (glean): 1 new entity, 1 new relation
        glean2 = (
            f"{_text_entity('Charlie')}\n"
            f"{_text_relation('Bob', 'Charlie')}\n"
            f"{cd}"
        )

        llm = RecordingLLM([initial, glean1, glean2])
        extractor = EntityRelationExtractor(llm)

        result = await extractor.extract(
            chunk_text="Alice knows Bob, who knows Charlie.",
            chunk_id="c1",
            entity_extract_max_gleaning=1,   # entity budget = 1
            relation_extract_max_gleaning=2, # relation budget = 2
        )

        # Entity budget was 1 → 1 initial + 1 glean round = Alice, Bob
        # (glean2 should NOT be merged for entities)
        entity_names = {e.entity_name for e in result.entities}
        assert "Alice" in entity_names
        assert "Bob" in entity_names
        # Charlie might have been returned but only entity gleaning 1 was done.
        # With the current implementation, the merge is skipped once
        # entity_exhausted is True, so Charlie should NOT appear.
        assert "Charlie" not in entity_names

        # Relation budget was 2 → both gleaning rounds should contribute
        rel_pairs = {
            (r.source_entity, r.target_entity) for r in result.relationships
        }
        assert ("Alice", "Bob") in rel_pairs
        assert ("Alice", "Charlie") in rel_pairs

    @pytest.mark.asyncio
    async def test_single_max_gleaning_still_works(self) -> None:
        """The legacy ``max_gleaning`` key still functions."""
        initial = f"{_text_entity('Alice')}\n{_complete()}"
        glean = f"{_text_entity('Bob')}\n{_complete()}"

        llm = RecordingLLM([initial, glean])
        extractor = EntityRelationExtractor(llm)

        result = await extractor.extract(
            chunk_text="Alice and Bob.",
            chunk_id="c2",
            max_gleaning=1,
        )
        entity_names = {e.entity_name for e in result.entities}
        assert "Alice" in entity_names
        assert "Bob" in entity_names
        # 1 initial call + 1 gleaning = 2 LLM calls.
        assert len(llm.calls) == 2

    @pytest.mark.asyncio
    async def test_zero_gleaning(self) -> None:
        """``max_gleaning=0`` yields a single extraction pass, no gleaning."""
        initial = f"{_text_entity('Alice')}\n{_complete()}"
        llm = RecordingLLM([initial])
        extractor = EntityRelationExtractor(llm)

        result = await extractor.extract(
            chunk_text="Alice.",
            chunk_id="c3",
            max_gleaning=0,
            entity_extract_max_gleaning=0,
            relation_extract_max_gleaning=0,
        )
        assert len(result.entities) == 1
        assert len(llm.calls) == 1

    @pytest.mark.asyncio
    async def test_relation_types_guidance_injected(self) -> None:
        """When ``relation_types_guidance`` is provided it appears in the system prompt."""
        initial = f"{_text_entity('Alice')}\n{_complete()}"
        llm = RecordingLLM([initial])
        extractor = EntityRelationExtractor(llm)

        await extractor.extract(
            chunk_text="Alice works for Acme.",
            chunk_id="c4",
            max_gleaning=0,
            entity_extract_max_gleaning=0,
            relation_extract_max_gleaning=0,
            relation_types_guidance="Prefer: works_for, located_in",
        )

        system_msg = llm.calls[0][0]
        assert system_msg.role == "system"
        assert "works_for" in system_msg.content
        assert "Relation" in system_msg.content or "relationship" in system_msg.content.lower()

    @pytest.mark.asyncio
    async def test_language_passed_through(self) -> None:
        """The ``language`` kwarg appears in the user prompt."""
        initial = f"{_text_entity('Alice')}\n{_complete()}"
        llm = RecordingLLM([initial])
        extractor = EntityRelationExtractor(llm)

        await extractor.extract(
            chunk_text="Alice works at Acme.",
            chunk_id="c5",
            language="Chinese",
            max_gleaning=0,
            entity_extract_max_gleaning=0,
            relation_extract_max_gleaning=0,
        )

        user_msgs = [m for m in llm.calls[0] if m.role == "user"]
        assert any("Chinese" in m.content for m in user_msgs)

    @pytest.mark.asyncio
    async def test_custom_entity_types_guidance(self) -> None:
        """A custom ``entity_types_guidance`` overrides the built-in default."""
        initial = f"{_text_entity('Alice', 'Engineer')}\n{_complete()}"
        llm = RecordingLLM([initial])
        extractor = EntityRelationExtractor(llm)

        custom_guidance = "Use only these types: Engineer, Manager, Intern"
        await extractor.extract(
            chunk_text="Alice is an engineer.",
            chunk_id="c6",
            max_gleaning=0,
            entity_extract_max_gleaning=0,
            relation_extract_max_gleaning=0,
            entity_types_guidance=custom_guidance,
        )

        system_msg = llm.calls[0][0]
        assert "Engineer, Manager, Intern" in system_msg.content

    @pytest.mark.asyncio
    async def test_early_exit_when_glean_returns_empty(self) -> None:
        """If a gleaning round returns nothing, further rounds are skipped."""
        initial = f"{_text_entity('Alice')}\n{_complete()}"
        # Glean round 1 returns nothing useful
        empty_glean = f"{_complete()}"

        llm = RecordingLLM([initial, empty_glean])
        extractor = EntityRelationExtractor(llm)

        result = await extractor.extract(
            chunk_text="Alice.",
            chunk_id="c7",
            entity_extract_max_gleaning=5,  # large budget
            relation_extract_max_gleaning=5,
        )

        # Should exit after 1 gleaning round that returned nothing,
        # so total LLM calls = 1 initial + 1 gleaning = 2.
        assert len(llm.calls) == 2
        assert len(result.entities) == 1
