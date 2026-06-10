"""Parser routing — select parser by file extension, hint, or env override.

Migrated from LightRAG ``parser/routing.py``.  The router maps file
extensions to parser instances and also supports filename hints
(e.g. ``doc.[native].docx``) for per-file parser selection.

Routing priority (highest → lowest):
    1. Filename hint  ``.[engine].``  (``native``, ``mineru``, ``docling``)
    2. Environment variable  ``AURORA_PARSER_ENGINE=ext:engine``
    3. Default parser for the extension (with fallback)

Supported extensions (46+ types, migrated from LightRAG):
    .txt .md .mdx .pdf .docx .pptx .xlsx .rtf .odt .tex .epub
    .html .htm .csv .json .xml .yaml .yml .log .conf .ini .properties
    .sql .bat .sh .c .h .cpp .hpp .py .java .js .ts .swift .go .rb
    .php .css .scss .less
    + MinerU image formats: .png .jpg .jpeg .webp .gif .bmp
    + Docling image formats: .tiff
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

from aurora_ext.rag.parser.base import BaseParser, ParseResult
from aurora_ext.rag.parser.docling_parser import DoclingParser
from aurora_ext.rag.parser.docx_parser import DocxParser
from aurora_ext.rag.parser.mineru_parser import MinerUParser
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
    "doc", "ppt",
    "png", "jpg", "jpeg", "webp", "gif", "bmp", "tiff",
}

_HINT_RE = re.compile(r"^(?P<base>.+)\.\[(?P<hints>[^\]]+)\]\.(?P<ext>\w+)$")

# ── Native parsers (always available) ────────────────────────────────

_NATIVE_PARSERS: list[BaseParser] = [
    PDFParser(),
    DocxParser(),
    PptxParser(),
    XlsxParser(),
    TextParser(),
]

_NATIVE_PARSER_MAP: dict[str, BaseParser] = {}
for _p in _NATIVE_PARSERS:
    for _ext in _p.supported_extensions:
        _NATIVE_PARSER_MAP[_ext] = _p

# ── Advanced parsers (optional, lazy-initialised) ────────────────────

_mineru_parser: MinerUParser | None = None
_docling_parser: DoclingParser | None = None


def _get_mineru() -> MinerUParser:
    global _mineru_parser
    if _mineru_parser is None:
        _mineru_parser = MinerUParser()
    return _mineru_parser


def _get_docling() -> DoclingParser:
    global _docling_parser
    if _docling_parser is None:
        _docling_parser = DoclingParser()
    return _docling_parser


# ── Engine name → parser lookup ──────────────────────────────────────

_ENGINE_MAP: dict[str, Any] = {
    "mineru": _get_mineru,
    "docling": _get_docling,
}


def _resolve_engine(engine_name: str) -> BaseParser | None:
    """Resolve an engine name to a parser, or ``None`` if unavailable."""
    factory = _ENGINE_MAP.get(engine_name)
    if factory is None:
        return None
    parser = factory()
    if hasattr(parser, "is_available") and not parser.is_available():
        logger.info("Parser engine '%s' requested but not available", engine_name)
        return None
    return parser


def _env_engine(ext: str) -> str | None:
    """Parse ``AURORA_PARSER_ENGINE`` env var for the given extension.

    Format: ``ext:engine`` or comma-separated ``ext:engine`` pairs.
    Example: ``pdf:mineru`` or ``pdf:mineru,docx:docling``
    """
    raw = os.environ.get("AURORA_PARSER_ENGINE", "")
    if not raw:
        return None
    for pair in raw.split(","):
        pair = pair.strip()
        if ":" not in pair:
            continue
        pair_ext, pair_engine = pair.split(":", 1)
        if pair_ext.strip().lower() == ext:
            return pair_engine.strip().lower()
    return None


# ── Filename hint parsing ────────────────────────────────────────────


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


# ── Parser selection ─────────────────────────────────────────────────


def get_parser(file_path: str | Path, **kwargs: Any) -> BaseParser:
    """Select the appropriate parser for *file_path*.

    Routing priority:
        1. ``parser_engine`` keyword argument (from hint parsing)
        2. ``AURORA_PARSER_ENGINE`` environment variable
        3. Default native parser for the extension

    Falls back to native parser when the requested advanced engine is
    unavailable.

    Raises ``ValueError`` if no parser supports the extension.
    """
    path = Path(file_path)
    ext = path.suffix.lstrip(".").lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"No parser for extension '.{ext}'. "
            f"Supported: {sorted(SUPPORTED_EXTENSIONS)}"
        )

    # 1. Explicit engine request (from hint or caller)
    engine_name: str | None = kwargs.get("parser_engine")

    # 2. Environment variable override
    if engine_name is None:
        engine_name = _env_engine(ext)

    if engine_name and engine_name != "native":
        parser = _resolve_engine(engine_name)
        if parser is not None:
            return parser
        logger.warning(
            "Requested engine '%s' for '.%s' is unavailable, "
            "falling back to native parser",
            engine_name,
            ext,
        )

    # 3. Default native parser
    native = _NATIVE_PARSER_MAP.get(ext)
    if native is not None:
        return native

    # No native parser — try advanced parsers as last resort
    for try_engine in ("mineru", "docling"):
        parser = _resolve_engine(try_engine)
        if parser is not None and ext in parser.supported_extensions:
            return parser

    raise ValueError(
        f"No parser for extension '.{ext}'. "
        f"Supported: {sorted(SUPPORTED_EXTENSIONS)}"
    )


async def parse_file(
    file_path: str | Path,
    *,
    parser_engine: str | None = None,
    **kwargs: Any,
) -> ParseResult:
    """Parse a file using the appropriate parser.

    Parameters
    ----------
    file_path:
        Path to the document.
    parser_engine:
        Force a specific engine (``"native"``, ``"mineru"``, ``"docling"``).
        Overrides environment variable and default routing.
    **kwargs:
        Forwarded to the selected parser's ``parse()`` method.
    """
    hints = parse_filename_hints(Path(file_path).name)
    engine = parser_engine or hints.get("parser_engine")

    parser = get_parser(file_path, parser_engine=engine)
    return await parser.parse(file_path, **kwargs)
