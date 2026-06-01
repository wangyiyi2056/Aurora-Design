"""Parser routing — select parser by file extension.

Migrated from LightRAG ``parser/routing.py``.  The router maps file
extensions to parser instances and also supports filename hints
(e.g. ``doc.[native].docx``) for per-file parser selection.

Supported extensions (46 types, migrated from LightRAG):
    .txt .md .mdx .pdf .docx .pptx .xlsx .rtf .odt .tex .epub
    .html .htm .csv .json .xml .yaml .yml .log .conf .ini .properties
    .sql .bat .sh .c .h .cpp .hpp .py .java .js .ts .swift .go .rb
    .php .css .scss .less
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from aurora_ext.rag.parser.base import BaseParser, ParseResult
from aurora_ext.rag.parser.docx_parser import DocxParser
from aurora_ext.rag.parser.pdf_parser import PDFParser
from aurora_ext.rag.parser.pptx_parser import PptxParser
from aurora_ext.rag.parser.text_parser import TextParser
from aurora_ext.rag.parser.xlsx_parser import XlsxParser

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS: set[str] = {
    "txt", "md", "mdx", "pdf", "docx", "pptx", "xlsx", "xls",
    "rtf", "odt", "tex", "html", "htm", "csv",
    "json", "xml", "yaml", "yml", "log", "conf", "ini", "properties",
    "sql", "bat", "sh", "c", "h", "cpp", "hpp", "py", "java",
    "js", "ts", "swift", "go", "rb", "php", "css", "scss", "less",
}

_HINT_RE = re.compile(r"^(?P<base>.+)\.\[(?P<hints>[^\]]+)\]\.(?P<ext>\w+)$")

_PARSERS: list[BaseParser] = [
    PDFParser(),
    DocxParser(),
    PptxParser(),
    XlsxParser(),
    TextParser(),
]

_PARSER_MAP: dict[str, BaseParser] = {}
for _p in _PARSERS:
    for _ext in _p.supported_extensions:
        _PARSER_MAP[_ext] = _p


def parse_filename_hints(filename: str) -> dict[str, Any]:
    """Extract parser/process hints from a filename.

    Format: ``name.[hints].ext``

    Hints:
    - ``native`` / ``mineru`` / ``docling`` — parser engine
    - ``i`` — VLM image analysis
    - ``t`` — VLM table analysis
    - ``e`` — VLM equation analysis
    - ``!`` — skip knowledge graph extraction
    - ``F`` — fixed-length chunking (default)
    - ``R`` — recursive semantic chunking
    - ``V`` — vector-driven semantic chunking
    - ``P`` — paragraph-driven semantic chunking
    """
    match = _HINT_RE.match(filename)
    if not match:
        return {"file_path": filename}

    hints_str = match.group("hints")
    result: dict[str, Any] = {
        "base_name": match.group("base"),
        "file_path": filename,
    }

    # Check for engine names first (they are multi-character keywords)
    engine_names = {"native", "mineru", "docling"}
    remaining = hints_str
    for engine in engine_names:
        if engine in remaining:
            result["parser_engine"] = engine
            remaining = remaining.replace(engine, "", 1)
            break

    # Parse remaining single-character flags
    chunk_map = {"F": "fixed", "R": "recursive", "V": "semantic", "P": "paragraph"}
    for char in remaining:
        if char in chunk_map:
            result["chunk_strategy"] = chunk_map[char]
        elif char == "i":
            result["vlm_image"] = True
        elif char == "t":
            result["vlm_table"] = True
        elif char == "e":
            result["vlm_equation"] = True
        elif char == "!":
            result["skip_kg"] = True

    return result


def get_parser(file_path: str | Path) -> BaseParser:
    """Select the appropriate parser for *file_path*.

    Raises ``ValueError`` if no parser supports the extension.
    """
    ext = Path(file_path).suffix.lstrip(".").lower()
    parser = _PARSER_MAP.get(ext)
    if parser is None:
        raise ValueError(
            f"No parser for extension '.{ext}'. "
            f"Supported: {sorted(SUPPORTED_EXTENSIONS)}"
        )
    return parser


async def parse_file(file_path: str | Path, **kwargs: Any) -> ParseResult:
    """Parse a file using the appropriate parser.

    Convenience function that selects the parser and calls ``parse()``.
    """
    parser = get_parser(file_path)
    return await parser.parse(file_path, **kwargs)
