"""Plain-text and Markdown parser.

Migrated from LightRAG native text parser.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from aurora_ext.rag.parser.base import BaseParser, ParseResult

logger = logging.getLogger(__name__)


class TextParser(BaseParser):
    """Parser for .txt, .md, .mdx and other plain-text formats."""

    _EXTENSIONS = {"txt", "md", "mdx", "rtf", "tex", "log", "conf", "ini",
                   "properties", "sql", "bat", "sh", "c", "h", "cpp", "hpp",
                   "py", "java", "js", "ts", "swift", "go", "rb", "php",
                   "css", "scss", "less", "yaml", "yml", "json", "xml",
                   "html", "htm", "csv"}

    @property
    def supported_extensions(self) -> set[str]:
        return self._EXTENSIONS

    async def parse(self, file_path: str | Path, **kwargs: Any) -> ParseResult:
        path = Path(file_path)
        encoding = kwargs.get("encoding", "utf-8")

        try:
            text = path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            text = path.read_text(encoding="latin-1")

        return ParseResult(
            text=text,
            file_path=str(path),
            file_type=path.suffix.lstrip(".").lower(),
            metadata={"char_count": len(text)},
        )
