"""Fine-grained token budget control for RAG queries.

Tracks LLM and embedding token consumption, enforces per-category and
total token budgets, and provides usage statistics.

Priority ordering when truncating:
    entities (highest) → relations → chunks (lowest)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Tuple

from aurora_core.rag.utils.tokenizer import count_tokens

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TokenBudget:
    """Immutable token budget configuration.

    Attributes
    ----------
    max_entity_tokens:
        Maximum tokens allocated to entity descriptions.
    max_relation_tokens:
        Maximum tokens allocated to relationship descriptions.
    max_total_tokens:
        Maximum total tokens for the entire query context.
    max_chunk_tokens:
        Maximum tokens allocated to text chunk content.
    track_usage:
        Whether to track token consumption statistics.
    """

    max_entity_tokens: int = 5000
    max_relation_tokens: int = 5000
    max_total_tokens: int = 12000
    max_chunk_tokens: int = 8000
    track_usage: bool = True

    def with_overrides(self, **kwargs: int) -> TokenBudget:
        """Return a new TokenBudget with specific fields overridden."""
        return TokenBudget(
            max_entity_tokens=kwargs.get(
                "max_entity_tokens", self.max_entity_tokens
            ),
            max_relation_tokens=kwargs.get(
                "max_relation_tokens", self.max_relation_tokens
            ),
            max_total_tokens=kwargs.get(
                "max_total_tokens", self.max_total_tokens
            ),
            max_chunk_tokens=kwargs.get(
                "max_chunk_tokens", self.max_chunk_tokens
            ),
            track_usage=kwargs.get("track_usage", self.track_usage),
        )

    @classmethod
    def from_toml(cls, config: dict[str, Any]) -> TokenBudget:
        """Build a TokenBudget from a TOML configuration dict.

        Expected format::

            [token_budget]
            max_entity_tokens = 5000
            max_relation_tokens = 5000
            max_total_tokens = 12000
            max_chunk_tokens = 8000
            track_usage = true
        """
        budget_section = config.get("token_budget", config)
        return cls(
            max_entity_tokens=budget_section.get("max_entity_tokens", 5000),
            max_relation_tokens=budget_section.get("max_relation_tokens", 5000),
            max_total_tokens=budget_section.get("max_total_tokens", 12000),
            max_chunk_tokens=budget_section.get("max_chunk_tokens", 8000),
            track_usage=budget_section.get("track_usage", True),
        )


class TokenTracker:
    """Track token usage and enforce budgets across RAG query stages.

    Not thread-safe — instantiate one per request.
    """

    def __init__(self, budget: TokenBudget | None = None) -> None:
        self.budget = budget or TokenBudget()
        self._usage: dict[str, int] = {
            "llm_calls": 0,
            "llm_prompt_tokens": 0,
            "llm_completion_tokens": 0,
            "embedding_calls": 0,
            "embedding_tokens": 0,
            "total_tokens": 0,
            "truncation_events": 0,
        }
        self._category_usage: dict[str, int] = {
            "entity_tokens": 0,
            "relation_tokens": 0,
            "chunk_tokens": 0,
            "entities_before_truncation": 0,
            "entities_after_truncation": 0,
            "relations_before_truncation": 0,
            "relations_after_truncation": 0,
            "chunks_before_truncation": 0,
            "chunks_after_truncation": 0,
        }

    # ── Tracking Methods ────────────────────────────────────────────

    def track_llm_call(self, prompt_tokens: int, completion_tokens: int) -> None:
        """Record an LLM call's token consumption.

        Parameters
        ----------
        prompt_tokens:
            Number of tokens in the prompt (input).
        completion_tokens:
            Number of tokens in the completion (output).
        """
        if not self.budget.track_usage:
            return
        self._usage["llm_calls"] += 1
        self._usage["llm_prompt_tokens"] += prompt_tokens
        self._usage["llm_completion_tokens"] += completion_tokens
        self._usage["total_tokens"] += prompt_tokens + completion_tokens

    def track_embedding_call(self, tokens: int) -> None:
        """Record an embedding call's token consumption.

        Parameters
        ----------
        tokens:
            Number of tokens embedded.
        """
        if not self.budget.track_usage:
            return
        self._usage["embedding_calls"] += 1
        self._usage["embedding_tokens"] += tokens
        self._usage["total_tokens"] += tokens

    # ── Truncation ──────────────────────────────────────────────────

    def truncate_to_budget(
        self,
        entities: list[dict[str, Any]],
        relations: list[dict[str, Any]],
        chunks: list[dict[str, Any]],
    ) -> Tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        """Truncate context lists to fit within the token budget.

        Priority ordering (highest to lowest):
            1. Entities — critical for knowledge graph context
            2. Relations — connect entities
            3. Chunks — raw text, trimmed most aggressively

        Within each category, items are sorted by relevance score
        (descending) so the most relevant content is preserved.

        The total budget (entity + relation + chunk tokens) is a hard
        cap. Per-category budgets are soft caps within the total.

        Parameters
        ----------
        entities:
            List of entity dicts. Expected fields: ``description``,
            ``entity_name`` or ``id``. Optional: ``score`` / ``weight``.
        relations:
            List of relation dicts. Expected fields: ``description``,
            ``source_entity`` or ``src_id``, ``target_entity`` or
            ``tgt_id``. Optional: ``score`` / ``weight``.
        chunks:
            List of chunk dicts. Expected fields: ``content``.
            Optional: ``score`` / ``weight`` / ``rerank_score``.

        Returns
        -------
        tuple
            ``(truncated_entities, truncated_relations, truncated_chunks)``
        """
        # Record pre-truncation counts
        if self.budget.track_usage:
            self._category_usage["entities_before_truncation"] += len(entities)
            self._category_usage["relations_before_truncation"] += len(relations)
            self._category_usage["chunks_before_truncation"] += len(chunks)

        # Sort each category by score (descending) to preserve high-relevance items
        sorted_entities = self._sort_by_score(entities)
        sorted_relations = self._sort_by_score(relations)
        sorted_chunks = self._sort_by_score(chunks)

        # Phase 1: Truncate entities to per-category budget,
        # also capped by the total budget
        entity_budget = min(
            self.budget.max_entity_tokens,
            self.budget.max_total_tokens,
        )
        truncated_entities, entity_tokens = self._truncate_list(
            sorted_entities,
            text_field="description",
            max_tokens=entity_budget,
        )

        # Phase 2: Truncate relations to per-category budget,
        # also respecting remaining total budget
        remaining_after_entities = self.budget.max_total_tokens - entity_tokens
        relation_budget = min(
            self.budget.max_relation_tokens,
            max(0, remaining_after_entities),
        )
        truncated_relations, relation_tokens = self._truncate_list(
            sorted_relations,
            text_field="description",
            max_tokens=relation_budget,
        )

        # Phase 3: Truncate chunks to remaining total budget
        used_so_far = entity_tokens + relation_tokens
        remaining_for_chunks = max(
            0, self.budget.max_total_tokens - used_so_far
        )
        chunk_budget = min(self.budget.max_chunk_tokens, remaining_for_chunks)
        truncated_chunks, chunk_tokens = self._truncate_list(
            sorted_chunks,
            text_field="content",
            max_tokens=chunk_budget,
        )

        # Record post-truncation stats
        if self.budget.track_usage:
            self._category_usage["entity_tokens"] += entity_tokens
            self._category_usage["relation_tokens"] += relation_tokens
            self._category_usage["chunk_tokens"] += chunk_tokens
            self._category_usage["entities_after_truncation"] += len(
                truncated_entities
            )
            self._category_usage["relations_after_truncation"] += len(
                truncated_relations
            )
            self._category_usage["chunks_after_truncation"] += len(
                truncated_chunks
            )

            # Track if any truncation happened
            if (
                len(truncated_entities) < len(entities)
                or len(truncated_relations) < len(relations)
                or len(truncated_chunks) < len(chunks)
            ):
                self._usage["truncation_events"] += 1
                logger.debug(
                    "Token budget truncation: entities %d→%d (%d tokens), "
                    "relations %d→%d (%d tokens), chunks %d→%d (%d tokens)",
                    len(entities), len(truncated_entities), entity_tokens,
                    len(relations), len(truncated_relations), relation_tokens,
                    len(chunks), len(truncated_chunks), chunk_tokens,
                )

        return truncated_entities, truncated_relations, truncated_chunks

    # ── Statistics ──────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """Return a snapshot of current token usage statistics.

        Returns
        -------
        dict
            Usage breakdown including LLM calls, embedding calls,
            per-category token counts, and truncation events.
        """
        return {
            "budget": {
                "max_entity_tokens": self.budget.max_entity_tokens,
                "max_relation_tokens": self.budget.max_relation_tokens,
                "max_total_tokens": self.budget.max_total_tokens,
                "max_chunk_tokens": self.budget.max_chunk_tokens,
                "track_usage": self.budget.track_usage,
            },
            "usage": {
                "llm_calls": self._usage["llm_calls"],
                "llm_prompt_tokens": self._usage["llm_prompt_tokens"],
                "llm_completion_tokens": self._usage["llm_completion_tokens"],
                "embedding_calls": self._usage["embedding_calls"],
                "embedding_tokens": self._usage["embedding_tokens"],
                "total_tokens": self._usage["total_tokens"],
                "truncation_events": self._usage["truncation_events"],
            },
            "categories": {
                "entity_tokens": self._category_usage["entity_tokens"],
                "relation_tokens": self._category_usage["relation_tokens"],
                "chunk_tokens": self._category_usage["chunk_tokens"],
                "entities_before_truncation": self._category_usage[
                    "entities_before_truncation"
                ],
                "entities_after_truncation": self._category_usage[
                    "entities_after_truncation"
                ],
                "relations_before_truncation": self._category_usage[
                    "relations_before_truncation"
                ],
                "relations_after_truncation": self._category_usage[
                    "relations_after_truncation"
                ],
                "chunks_before_truncation": self._category_usage[
                    "chunks_before_truncation"
                ],
                "chunks_after_truncation": self._category_usage[
                    "chunks_after_truncation"
                ],
            },
        }

    def reset_stats(self) -> None:
        """Reset all usage counters to zero."""
        for key in self._usage:
            self._usage[key] = 0
        for key in self._category_usage:
            self._category_usage[key] = 0

    # ── Internal Helpers ────────────────────────────────────────────

    @staticmethod
    def _get_item_score(item: dict[str, Any]) -> float:
        """Extract the relevance score from an item dict.

        Checks ``rerank_score``, ``score``, and ``weight`` fields.
        Items without a score are treated as having score 0.0.
        """
        score = item.get("rerank_score")
        if score is not None:
            try:
                return float(score)
            except (TypeError, ValueError):
                pass
        score = item.get("score")
        if score is not None:
            try:
                return float(score)
            except (TypeError, ValueError):
                pass
        score = item.get("weight")
        if score is not None:
            try:
                return float(score)
            except (TypeError, ValueError):
                pass
        return 0.0

    @classmethod
    def _sort_by_score(
        cls, items: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Return items sorted by relevance score (descending).

        Creates a new list — does not mutate the input.
        """
        return sorted(items, key=cls._get_item_score, reverse=True)

    @staticmethod
    def _truncate_list(
        items: list[dict[str, Any]],
        text_field: str,
        max_tokens: int,
    ) -> Tuple[list[dict[str, Any]], int]:
        """Keep items until the token budget is exhausted.

        Each item's text is taken from ``text_field``. Items are added
        whole — no partial item truncation.

        Parameters
        ----------
        items:
            Already score-sorted list of item dicts.
        text_field:
            Dict key containing the text to count tokens for.
        max_tokens:
            Maximum tokens to allocate.

        Returns
        -------
        tuple
            ``(kept_items, total_tokens_used)``
        """
        result: list[dict[str, Any]] = []
        used = 0
        for item in items:
            text = item.get(text_field, "")
            tokens = count_tokens(text)
            if used + tokens > max_tokens:
                break
            result.append(item)
            used += tokens
        return result, used
