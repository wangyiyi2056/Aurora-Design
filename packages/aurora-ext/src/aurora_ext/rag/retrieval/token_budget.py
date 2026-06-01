"""Token budget allocation for query context.

Migrated from LightRAG ``operate.py`` ``_apply_token_truncation()``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aurora_core.rag.utils.tokenizer import count_tokens


@dataclass
class TokenBudget:
    """Token budget configuration for a query.

    Attributes
    ----------
    max_entity_tokens:
        Maximum tokens allocated to entity descriptions.
    max_relation_tokens:
        Maximum tokens allocated to relationship descriptions.
    max_total_tokens:
        Maximum total tokens for the entire context.
    max_chunk_tokens:
        Maximum tokens allocated to text chunk content.
    """

    max_entity_tokens: int = 6000
    max_relation_tokens: int = 8000
    max_total_tokens: int = 30000
    max_chunk_tokens: int = 8000

    def truncate_entities(
        self, entities: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Truncate entity list to fit within entity token budget."""
        return self._truncate_by_field(
            entities, "description", self.max_entity_tokens
        )

    def truncate_relations(
        self, relations: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Truncate relation list to fit within relation token budget."""
        return self._truncate_by_field(
            relations, "description", self.max_relation_tokens
        )

    def truncate_chunks(
        self, chunks: list[dict[str, Any]], reserved: int = 0
    ) -> list[dict[str, Any]]:
        """Truncate chunk list to fit within remaining total budget."""
        remaining = self.max_total_tokens - reserved
        chunk_budget = min(self.max_chunk_tokens, max(0, remaining))
        return self._truncate_by_field(chunks, "content", chunk_budget)

    @staticmethod
    def _truncate_by_field(
        items: list[dict[str, Any]],
        field: str,
        max_tokens: int,
    ) -> list[dict[str, Any]]:
        """Keep items until token budget is exhausted."""
        result: list[dict[str, Any]] = []
        used = 0
        for item in items:
            text = item.get(field, "")
            tokens = count_tokens(text)
            if used + tokens > max_tokens:
                break
            result.append(item)
            used += tokens
        return result
