"""Document parsers — multi-format text extraction.

Migrated from LightRAG ``parser/`` module.  Each parser converts a
specific file format into plain text suitable for chunking and indexing.

Three parsing tiers:

1. **Native** (always available): PDF, DOCX, PPTX, XLSX, plain text
2. **MinerU** (optional): GPU-accelerated layout-aware parsing
3. **Docling** (optional): IBM's document converter, CPU-bound

Use filename hints (``file.[mineru].pdf``) or the
``AURORA_PARSER_ENGINE`` environment variable to select advanced engines.
"""

from aurora_ext.rag.parser.base import BaseParser, ParseResult
from aurora_ext.rag.parser.docling_parser import DoclingParser
from aurora_ext.rag.parser.mineru_parser import MinerUParser
from aurora_ext.rag.parser.routing import (
    SUPPORTED_EXTENSIONS,
    get_parser,
    parse_file,
    parse_filename_hints,
)

__all__ = [
    "BaseParser",
    "DoclingParser",
    "MinerUParser",
    "ParseResult",
    "SUPPORTED_EXTENSIONS",
    "get_parser",
    "parse_file",
    "parse_filename_hints",
]
