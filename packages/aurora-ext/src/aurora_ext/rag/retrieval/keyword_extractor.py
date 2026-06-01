"""LLM-driven keyword extraction for query routing.

Migrated from LightRAG ``operate.py`` ``get_keywords_from_query()``
and ``extract_keywords_only()``.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from aurora_core.model.base import BaseLLM
from aurora_core.schema.message import Message
from aurora_ext.rag.extraction.prompts import PROMPTS

logger = logging.getLogger(__name__)


class KeywordExtractor:
    """Extract high-level and low-level keywords from user queries.

    High-level keywords target abstract concepts/themes (for KG
    relationship search).  Low-level keywords target specific entities
    (for KG entity search).
    """

    def __init__(self, llm: BaseLLM) -> None:
        self._llm = llm

    async def extract(
        self,
        query: str,
        language: str = "English",
    ) -> tuple[list[str], list[str]]:
        """Extract (hl_keywords, ll_keywords) from *query*.

        Returns
        -------
        tuple[list[str], list[str]]
            (high_level_keywords, low_level_keywords)
        """
        examples = "\n".join(PROMPTS["keywords_extraction_examples"])
        prompt_text = PROMPTS["keywords_extraction"].format(
            language=language,
            examples=examples,
            query=query,
        )

        messages = [
            Message(role="user", content=prompt_text),
        ]

        try:
            output = await self._llm.achat(messages)
            result = self._parse_keywords(output.text)
            return result
        except Exception as exc:
            logger.warning("Keyword extraction failed: %s", exc)
            return [], []

    @staticmethod
    def _parse_keywords(text: str) -> tuple[list[str], list[str]]:
        """Parse the JSON keyword response from the LLM."""
        try:
            # Strip markdown code fences if present
            cleaned = text.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                cleaned = "\n".join(
                    line for line in lines
                    if not line.strip().startswith("```")
                )

            # Try json_repair for robust parsing
            try:
                from json_repair import repair_json
                data = json.loads(repair_json(cleaned))
            except ImportError:
                data = json.loads(cleaned)

            hl = data.get("high_level_keywords", [])
            ll = data.get("low_level_keywords", [])
            return hl, ll
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.warning("Failed to parse keywords from: %s", text[:200])
            return [], []
