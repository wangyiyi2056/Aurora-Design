"""Document parsers — multi-format text extraction.

Migrated from LightRAG ``parser/`` module.  Each parser converts a
specific file format into plain text suitable for chunking and indexing.
"""

from aurora_ext.rag.parser.base import BaseParser, ParseResult
from aurora_ext.rag.parser.routing import SUPPORTED_EXTENSIONS, get_parser

__all__ = [
    "BaseParser",
    "ParseResult",
    "SUPPORTED_EXTENSIONS",
    "get_parser",
]
