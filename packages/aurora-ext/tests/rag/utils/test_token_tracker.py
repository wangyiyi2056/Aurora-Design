"""Tests for the fine-grained token budget control system.

Covers TokenBudget configuration, TokenTracker usage tracking,
priority-based truncation, and statistics accuracy.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from aurora_ext.rag.utils.token_tracker import TokenBudget, TokenTracker


# ── TokenBudget Tests ───────────────────────────────────────────────


class TestTokenBudget:
    """TokenBudget dataclass — immutable configuration."""

    def test_default_values(self):
        """Default budget values match specification."""
        budget = TokenBudget()

        assert budget.max_entity_tokens == 5000
        assert budget.max_relation_tokens == 5000
        assert budget.max_total_tokens == 12000
        assert budget.max_chunk_tokens == 8000
        assert budget.track_usage is True

    def test_custom_values(self):
        """Custom budget values are stored correctly."""
        budget = TokenBudget(
            max_entity_tokens=1000,
            max_relation_tokens=2000,
            max_total_tokens=5000,
            max_chunk_tokens=3000,
            track_usage=False,
        )

        assert budget.max_entity_tokens == 1000
        assert budget.max_relation_tokens == 2000
        assert budget.max_total_tokens == 5000
        assert budget.max_chunk_tokens == 3000
        assert budget.track_usage is False

    def test_frozen_immutable(self):
        """TokenBudget is frozen — cannot mutate fields."""
        budget = TokenBudget()

        with pytest.raises(Exception):
            budget.max_entity_tokens = 9999

    def test_with_overrides(self):
        """with_overrides returns new budget with specified fields changed."""
        original = TokenBudget(max_entity_tokens=5000, max_total_tokens=12000)
        updated = original.with_overrides(max_entity_tokens=10000)

        assert updated.max_entity_tokens == 10000
        assert updated.max_total_tokens == 12000  # unchanged
        assert original.max_entity_tokens == 5000  # original untouched

    def test_with_overrides_multiple(self):
        """with_overrides accepts multiple field overrides."""
        original = TokenBudget()
        updated = original.with_overrides(
            max_entity_tokens=100,
            max_chunk_tokens=200,
            track_usage=False,
        )

        assert updated.max_entity_tokens == 100
        assert updated.max_chunk_tokens == 200
        assert updated.track_usage is False
        assert updated.max_relation_tokens == 5000  # unchanged

    def test_from_toml_full(self):
        """Build from a complete TOML dict."""
        config = {
            "token_budget": {
                "max_entity_tokens": 3000,
                "max_relation_tokens": 4000,
                "max_total_tokens": 10000,
                "max_chunk_tokens": 6000,
                "track_usage": False,
            }
        }
        budget = TokenBudget.from_toml(config)

        assert budget.max_entity_tokens == 3000
        assert budget.max_relation_tokens == 4000
        assert budget.max_total_tokens == 10000
        assert budget.max_chunk_tokens == 6000
        assert budget.track_usage is False

    def test_from_toml_partial(self):
        """Missing TOML keys fall back to defaults."""
        config = {
            "token_budget": {
                "max_total_tokens": 8000,
            }
        }
        budget = TokenBudget.from_toml(config)

        assert budget.max_entity_tokens == 5000  # default
        assert budget.max_total_tokens == 8000
        assert budget.max_chunk_tokens == 8000  # default

    def test_from_toml_empty(self):
        """Empty config returns all defaults."""
        budget = TokenBudget.from_toml({})

        assert budget.max_entity_tokens == 5000
        assert budget.max_total_tokens == 12000

    def test_from_toml_flat_keys(self):
        """TOML dict without token_budget wrapper still works."""
        config = {
            "max_entity_tokens": 2000,
            "max_total_tokens": 6000,
        }
        budget = TokenBudget.from_toml(config)

        assert budget.max_entity_tokens == 2000
        assert budget.max_total_tokens == 6000


# ── TokenTracker — Initialization ──────────────────────────────────


class TestTokenTrackerInit:
    """TokenTracker initialization and default state."""

    def test_default_budget(self):
        """Default constructor creates a default TokenBudget."""
        tracker = TokenTracker()

        assert tracker.budget.max_entity_tokens == 5000
        assert tracker.budget.max_total_tokens == 12000

    def test_custom_budget(self):
        """Custom budget is stored."""
        budget = TokenBudget(max_total_tokens=100)
        tracker = TokenTracker(budget)

        assert tracker.budget.max_total_tokens == 100

    def test_initial_stats_zero(self):
        """All counters start at zero."""
        tracker = TokenTracker()
        stats = tracker.get_stats()

        assert stats["usage"]["llm_calls"] == 0
        assert stats["usage"]["embedding_calls"] == 0
        assert stats["usage"]["total_tokens"] == 0
        assert stats["usage"]["truncation_events"] == 0


# ── TokenTracker — LLM Tracking ────────────────────────────────────


class TestLLMTracking:
    """Track LLM call token consumption."""

    def test_single_llm_call(self):
        """Single LLM call records prompt + completion tokens."""
        tracker = TokenTracker()
        tracker.track_llm_call(prompt_tokens=100, completion_tokens=50)

        stats = tracker.get_stats()
        assert stats["usage"]["llm_calls"] == 1
        assert stats["usage"]["llm_prompt_tokens"] == 100
        assert stats["usage"]["llm_completion_tokens"] == 50
        assert stats["usage"]["total_tokens"] == 150

    def test_multiple_llm_calls(self):
        """Multiple LLM calls accumulate."""
        tracker = TokenTracker()
        tracker.track_llm_call(prompt_tokens=100, completion_tokens=50)
        tracker.track_llm_call(prompt_tokens=200, completion_tokens=80)
        tracker.track_llm_call(prompt_tokens=50, completion_tokens=20)

        stats = tracker.get_stats()
        assert stats["usage"]["llm_calls"] == 3
        assert stats["usage"]["llm_prompt_tokens"] == 350
        assert stats["usage"]["llm_completion_tokens"] == 150
        assert stats["usage"]["total_tokens"] == 500

    def test_tracking_disabled(self):
        """When track_usage=False, calls are not recorded."""
        budget = TokenBudget(track_usage=False)
        tracker = TokenTracker(budget)
        tracker.track_llm_call(prompt_tokens=100, completion_tokens=50)

        stats = tracker.get_stats()
        assert stats["usage"]["llm_calls"] == 0
        assert stats["usage"]["total_tokens"] == 0


# ── TokenTracker — Embedding Tracking ──────────────────────────────


class TestEmbeddingTracking:
    """Track embedding call token consumption."""

    def test_single_embedding_call(self):
        """Single embedding call records token count."""
        tracker = TokenTracker()
        tracker.track_embedding_call(tokens=300)

        stats = tracker.get_stats()
        assert stats["usage"]["embedding_calls"] == 1
        assert stats["usage"]["embedding_tokens"] == 300
        assert stats["usage"]["total_tokens"] == 300

    def test_multiple_embedding_calls(self):
        """Multiple embedding calls accumulate."""
        tracker = TokenTracker()
        tracker.track_embedding_call(tokens=100)
        tracker.track_embedding_call(tokens=200)

        stats = tracker.get_stats()
        assert stats["usage"]["embedding_calls"] == 2
        assert stats["usage"]["embedding_tokens"] == 300
        assert stats["usage"]["total_tokens"] == 300

    def test_mixed_llm_and_embedding(self):
        """LLM and embedding tokens sum into total_tokens."""
        tracker = TokenTracker()
        tracker.track_llm_call(prompt_tokens=100, completion_tokens=50)
        tracker.track_embedding_call(tokens=200)

        stats = tracker.get_stats()
        assert stats["usage"]["total_tokens"] == 350


# ── TokenTracker — Reset ──────────────────────────────────────────


class TestResetStats:
    """Reset usage counters to zero."""

    def test_reset_clears_all(self):
        """reset_stats zeros every counter."""
        tracker = TokenTracker()
        tracker.track_llm_call(100, 50)
        tracker.track_embedding_call(200)

        tracker.reset_stats()
        stats = tracker.get_stats()

        assert stats["usage"]["llm_calls"] == 0
        assert stats["usage"]["embedding_calls"] == 0
        assert stats["usage"]["total_tokens"] == 0
        assert stats["categories"]["entity_tokens"] == 0

    def test_reset_then_track(self):
        """After reset, new tracking starts from zero."""
        tracker = TokenTracker()
        tracker.track_llm_call(100, 50)
        tracker.reset_stats()
        tracker.track_llm_call(30, 20)

        stats = tracker.get_stats()
        assert stats["usage"]["llm_calls"] == 1
        assert stats["usage"]["llm_prompt_tokens"] == 30
        assert stats["usage"]["total_tokens"] == 50


# ── TokenTracker — Truncation Logic ───────────────────────────────


def _mock_count_tokens(text: str) -> int:
    """Deterministic mock: 1 token per word (split on whitespace)."""
    if not text:
        return 0
    return len(text.split())


class TestTruncationBasic:
    """Basic truncation — items within budget."""

    @patch("aurora_ext.rag.utils.token_tracker.count_tokens", side_effect=_mock_count_tokens)
    def test_no_truncation_needed(self, _mock):
        """Items within budget are returned unchanged."""
        budget = TokenBudget(
            max_entity_tokens=100,
            max_relation_tokens=100,
            max_total_tokens=500,
            max_chunk_tokens=100,
        )
        tracker = TokenTracker(budget)

        entities = [{"description": "hello world", "entity_name": "e1"}]
        relations = [{"description": "foo bar", "src_id": "a", "tgt_id": "b"}]
        chunks = [{"content": "some text here"}]

        e, r, c = tracker.truncate_to_budget(entities, relations, chunks)

        assert len(e) == 1
        assert len(r) == 1
        assert len(c) == 1

    @patch("aurora_ext.rag.utils.token_tracker.count_tokens", side_effect=_mock_count_tokens)
    def test_empty_lists(self, _mock):
        """Empty input lists return empty output."""
        tracker = TokenTracker()
        e, r, c = tracker.truncate_to_budget([], [], [])

        assert e == []
        assert r == []
        assert c == []


class TestTruncationPriority:
    """Priority ordering: entities → relations → chunks."""

    @patch("aurora_ext.rag.utils.token_tracker.count_tokens", side_effect=_mock_count_tokens)
    def test_entities_preserved_over_chunks(self, _mock):
        """Entities are kept even when chunks must be dropped."""
        budget = TokenBudget(
            max_entity_tokens=100,
            max_relation_tokens=100,
            max_total_tokens=10,  # very tight total
            max_chunk_tokens=100,
        )
        tracker = TokenTracker(budget)

        # Entity: 2 tokens
        entities = [{"description": "hello world", "entity_name": "e1"}]
        # Chunk: 5 tokens — won't fit after entities use 2 of the 10 total
        chunks = [{"content": "one two three four five"}]

        e, r, c = tracker.truncate_to_budget(entities, [], chunks)

        assert len(e) == 1  # entity preserved (2 tokens ≤ 10 total)
        assert len(c) == 1  # chunk fits: 2 + 5 = 7 ≤ 10

    @patch("aurora_ext.rag.utils.token_tracker.count_tokens", side_effect=_mock_count_tokens)
    def test_entities_preserved_relations_dropped(self, _mock):
        """Entities get priority when total budget is very tight."""
        budget = TokenBudget(
            max_entity_tokens=100,
            max_relation_tokens=100,
            max_total_tokens=5,  # only room for entities
            max_chunk_tokens=100,
        )
        tracker = TokenTracker(budget)

        # Entity: 3 tokens
        entities = [{"description": "a b c", "entity_name": "e1"}]
        # Relation: 3 tokens — 3+3=6 > 5 total, won't fit
        relations = [{"description": "x y z", "src_id": "a", "tgt_id": "b"}]
        # Chunk: 3 tokens
        chunks = [{"content": "p q r"}]

        e, r, c = tracker.truncate_to_budget(entities, relations, chunks)

        assert len(e) == 1  # entity preserved
        assert len(r) == 0  # relation dropped (3+3=6 > 5)
        assert len(c) == 0  # chunk dropped too

    @patch("aurora_ext.rag.utils.token_tracker.count_tokens", side_effect=_mock_count_tokens)
    def test_relations_preserved_over_chunks(self, _mock):
        """Relations have higher priority than chunks."""
        budget = TokenBudget(
            max_entity_tokens=0,  # no entities allowed
            max_relation_tokens=100,
            max_total_tokens=8,
            max_chunk_tokens=100,
        )
        tracker = TokenTracker(budget)

        # Relation: 4 tokens
        relations = [{"description": "a b c d", "src_id": "x", "tgt_id": "y"}]
        # Chunk: 5 tokens — 4+5=9 > 8 total
        chunks = [{"content": "one two three four five"}]

        e, r, c = tracker.truncate_to_budget([], relations, chunks)

        assert len(r) == 1  # relation preserved
        assert len(c) == 0  # chunk dropped


class TestTruncationScoreSorting:
    """High-score items preserved when truncating."""

    @patch("aurora_ext.rag.utils.token_tracker.count_tokens", side_effect=_mock_count_tokens)
    def test_entities_sorted_by_score(self, _mock):
        """Higher-score entities are kept when budget is limited."""
        budget = TokenBudget(
            max_entity_tokens=4,  # room for ~2 entities of 2 tokens each
            max_relation_tokens=100,
            max_total_tokens=100,
            max_chunk_tokens=100,
        )
        tracker = TokenTracker(budget)

        entities = [
            {"description": "low score", "entity_name": "low", "score": 0.1},
            {"description": "high score", "entity_name": "high", "score": 0.9},
            {"description": "mid score", "entity_name": "mid", "score": 0.5},
        ]

        e, _, _ = tracker.truncate_to_budget(entities, [], [])

        # high (2 tokens) + mid (2 tokens) = 4 tokens, fits
        # low would push to 6 > 4
        assert len(e) == 2
        assert e[0]["entity_name"] == "high"
        assert e[1]["entity_name"] == "mid"

    @patch("aurora_ext.rag.utils.token_tracker.count_tokens", side_effect=_mock_count_tokens)
    def test_chunks_sorted_by_rerank_score(self, _mock):
        """Chunks with rerank_score are sorted correctly."""
        budget = TokenBudget(
            max_entity_tokens=0,
            max_relation_tokens=0,
            max_total_tokens=6,
            max_chunk_tokens=6,
        )
        tracker = TokenTracker(budget)

        chunks = [
            {"content": "low content here", "rerank_score": 0.2},  # 3 tokens
            {"content": "high content text", "rerank_score": 0.95},  # 3 tokens
            {"content": "mid level words", "rerank_score": 0.5},  # 3 tokens
        ]

        _, _, c = tracker.truncate_to_budget([], [], chunks)

        # high (3) + mid (3) = 6 ≤ 6, fits
        assert len(c) == 2
        assert c[0]["rerank_score"] == 0.95
        assert c[1]["rerank_score"] == 0.5

    @patch("aurora_ext.rag.utils.token_tracker.count_tokens", side_effect=_mock_count_tokens)
    def test_weight_field_used_as_fallback(self, _mock):
        """When no score/rerank_score, weight is used."""
        budget = TokenBudget(
            max_entity_tokens=4,
            max_relation_tokens=100,
            max_total_tokens=100,
            max_chunk_tokens=100,
        )
        tracker = TokenTracker(budget)

        entities = [
            {"description": "low w", "entity_name": "low", "weight": 1.0},
            {"description": "high w", "entity_name": "high", "weight": 10.0},
            {"description": "mid w", "entity_name": "mid", "weight": 5.0},
        ]

        e, _, _ = tracker.truncate_to_budget(entities, [], [])

        assert len(e) == 2
        assert e[0]["entity_name"] == "high"
        assert e[1]["entity_name"] == "mid"


class TestTruncationEdgeCases:
    """Edge cases in truncation logic."""

    @patch("aurora_ext.rag.utils.token_tracker.count_tokens", side_effect=_mock_count_tokens)
    def test_single_oversized_entity(self, _mock):
        """A single entity exceeding the per-category budget is dropped."""
        budget = TokenBudget(
            max_entity_tokens=2,  # only 2 tokens allowed
            max_relation_tokens=100,
            max_total_tokens=100,
            max_chunk_tokens=100,
        )
        tracker = TokenTracker(budget)

        # Entity with 10 tokens — exceeds max_entity_tokens
        entities = [
            {"description": "one two three four five six seven eight nine ten"}
        ]

        e, _, _ = tracker.truncate_to_budget(entities, [], [])

        assert len(e) == 0

    @patch("aurora_ext.rag.utils.token_tracker.count_tokens", side_effect=_mock_count_tokens)
    def test_zero_budget(self, _mock):
        """Zero token budget drops everything."""
        budget = TokenBudget(
            max_entity_tokens=0,
            max_relation_tokens=0,
            max_total_tokens=0,
            max_chunk_tokens=0,
        )
        tracker = TokenTracker(budget)

        entities = [{"description": "hello"}]
        relations = [{"description": "world"}]
        chunks = [{"content": "text"}]

        e, r, c = tracker.truncate_to_budget(entities, relations, chunks)

        assert e == []
        assert r == []
        assert c == []

    @patch("aurora_ext.rag.utils.token_tracker.count_tokens", side_effect=_mock_count_tokens)
    def test_items_without_text_field(self, _mock):
        """Items missing the text field count as 0 tokens."""
        budget = TokenBudget(
            max_entity_tokens=100,
            max_relation_tokens=100,
            max_total_tokens=100,
            max_chunk_tokens=100,
        )
        tracker = TokenTracker(budget)

        # Entity without 'description' field
        entities = [{"entity_name": "e1", "entity_type": "person"}]

        e, _, _ = tracker.truncate_to_budget(entities, [], [])

        assert len(e) == 1  # kept because 0 tokens

    @patch("aurora_ext.rag.utils.token_tracker.count_tokens", side_effect=_mock_count_tokens)
    def test_empty_string_fields(self, _mock):
        """Items with empty string text fields count as 0 tokens."""
        budget = TokenBudget(
            max_entity_tokens=100,
            max_relation_tokens=100,
            max_total_tokens=100,
            max_chunk_tokens=100,
        )
        tracker = TokenTracker(budget)

        entities = [{"description": "", "entity_name": "e1"}]
        e, _, _ = tracker.truncate_to_budget(entities, [], [])

        assert len(e) == 1

    @patch("aurora_ext.rag.utils.token_tracker.count_tokens", side_effect=_mock_count_tokens)
    def test_exact_budget_boundary(self, _mock):
        """Items that exactly fill the budget are included."""
        budget = TokenBudget(
            max_entity_tokens=4,
            max_relation_tokens=0,
            max_total_tokens=4,
            max_chunk_tokens=0,
        )
        tracker = TokenTracker(budget)

        # Exactly 4 tokens
        entities = [
            {"description": "a b", "entity_name": "e1"},  # 2 tokens
            {"description": "c d", "entity_name": "e2"},  # 2 tokens
        ]

        e, _, _ = tracker.truncate_to_budget(entities, [], [])

        assert len(e) == 2  # exactly fits

    @patch("aurora_ext.rag.utils.token_tracker.count_tokens", side_effect=_mock_count_tokens)
    def test_one_over_budget(self, _mock):
        """Item that pushes 1 token over is excluded."""
        budget = TokenBudget(
            max_entity_tokens=3,
            max_relation_tokens=0,
            max_total_tokens=100,
            max_chunk_tokens=0,
        )
        tracker = TokenTracker(budget)

        entities = [
            {"description": "a b", "entity_name": "e1"},  # 2 tokens
            {"description": "c d", "entity_name": "e2"},  # 2 tokens — total would be 4 > 3
        ]

        e, _, _ = tracker.truncate_to_budget(entities, [], [])

        assert len(e) == 1


# ── TokenTracker — Category Stats ─────────────────────────────────


class TestCategoryStats:
    """Per-category token and count statistics."""

    @patch("aurora_ext.rag.utils.token_tracker.count_tokens", side_effect=_mock_count_tokens)
    def test_category_tokens_recorded(self, _mock):
        """Category token counts are recorded after truncation."""
        budget = TokenBudget(
            max_entity_tokens=100,
            max_relation_tokens=100,
            max_total_tokens=200,
            max_chunk_tokens=100,
        )
        tracker = TokenTracker(budget)

        entities = [{"description": "hello world", "entity_name": "e1"}]  # 2 tokens
        relations = [{"description": "foo bar baz"}]  # 3 tokens
        chunks = [{"content": "one two"}]  # 2 tokens

        tracker.truncate_to_budget(entities, relations, chunks)
        stats = tracker.get_stats()

        assert stats["categories"]["entity_tokens"] == 2
        assert stats["categories"]["relation_tokens"] == 3
        assert stats["categories"]["chunk_tokens"] == 2

    @patch("aurora_ext.rag.utils.token_tracker.count_tokens", side_effect=_mock_count_tokens)
    def test_truncation_counts_recorded(self, _mock):
        """Before/after counts are tracked."""
        budget = TokenBudget(
            max_entity_tokens=2,  # only 1 entity fits (2 tokens)
            max_relation_tokens=100,
            max_total_tokens=100,
            max_chunk_tokens=100,
        )
        tracker = TokenTracker(budget)

        entities = [
            {"description": "a b", "entity_name": "e1", "score": 0.9},
            {"description": "c d", "entity_name": "e2", "score": 0.1},
        ]

        tracker.truncate_to_budget(entities, [], [])
        stats = tracker.get_stats()

        assert stats["categories"]["entities_before_truncation"] == 2
        assert stats["categories"]["entities_after_truncation"] == 1

    @patch("aurora_ext.rag.utils.token_tracker.count_tokens", side_effect=_mock_count_tokens)
    def test_truncation_event_counter(self, _mock):
        """truncation_events increments when items are dropped."""
        budget = TokenBudget(
            max_entity_tokens=2,
            max_relation_tokens=100,
            max_total_tokens=100,
            max_chunk_tokens=100,
        )
        tracker = TokenTracker(budget)

        # 3 entities, budget allows 1
        entities = [
            {"description": "a b", "entity_name": "e1", "score": 0.9},
            {"description": "c d", "entity_name": "e2", "score": 0.5},
            {"description": "e f", "entity_name": "e3", "score": 0.1},
        ]

        tracker.truncate_to_budget(entities, [], [])
        stats = tracker.get_stats()

        assert stats["usage"]["truncation_events"] == 1

    @patch("aurora_ext.rag.utils.token_tracker.count_tokens", side_effect=_mock_count_tokens)
    def test_no_truncation_event_when_fits(self, _mock):
        """No truncation event when everything fits."""
        budget = TokenBudget(
            max_entity_tokens=100,
            max_relation_tokens=100,
            max_total_tokens=200,
            max_chunk_tokens=100,
        )
        tracker = TokenTracker(budget)

        entities = [{"description": "hello", "entity_name": "e1"}]
        tracker.truncate_to_budget(entities, [], [])

        stats = tracker.get_stats()
        assert stats["usage"]["truncation_events"] == 0


# ── TokenTracker — get_stats structure ─────────────────────────────


class TestStatsStructure:
    """Verify the stats dict structure."""

    def test_stats_has_all_keys(self):
        """get_stats returns all expected top-level and nested keys."""
        tracker = TokenTracker()
        stats = tracker.get_stats()

        assert "budget" in stats
        assert "usage" in stats
        assert "categories" in stats

        assert "max_entity_tokens" in stats["budget"]
        assert "max_relation_tokens" in stats["budget"]
        assert "max_total_tokens" in stats["budget"]
        assert "max_chunk_tokens" in stats["budget"]
        assert "track_usage" in stats["budget"]

        assert "llm_calls" in stats["usage"]
        assert "llm_prompt_tokens" in stats["usage"]
        assert "llm_completion_tokens" in stats["usage"]
        assert "embedding_calls" in stats["usage"]
        assert "embedding_tokens" in stats["usage"]
        assert "total_tokens" in stats["usage"]
        assert "truncation_events" in stats["usage"]

        assert "entity_tokens" in stats["categories"]
        assert "relation_tokens" in stats["categories"]
        assert "chunk_tokens" in stats["categories"]

    def test_budget_reflected_in_stats(self):
        """Stats budget section mirrors the TokenBudget."""
        budget = TokenBudget(max_entity_tokens=999, max_total_tokens=1234)
        tracker = TokenTracker(budget)
        stats = tracker.get_stats()

        assert stats["budget"]["max_entity_tokens"] == 999
        assert stats["budget"]["max_total_tokens"] == 1234


# ── TokenTracker — Score Extraction ────────────────────────────────


class TestScoreExtraction:
    """Score extraction from different field names."""

    def test_rerank_score_preferred(self):
        """rerank_score takes precedence over score and weight."""
        item = {"rerank_score": 0.95, "score": 0.5, "weight": 1.0}
        assert TokenTracker._get_item_score(item) == 0.95

    def test_score_fallback(self):
        """score is used when rerank_score is absent."""
        item = {"score": 0.7, "weight": 2.0}
        assert TokenTracker._get_item_score(item) == 0.7

    def test_weight_fallback(self):
        """weight is used when score and rerank_score are absent."""
        item = {"weight": 3.0}
        assert TokenTracker._get_item_score(item) == 3.0

    def test_no_score_returns_zero(self):
        """Missing all score fields returns 0.0."""
        item = {"content": "hello"}
        assert TokenTracker._get_item_score(item) == 0.0

    def test_invalid_score_returns_zero(self):
        """Non-numeric score values return 0.0."""
        item = {"score": "not_a_number"}
        assert TokenTracker._get_item_score(item) == 0.0

    def test_none_score_falls_through(self):
        """None score values fall through to next field."""
        item = {"rerank_score": None, "score": 0.5}
        assert TokenTracker._get_item_score(item) == 0.5


# ── Integration: Budget Overflow ──────────────────────────────────


class TestBudgetOverflow:
    """Scenarios where content exceeds budget significantly."""

    @patch("aurora_ext.rag.utils.token_tracker.count_tokens", side_effect=_mock_count_tokens)
    def test_entities_exceed_total_budget(self, _mock):
        """When entities alone exceed total, they are truncated first."""
        budget = TokenBudget(
            max_entity_tokens=100,
            max_relation_tokens=100,
            max_total_tokens=5,  # very tight
            max_chunk_tokens=100,
        )
        tracker = TokenTracker(budget)

        entities = [
            {"description": "a b c", "entity_name": "e1", "score": 0.9},  # 3 tokens
            {"description": "d e f", "entity_name": "e2", "score": 0.5},  # 3 tokens — total 6 > 5
        ]
        relations = [{"description": "x y", "src_id": "a", "tgt_id": "b"}]
        chunks = [{"content": "hello"}]

        e, r, c = tracker.truncate_to_budget(entities, relations, chunks)

        assert len(e) == 1  # only first entity fits in total budget
        assert len(r) == 1  # 3 + 2 = 5, fits
        assert len(c) == 0  # no room left

    @patch("aurora_ext.rag.utils.token_tracker.count_tokens", side_effect=_mock_count_tokens)
    def test_all_categories_truncated(self, _mock):
        """All three categories can be truncated simultaneously."""
        budget = TokenBudget(
            max_entity_tokens=4,
            max_relation_tokens=4,
            max_total_tokens=8,
            max_chunk_tokens=4,
        )
        tracker = TokenTracker(budget)

        entities = [
            {"description": "a b", "entity_name": "e1", "score": 0.9},
            {"description": "c d", "entity_name": "e2", "score": 0.8},
            {"description": "e f", "entity_name": "e3", "score": 0.1},
        ]
        relations = [
            {"description": "g h", "src_id": "a", "tgt_id": "b", "score": 0.7},
            {"description": "i j", "src_id": "c", "tgt_id": "d", "score": 0.3},
        ]
        chunks = [
            {"content": "k l", "score": 0.6},
            {"content": "m n", "score": 0.2},
        ]

        e, r, c = tracker.truncate_to_budget(entities, relations, chunks)

        # entities: 2+2=4 ≤ 4 ✓, but total is 8
        # relations: 2+2=4 ≤ 4, but total remaining = 8-4=4, so 2+2=4 ✓
        # chunks: total remaining = 8-4-4=0, so 0 chunks
        assert len(e) == 2
        assert len(r) == 2
        assert len(c) == 0
