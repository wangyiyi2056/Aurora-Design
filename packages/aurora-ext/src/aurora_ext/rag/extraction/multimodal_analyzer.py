"""Multimodal VLM analysis layer for images, tables, and equations.

Provides :class:`MultimodalAnalyzer` which wraps a VLM role from the
:class:`LLMRoleRegistry` and exposes three analysis modes:

- **image** (``i`` hint): Describe or extract information from images
- **table** (``t`` hint): Analyse tabular data, extract structured rows
- **equation** (``e`` hint): Recognise and interpret mathematical formulae

Each analysis method returns a :class:`MultimodalAnalysisResult` that is
stored in ``doc_status.metadata`` for downstream consumption by the
extraction pipeline.
"""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, List

from aurora_core.model.roles import LLMRole, LLMRoleRegistry
from aurora_core.schema.message import Message

logger = logging.getLogger(__name__)


# ── Analysis modes ────────────────────────────────────────────────


class AnalysisMode(str, Enum):
    """VLM analysis modes triggered by filename hints."""

    IMAGE = "image"       # ``i`` hint
    TABLE = "table"       # ``t`` hint
    EQUATION = "equation" # ``e`` hint


# ── Result types ──────────────────────────────────────────────────


@dataclass(frozen=True)
class MultimodalAnalysisResult:
    """Result of a single VLM analysis call.

    Attributes
    ----------
    mode:
        Which analysis mode produced this result.
    description:
        Free-form textual description from the VLM.
    structured_data:
        Optional structured extraction (JSON-serialisable).
    confidence:
        Self-reported confidence from 0.0 to 1.0 (if available).
    source_index:
        Index of the source element within the document (page, figure, etc.).
    raw_response:
        The raw VLM response text (for debugging / audit).
    """

    mode: AnalysisMode
    description: str
    structured_data: dict[str, Any] | None = None
    confidence: float = 0.0
    source_index: int = 0
    raw_response: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict for metadata storage."""
        return {
            "mode": self.mode.value,
            "description": self.description,
            "structured_data": self.structured_data,
            "confidence": self.confidence,
            "source_index": self.source_index,
        }


@dataclass
class DocumentAnalysisReport:
    """Aggregated VLM analysis results for a single document.

    Attributes
    ----------
    image_results:
        Results from image analysis.
    table_results:
        Results from table analysis.
    equation_results:
        Results from equation analysis.
    """

    image_results: list[MultimodalAnalysisResult] = field(default_factory=list)
    table_results: list[MultimodalAnalysisResult] = field(default_factory=list)
    equation_results: list[MultimodalAnalysisResult] = field(default_factory=list)

    @property
    def total_count(self) -> int:
        return (
            len(self.image_results)
            + len(self.table_results)
            + len(self.equation_results)
        )

    def to_metadata_dict(self) -> dict[str, Any]:
        """Convert to a dict suitable for storing in ``doc_status.metadata``."""
        return {
            "vlm_analysis": {
                "images": [r.to_dict() for r in self.image_results],
                "tables": [r.to_dict() for r in self.table_results],
                "equations": [r.to_dict() for r in self.equation_results],
                "total_analysed": self.total_count,
            }
        }


# ── Prompts ───────────────────────────────────────────────────────

_IMAGE_SYSTEM_PROMPT = (
    "You are a visual analysis assistant. Describe the provided image "
    "in detail. Focus on:\n"
    "1. Key objects, people, or scenes visible\n"
    "2. Text or labels visible in the image\n"
    "3. Relationships between elements\n"
    "4. Any data or information that could be extracted\n\n"
    "Respond in the same language as any text visible in the image. "
    "If the image contains technical or scientific content, provide "
    "precise domain-specific descriptions."
)

_TABLE_SYSTEM_PROMPT = (
    "You are a tabular data analysis assistant. Analyse the provided "
    "table image and extract structured data.\n\n"
    "Return a JSON object with the following structure:\n"
    "```json\n"
    "{\n"
    '  "title": "table title or description",\n'
    '  "headers": ["column1", "column2", ...],\n'
    '  "rows": [["cell1", "cell2", ...], ...],\n'
    '  "summary": "brief summary of the table content",\n'
    '  "notes": "any footnotes or special observations"\n'
    "}\n"
    "```\n\n"
    "Be precise with numbers and preserve the original data exactly."
)

_EQUATION_SYSTEM_PROMPT = (
    "You are a mathematical formula recognition assistant. Analyse the "
    "provided equation/formula image and:\n\n"
    "1. Transcribe the formula in LaTeX notation\n"
    "2. Explain what the formula represents\n"
    "3. Define each variable and constant\n"
    "4. Note the domain or field this formula belongs to\n\n"
    "Return a JSON object:\n"
    "```json\n"
    "{\n"
    '  "latex": "LaTeX representation",\n'
    '  "description": "what the formula computes or represents",\n'
    '  "variables": {"var_name": "meaning", ...},\n'
    '  "field": "mathematics/physics/engineering/etc"\n'
    "}\n"
    "```"
)


# ── Main analyzer class ──────────────────────────────────────────


class MultimodalAnalyzer:
    """Multimodal VLM analyzer for the knowledge ingestion pipeline.

    Uses the VLM role from :class:`LLMRoleRegistry` to analyse images,
    tables, and equations found in documents. Analysis results are
    returned as structured data that enriches the downstream extraction.

    Parameters
    ----------
    role_registry:
        The LLM role registry providing access to the VLM model.
    """

    def __init__(self, role_registry: LLMRoleRegistry) -> None:
        self._registry = role_registry

    # ── Public API ────────────────────────────────────────────────

    async def analyze_image(
        self,
        image_data: bytes | str,
        *,
        context: str = "",
        source_index: int = 0,
        mime_type: str = "image/png",
    ) -> MultimodalAnalysisResult:
        """Analyse an image using the VLM.

        Parameters
        ----------
        image_data:
            Raw image bytes or a base64-encoded string.
        context:
            Optional surrounding text context for better analysis.
        source_index:
            Index of this image within the document.
        mime_type:
            MIME type of the image (default ``image/png``).

        Returns
        -------
        MultimodalAnalysisResult
            Structured analysis result.
        """
        b64_data = self._to_base64(image_data)
        user_content = self._build_image_message(b64_data, context, mime_type)

        raw_response = await self._call_vlm(
            system_prompt=_IMAGE_SYSTEM_PROMPT,
            user_content=user_content,
        )

        return MultimodalAnalysisResult(
            mode=AnalysisMode.IMAGE,
            description=raw_response,
            source_index=source_index,
            raw_response=raw_response,
        )

    async def analyze_table(
        self,
        table_data: bytes | str,
        *,
        context: str = "",
        source_index: int = 0,
        mime_type: str = "image/png",
    ) -> MultimodalAnalysisResult:
        """Analyse a table image and extract structured tabular data.

        Parameters
        ----------
        table_data:
            Table image as raw bytes or base64-encoded string.
        context:
            Optional surrounding text (caption, headers, etc.).
        source_index:
            Index of this table within the document.
        mime_type:
            MIME type of the image.

        Returns
        -------
        MultimodalAnalysisResult
            Result with ``structured_data`` containing headers, rows, etc.
        """
        b64_data = self._to_base64(table_data)
        user_content = self._build_image_message(b64_data, context, mime_type)

        raw_response = await self._call_vlm(
            system_prompt=_TABLE_SYSTEM_PROMPT,
            user_content=user_content,
        )

        structured = self._try_parse_json(raw_response)

        description = ""
        if structured and isinstance(structured, dict):
            description = structured.get("summary", raw_response[:200])
        else:
            description = raw_response

        return MultimodalAnalysisResult(
            mode=AnalysisMode.TABLE,
            description=description,
            structured_data=structured if isinstance(structured, dict) else None,
            source_index=source_index,
            raw_response=raw_response,
        )

    async def analyze_equation(
        self,
        equation_data: bytes | str,
        *,
        context: str = "",
        source_index: int = 0,
        mime_type: str = "image/png",
    ) -> MultimodalAnalysisResult:
        """Analyse an equation/formula image and extract LaTeX + semantics.

        Parameters
        ----------
        equation_data:
            Equation image as raw bytes or base64-encoded string.
        context:
            Optional surrounding text (section title, paragraph, etc.).
        source_index:
            Index of this equation within the document.
        mime_type:
            MIME type of the image.

        Returns
        -------
        MultimodalAnalysisResult
            Result with ``structured_data`` containing LaTeX, variables, etc.
        """
        b64_data = self._to_base64(equation_data)
        user_content = self._build_image_message(b64_data, context, mime_type)

        raw_response = await self._call_vlm(
            system_prompt=_EQUATION_SYSTEM_PROMPT,
            user_content=user_content,
        )

        structured = self._try_parse_json(raw_response)

        description = ""
        if structured and isinstance(structured, dict):
            latex = structured.get("latex", "")
            desc = structured.get("description", "")
            description = f"{latex}: {desc}" if latex else desc or raw_response[:200]
        else:
            description = raw_response

        return MultimodalAnalysisResult(
            mode=AnalysisMode.EQUATION,
            description=description,
            structured_data=structured if isinstance(structured, dict) else None,
            source_index=source_index,
            raw_response=raw_response,
        )

    async def analyze_document(
        self,
        *,
        images: list[dict[str, Any]] | None = None,
        tables: list[dict[str, Any]] | None = None,
        equations: list[dict[str, Any]] | None = None,
        enabled_modes: set[AnalysisMode] | None = None,
    ) -> DocumentAnalysisReport:
        """Analyse all multimodal elements in a document.

        Parameters
        ----------
        images:
            List of dicts with ``data`` (bytes/b64), optional ``context``,
            and optional ``mime_type``.
        tables:
            List of dicts with ``data``, optional ``context``, ``mime_type``.
        equations:
            List of dicts with ``data``, optional ``context``, ``mime_type``.
        enabled_modes:
            Set of enabled modes. If ``None``, all modes are enabled.

        Returns
        -------
        DocumentAnalysisReport
            Aggregated analysis report.
        """
        modes = enabled_modes or {m for m in AnalysisMode}
        report = DocumentAnalysisReport()

        if images and AnalysisMode.IMAGE in modes:
            for idx, img in enumerate(images):
                try:
                    result = await self.analyze_image(
                        img["data"],
                        context=img.get("context", ""),
                        source_index=img.get("index", idx),
                        mime_type=img.get("mime_type", "image/png"),
                    )
                    report.image_results.append(result)
                except Exception:
                    logger.exception(
                        "VLM image analysis failed for image %d", idx
                    )

        if tables and AnalysisMode.TABLE in modes:
            for idx, tbl in enumerate(tables):
                try:
                    result = await self.analyze_table(
                        tbl["data"],
                        context=tbl.get("context", ""),
                        source_index=tbl.get("index", idx),
                        mime_type=tbl.get("mime_type", "image/png"),
                    )
                    report.table_results.append(result)
                except Exception:
                    logger.exception(
                        "VLM table analysis failed for table %d", idx
                    )

        if equations and AnalysisMode.EQUATION in modes:
            for idx, eq in enumerate(equations):
                try:
                    result = await self.analyze_equation(
                        eq["data"],
                        context=eq.get("context", ""),
                        source_index=eq.get("index", idx),
                        mime_type=eq.get("mime_type", "image/png"),
                    )
                    report.equation_results.append(result)
                except Exception:
                    logger.exception(
                        "VLM equation analysis failed for equation %d", idx
                    )

        logger.info(
            "VLM analysis complete: %d images, %d tables, %d equations",
            len(report.image_results),
            len(report.table_results),
            len(report.equation_results),
        )

        return report

    # ── Helpers ───────────────────────────────────────────────────

    async def _call_vlm(
        self,
        *,
        system_prompt: str,
        user_content: str | List[dict[str, Any]],
    ) -> str:
        """Send a message to the VLM role and return the text response.

        Acquires the VLM semaphore for concurrency control.
        """
        llm = await self._registry.get_llm(LLMRole.VLM)
        semaphore = self._registry.get_semaphore(LLMRole.VLM)

        messages: list[Message] = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_content),
        ]

        async with semaphore:
            output = await llm.achat(messages)
            return output.text

    @staticmethod
    def _to_base64(data: bytes | str) -> str:
        """Convert raw bytes or string to a base64-encoded string."""
        if isinstance(data, bytes):
            return base64.b64encode(data).decode("utf-8")
        return data

    @staticmethod
    def _build_image_message(
        b64_data: str,
        context: str,
        mime_type: str,
    ) -> list[dict[str, Any]]:
        """Build a multimodal message content array with image + text."""
        content: list[dict[str, Any]] = []

        if context:
            content.append({
                "type": "text",
                "text": f"Context: {context}\n\nPlease analyse the following image:",
            })
        else:
            content.append({
                "type": "text",
                "text": "Please analyse the following image:",
            })

        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:{mime_type};base64,{b64_data}",
            },
        })

        return content

    @staticmethod
    def _try_parse_json(text: str) -> dict | list | None:
        """Best-effort JSON extraction from VLM responses.

        Handles markdown code fences and partial JSON.
        """
        import json_repair

        cleaned = text.strip()

        # Strip markdown code fences
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Remove first and last lines if they're fences
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines)

        try:
            return json_repair.loads(cleaned)
        except Exception:
            logger.debug("Failed to parse JSON from VLM response")
            return None


# ── Utility functions ─────────────────────────────────────────────


def get_enabled_modes(parse_options: dict[str, Any]) -> set[AnalysisMode]:
    """Derive enabled VLM modes from filename parse options.

    The filename hint parser (``routing.parse_filename_hints``) sets
    boolean flags for each VLM mode:

    - ``vlm_image`` → :attr:`AnalysisMode.IMAGE`
    - ``vlm_table`` → :attr:`AnalysisMode.TABLE`
    - ``vlm_equation`` → :attr:`AnalysisMode.EQUATION`

    Parameters
    ----------
    parse_options:
        The ``parse_options`` dict from ``DocStatusInfo.metadata``.

    Returns
    -------
    set[AnalysisMode]
        The set of enabled modes (may be empty if no VLM hints present).
    """
    modes: set[AnalysisMode] = set()
    if parse_options.get("vlm_image"):
        modes.add(AnalysisMode.IMAGE)
    if parse_options.get("vlm_table"):
        modes.add(AnalysisMode.TABLE)
    if parse_options.get("vlm_equation"):
        modes.add(AnalysisMode.EQUATION)
    return modes


def has_vlm_hints(parse_options: dict[str, Any]) -> bool:
    """Check whether any VLM analysis hints are present."""
    return bool(
        parse_options.get("vlm_image")
        or parse_options.get("vlm_table")
        or parse_options.get("vlm_equation")
    )
