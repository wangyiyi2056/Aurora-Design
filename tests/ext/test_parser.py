"""Tests for document parsers — routing, hints, and parser interface.

Covers:
    - BaseParser interface compliance (MinerU, Docling)
    - Filename hint parsing (engine, chunk strategy, VLM flags)
    - Routing priority: hint → env var → default
    - Graceful fallback when advanced engines are unavailable
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

import pytest

from aurora_ext.rag.parser import (
    BaseParser,
    DoclingParser,
    MinerUParser,
    ParseResult,
    get_parser,
    parse_file,
    parse_filename_hints,
)
from aurora_ext.rag.parser.docx_parser import DocxParser
from aurora_ext.rag.parser.pdf_parser import PDFParser
from aurora_ext.rag.parser.pptx_parser import PptxParser
from aurora_ext.rag.parser.text_parser import TextParser
from aurora_ext.rag.parser.xlsx_parser import XlsxParser


# ── Interface compliance ─────────────────────────────────────────────


class TestBaseParserInterface:
    """Verify MinerU and Docling parsers implement BaseParser correctly."""

    def test_mineru_is_base_parser(self):
        parser = MinerUParser()
        assert isinstance(parser, BaseParser)

    def test_docling_is_base_parser(self):
        parser = DoclingParser()
        assert isinstance(parser, BaseParser)

    def test_mineru_extensions(self):
        parser = MinerUParser()
        exts = parser.supported_extensions
        for required in ("pdf", "docx", "pptx", "xlsx", "png", "jpg"):
            assert required in exts, f"MinerU missing '{required}'"

    def test_docling_extensions(self):
        parser = DoclingParser()
        exts = parser.supported_extensions
        for required in ("pdf", "docx", "pptx", "xlsx", "md", "html"):
            assert required in exts, f"Docling missing '{required}'"

    def test_mineru_can_handle(self):
        parser = MinerUParser()
        assert parser.can_handle("report.pdf")
        assert parser.can_handle("scan.[mineru].png")
        assert not parser.can_handle("data.txt")

    def test_docling_can_handle(self):
        parser = DoclingParser()
        assert parser.can_handle("report.pdf")
        assert parser.can_handle("page.html")
        assert not parser.can_handle("data.txt")

    def test_mineru_unavailable_raises(self):
        """MinerU parse should raise ValueError when neither SDK nor API is available."""
        parser = MinerUParser()
        # Clear env to ensure no API URL
        old = os.environ.pop("MINERU_API_URL", None)
        try:
            if not parser._sdk_available():
                with pytest.raises(ValueError, match="not available"):
                    asyncio.get_event_loop().run_until_complete(
                        parser.parse("/tmp/test.pdf")
                    )
        finally:
            if old:
                os.environ["MINERU_API_URL"] = old

    def test_docling_unavailable_raises(self):
        """Docling parse should raise ValueError when SDK is not installed."""
        parser = DoclingParser()
        if not parser._sdk_available():
            with pytest.raises(ValueError, match="not installed"):
                asyncio.get_event_loop().run_until_complete(
                    parser.parse("/tmp/test.pdf")
                )


# ── Filename hint parsing ────────────────────────────────────────────


class TestFilenameHints:

    def test_no_hint(self):
        result = parse_filename_hints("report.pdf")
        assert result == {"file_path": "report.pdf"}

    def test_mineru_hint(self):
        result = parse_filename_hints("report.[mineru].pdf")
        assert result["parser_engine"] == "mineru"
        assert result["base_name"] == "report"

    def test_docling_hint(self):
        result = parse_filename_hints("data.[docling].docx")
        assert result["parser_engine"] == "docling"

    def test_native_hint(self):
        result = parse_filename_hints("scan.[native].pdf")
        assert result["parser_engine"] == "native"

    def test_combined_hint(self):
        result = parse_filename_hints("doc.[mineruR].pdf")
        assert result["parser_engine"] == "mineru"
        assert result["chunk_strategy"] == "recursive"

    def test_skip_kg_hint(self):
        result = parse_filename_hints("raw.[!].txt")
        assert result["skip_kg"] is True

    def test_vlm_hints(self):
        result = parse_filename_hints("scan.[ite].pdf")
        assert result["vlm_image"] is True
        assert result["vlm_table"] is True
        assert result["vlm_equation"] is True

    def test_chunk_strategies(self):
        assert parse_filename_hints("a.[F].txt")["chunk_strategy"] == "fixed"
        assert parse_filename_hints("a.[R].txt")["chunk_strategy"] == "recursive"
        assert parse_filename_hints("a.[V].txt")["chunk_strategy"] == "semantic"
        assert parse_filename_hints("a.[P].txt")["chunk_strategy"] == "paragraph"


# ── Routing ──────────────────────────────────────────────────────────


class TestRouting:

    def test_pdf_routes_to_native(self):
        parser = get_parser("test.pdf")
        assert isinstance(parser, PDFParser)

    def test_docx_routes_to_native(self):
        parser = get_parser("test.docx")
        assert isinstance(parser, DocxParser)

    def test_pptx_routes_to_native(self):
        parser = get_parser("test.pptx")
        assert isinstance(parser, PptxParser)

    def test_xlsx_routes_to_native(self):
        parser = get_parser("test.xlsx")
        assert isinstance(parser, XlsxParser)

    def test_txt_routes_to_text(self):
        parser = get_parser("test.txt")
        assert isinstance(parser, TextParser)

    def test_md_routes_to_text(self):
        parser = get_parser("readme.md")
        assert isinstance(parser, TextParser)

    def test_native_engine_forced(self):
        parser = get_parser("test.pdf", parser_engine="native")
        assert isinstance(parser, PDFParser)

    def test_unavailable_engine_falls_back(self):
        """Requesting mineru when unavailable should fall back to native PDFParser."""
        parser = get_parser("test.pdf", parser_engine="mineru")
        assert isinstance(parser, PDFParser)

    def test_unknown_extension_raises(self):
        with pytest.raises(ValueError, match="No parser"):
            get_parser("file.xyz")

    def test_env_var_override(self, monkeypatch):
        monkeypatch.setenv("AURORA_PARSER_ENGINE", "pdf:docling")
        # Docling unavailable → falls back to native
        parser = get_parser("test.pdf")
        assert isinstance(parser, PDFParser)

    def test_env_var_multiple_entries(self, monkeypatch):
        monkeypatch.setenv("AURORA_PARSER_ENGINE", "pdf:mineru,docx:docling")
        p1 = get_parser("test.pdf")
        assert isinstance(p1, PDFParser)  # fallback
        p2 = get_parser("test.docx")
        assert isinstance(p2, DocxParser)  # fallback


# ── parse_file integration ───────────────────────────────────────────


class TestParseFile:

    @pytest.mark.asyncio
    async def test_parse_text_file(self, tmp_path):
        p = tmp_path / "hello.txt"
        p.write_text("Hello, world!")
        result = await parse_file(str(p))
        assert result.text == "Hello, world!"
        assert result.file_type == "txt"

    @pytest.mark.asyncio
    async def test_parse_with_engine_kwarg(self, tmp_path):
        p = tmp_path / "data.txt"
        p.write_text("some data")
        result = await parse_file(str(p), parser_engine="native")
        assert result.text == "some data"

    @pytest.mark.asyncio
    async def test_parse_with_hint_filename(self, tmp_path):
        p = tmp_path / "doc.[native].txt"
        p.write_text("hinted content")
        result = await parse_file(str(p))
        assert result.text == "hinted content"


# ── Concurrency control ──────────────────────────────────────────────


class TestConcurrency:

    def test_mineru_default_parallel(self, monkeypatch):
        monkeypatch.delenv("MINERU_MAX_PARALLEL", raising=False)
        parser = MinerUParser()
        assert parser._max_parallel == 1

    def test_mineru_custom_parallel(self, monkeypatch):
        monkeypatch.setenv("MINERU_MAX_PARALLEL", "4")
        parser = MinerUParser()
        assert parser._max_parallel == 4

    def test_docling_default_parallel(self, monkeypatch):
        monkeypatch.delenv("DOCLING_MAX_PARALLEL", raising=False)
        parser = DoclingParser()
        assert parser._max_parallel == 2

    def test_docling_custom_parallel(self, monkeypatch):
        monkeypatch.setenv("DOCLING_MAX_PARALLEL", "8")
        parser = DoclingParser()
        assert parser._max_parallel == 8
