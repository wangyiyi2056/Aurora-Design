"""PDF parser using pypdf.

Migrated from LightRAG native PDF parser.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from aurora_ext.rag.parser.base import BaseParser, ParseResult

logger = logging.getLogger(__name__)


class PDFParser(BaseParser):
    """Parser for .pdf files using ``pypdf``."""

    _EXTENSIONS = {"pdf"}

    @property
    def supported_extensions(self) -> set[str]:
        return self._EXTENSIONS

    async def parse(self, file_path: str | Path, **kwargs: Any) -> ParseResult:
        import os

        from pypdf import PdfReader

        path = Path(file_path)
        password = kwargs.get("password") or os.environ.get("PDF_DECRYPT_PASSWORD")

        try:
            reader = PdfReader(str(path))
        except Exception as exc:
            raise ValueError(f"Cannot open PDF: {path}") from exc

        if reader.is_encrypted:
            if password is None:
                raise ValueError(f"PDF is encrypted: {path}")
            try:
                reader.decrypt(password)
            except Exception as exc:
                raise ValueError(f"Failed to decrypt PDF: {path}") from exc

        pages_text: list[str] = []
        for i, page in enumerate(reader.pages):
            try:
                text = page.extract_text() or ""
                pages_text.append(text)
            except Exception as exc:
                logger.warning("Failed to extract text from page %d of %s: %s", i, path, exc)

        full_text = "\n\n".join(pages_text)

        return ParseResult(
            text=full_text,
            file_path=str(path),
            file_type="pdf",
            metadata={
                "page_count": len(reader.pages),
                "char_count": len(full_text),
            },
        )
