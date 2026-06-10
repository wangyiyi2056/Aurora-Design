"""Docling parser — IBM's document converter.

Docling (``docling``) provides unified document parsing for PDF, Office,
Markdown, HTML and image formats.  It uses layout analysis and table
structure recognition to produce high-quality Markdown output.

The parser is CPU-bound (no GPU required) and falls back gracefully when
the ``docling`` package is not installed.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from aurora_ext.rag.parser.base import BaseParser, ParseResult

logger = logging.getLogger(__name__)

_EXTENSIONS = {
    "pdf",
    "docx",
    "pptx",
    "xlsx",
    "md",
    "html", "htm",
    "png", "jpg", "jpeg", "tiff", "webp", "bmp",
}

_DEFAULT_MAX_PARALLEL = 2


class DoclingParser(BaseParser):
    """Document parser powered by IBM Docling.

    Configuration
    -------------
    ``DOCLING_MAX_PARALLEL``
        Maximum concurrent parse jobs (default ``2`` — CPU-bound).
    """

    def __init__(self, *, max_parallel: int | None = None) -> None:
        self._max_parallel = max_parallel or int(
            os.environ.get("DOCLING_MAX_PARALLEL", str(_DEFAULT_MAX_PARALLEL))
        )
        self._semaphore = asyncio.Semaphore(self._max_parallel)

    @property
    def supported_extensions(self) -> set[str]:
        return _EXTENSIONS

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    @staticmethod
    def _sdk_available() -> bool:
        """Check whether ``docling`` is importable."""
        try:
            import docling  # noqa: F401
            return True
        except ImportError:
            return False

    def is_available(self) -> bool:
        """Return ``True`` when the Docling SDK is usable."""
        return self._sdk_available()

    # ------------------------------------------------------------------
    # Core parse
    # ------------------------------------------------------------------

    async def parse(self, file_path: str | Path, **kwargs: Any) -> ParseResult:
        path = Path(file_path)
        ext = path.suffix.lstrip(".").lower()
        if ext not in _EXTENSIONS:
            raise ValueError(
                f"Docling does not support '.{ext}'. "
                f"Supported: {sorted(_EXTENSIONS)}"
            )

        if not self._sdk_available():
            raise ValueError(
                "Docling is not installed. Install with "
                "`pip install docling`."
            )

        async with self._semaphore:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, self._extract, path, kwargs)

    # ------------------------------------------------------------------
    # Extraction (runs in a worker thread)
    # ------------------------------------------------------------------

    @staticmethod
    def _extract(path: Path, kwargs: dict[str, Any]) -> ParseResult:
        """Synchronous Docling extraction — runs in a worker thread."""
        from docling.document_converter import DocumentConverter, ConversionError  # type: ignore[import-untyped]

        try:
            converter = DocumentConverter()
            result = converter.convert(str(path))
        except ConversionError as exc:
            raise ValueError(f"Docling failed to convert: {path}") from exc
        except Exception as exc:
            raise ValueError(
                f"Unexpected Docling error for {path}: {exc}"
            ) from exc

        markdown_text: str = result.document.export_to_markdown()

        element_counts: dict[str, int] = {}
        for element in result.document.texts:
            tag = getattr(element, "tag", "unknown")
            element_counts[tag] = element_counts.get(tag, 0) + 1

        table_count = len(result.document.tables)

        metadata: dict[str, Any] = {
            "parser_engine": "docling",
            "char_count": len(markdown_text),
            "table_count": table_count,
            "element_counts": element_counts,
        }

        return ParseResult(
            text=markdown_text.strip(),
            file_path=str(path),
            file_type=path.suffix.lstrip(".").lower(),
            metadata=metadata,
        )
