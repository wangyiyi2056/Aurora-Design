"""Tests for the citation tracking system.

Covers:
  - Citation data structure immutability
  - Chunk ID generation determinism
  - Distance-to-score conversion
  - CitationTracker: from_retrieval_results, sort, deduplicate, filter
  - ChunkManager: chunk_id propagation, page_number tracking
  - PDFParser page boundaries
  - QueryEngine citation building
  - EmbeddingRetriever raw results
  - ChromaVectorStore metadata round-trip
"""

from __future__ import annotations

import math
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aurora_ext.rag.retrieval.citation_tracker import (
    Citation,
    CitationTracker,
    QueryResultWithCitations,
    distance_to_score,
    generate_chunk_id,
)
from aurora_ext.rag.transformer.chunk import ChunkManager, ChunkParameters
from aurora_ext.rag.knowledge.base import Document


# ── Citation data structures ─────────────────────────────────────────


class TestCitation:
    def test_citation_is_frozen(self):
        c = Citation(
            content="hello",
            source_file="doc.pdf",
            page=1,
            chunk_id="chunk_abc",
            score=0.9,
        )
        with pytest.raises(AttributeError):
            c.content = "changed"  # type: ignore[misc]

    def test_citation_optional_fields(self):
        c = Citation(
            content="text",
            source_file="f.md",
            page=None,
            chunk_id="chunk_1",
            score=0.5,
        )
        assert c.page is None
        assert c.start_pos is None
        assert c.end_pos is None

    def test_citation_with_positions(self):
        c = Citation(
            content="text",
            source_file="f.md",
            page=3,
            chunk_id="chunk_2",
            score=0.8,
            start_pos=100,
            end_pos=200,
        )
        assert c.start_pos == 100
        assert c.end_pos == 200


class TestQueryResultWithCitations:
    def test_frozen(self):
        r = QueryResultWithCitations(answer="ans", citations=(), metadata={})
        with pytest.raises(AttributeError):
            r.answer = "new"  # type: ignore[misc]

    def test_defaults(self):
        r = QueryResultWithCitations(answer="hello")
        assert r.citations == ()
        assert r.metadata == {}

    def test_with_citations(self):
        c1 = Citation("a", "f.pdf", 1, "c1", 0.9)
        c2 = Citation("b", "g.md", None, "c2", 0.7)
        r = QueryResultWithCitations(
            answer="result",
            citations=(c1, c2),
            metadata={"mode": "mix"},
        )
        assert len(r.citations) == 2
        assert r.citations[0].score == 0.9
        assert r.metadata["mode"] == "mix"


# ── Utility functions ────────────────────────────────────────────────


class TestGenerateChunkId:
    def test_deterministic(self):
        id1 = generate_chunk_id("/docs/file.pdf", 0)
        id2 = generate_chunk_id("/docs/file.pdf", 0)
        assert id1 == id2

    def test_different_indices(self):
        id1 = generate_chunk_id("/docs/file.pdf", 0)
        id2 = generate_chunk_id("/docs/file.pdf", 1)
        assert id1 != id2

    def test_different_files(self):
        id1 = generate_chunk_id("/docs/a.pdf", 0)
        id2 = generate_chunk_id("/docs/b.pdf", 0)
        assert id1 != id2

    def test_prefix(self):
        cid = generate_chunk_id("test.txt", 5)
        assert cid.startswith("chunk_")


class TestDistanceToScore:
    def test_zero_distance(self):
        assert distance_to_score(0.0) == 1.0

    def test_large_distance(self):
        score = distance_to_score(9.0)
        assert 0.0 < score < 0.2

    def test_none_distance(self):
        assert distance_to_score(None) == 0.0

    def test_negative_distance(self):
        assert distance_to_score(-1.0) == 0.0

    def test_monotonic_decrease(self):
        prev = 1.0
        for d in [0.1, 0.5, 1.0, 2.0, 5.0]:
            s = distance_to_score(d)
            assert s < prev
            prev = s


# ── CitationTracker ──────────────────────────────────────────────────


class TestCitationTracker:
    def _make_results(self, n: int = 3) -> list[dict]:
        return [
            {
                "content": f"Content chunk {i}",
                "chunk_id": f"chunk_{i:03d}",
                "file_path": f"docs/file_{i % 2}.pdf",
                "page_number": i + 1,
                "score": 0.9 - i * 0.1,
            }
            for i in range(n)
        ]

    def test_from_retrieval_results(self):
        results = self._make_results(3)
        citations = CitationTracker.from_retrieval_results(results)
        assert len(citations) == 3
        assert all(isinstance(c, Citation) for c in citations)
        assert citations[0].source_file == "docs/file_0.pdf"
        assert citations[0].page == 1

    def test_from_results_with_distance_fallback(self):
        results = [
            {"content": "text", "distance": 0.5, "chunk_id": "c1"},
        ]
        citations = CitationTracker.from_retrieval_results(results)
        assert len(citations) == 1
        assert citations[0].score == pytest.approx(1.0 / 1.5, rel=1e-3)

    def test_from_results_with_metadata_fallback(self):
        results = [
            {
                "content": "text",
                "metadata": {
                    "source": "meta.pdf",
                    "chunk_id": "meta_c1",
                    "page_number": 7,
                },
            },
        ]
        citations = CitationTracker.from_retrieval_results(results)
        assert len(citations) == 1
        assert citations[0].source_file == "meta.pdf"
        assert citations[0].page == 7
        assert citations[0].chunk_id == "meta_c1"

    def test_skips_empty_content(self):
        results = [
            {"content": "", "chunk_id": "c1", "score": 0.9},
            {"content": "valid", "chunk_id": "c2", "score": 0.8},
        ]
        citations = CitationTracker.from_retrieval_results(results)
        assert len(citations) == 1
        assert citations[0].chunk_id == "c2"

    def test_sort_by_score(self):
        c1 = Citation("a", "f1", None, "c1", 0.3)
        c2 = Citation("b", "f2", None, "c2", 0.9)
        c3 = Citation("c", "f3", None, "c3", 0.6)
        sorted_citations = CitationTracker.sort_by_score([c1, c2, c3])
        assert sorted_citations[0].score == 0.9
        assert sorted_citations[1].score == 0.6
        assert sorted_citations[2].score == 0.3

    def test_deduplicate_by_chunk_id(self):
        c1 = Citation("text A", "f.pdf", 1, "same_id", 0.9)
        c2 = Citation("text B", "f.pdf", 2, "same_id", 0.8)
        c3 = Citation("text C", "f.pdf", 3, "different_id", 0.7)
        result = CitationTracker.deduplicate([c1, c2, c3])
        assert len(result) == 2
        assert result[0].chunk_id == "same_id"
        assert result[1].chunk_id == "different_id"

    def test_deduplicate_by_content_similarity(self):
        text = "This is a long enough text that shingles will overlap significantly."
        c1 = Citation(text, "f.pdf", 1, "id1", 0.9)
        c2 = Citation(text, "f.pdf", 2, "id2", 0.8)  # Same content, different id
        c3 = Citation("Completely different content here.", "f.pdf", 3, "id3", 0.7)
        result = CitationTracker.deduplicate([c1, c2, c3])
        assert len(result) == 2

    def test_filter_by_source(self):
        c1 = Citation("a", "file_a.pdf", 1, "c1", 0.9)
        c2 = Citation("b", "file_b.pdf", 1, "c2", 0.8)
        c3 = Citation("c", "file_a.pdf", 2, "c3", 0.7)
        result = CitationTracker.filter_by_source([c1, c2, c3], "file_a.pdf")
        assert len(result) == 2
        assert all(c.source_file == "file_a.pdf" for c in result)

    def test_filter_by_min_score(self):
        c1 = Citation("a", "f", None, "c1", 0.9)
        c2 = Citation("b", "f", None, "c2", 0.4)
        c3 = Citation("c", "f", None, "c3", 0.6)
        result = CitationTracker.filter_by_min_score([c1, c2, c3], 0.5)
        assert len(result) == 2

    def test_build_full_pipeline(self):
        results = self._make_results(5)
        # Add a duplicate
        results.append({**results[0]})
        citations = CitationTracker.build(results, min_score=0.5)
        # Should be deduplicated, filtered, and sorted
        assert all(c.score >= 0.5 for c in citations)
        scores = [c.score for c in citations]
        assert scores == sorted(scores, reverse=True)

    def test_build_with_source_filter(self):
        results = self._make_results(4)
        citations = CitationTracker.build(
            results, source_filter="docs/file_0.pdf"
        )
        assert all(c.source_file == "docs/file_0.pdf" for c in citations)


# ── ChunkManager with citation metadata ──────────────────────────────


class TestChunkManagerCitations:
    def test_chunks_include_chunk_id(self):
        doc = Document(content="Hello world " * 100, metadata={"source": "test.txt"})
        mgr = ChunkManager(ChunkParameters(chunk_size=50, chunk_overlap=10))
        chunks = mgr.split([doc])
        assert len(chunks) > 1
        for chunk in chunks:
            assert "chunk_id" in chunk.metadata
            assert chunk.metadata["chunk_id"].startswith("chunk_")

    def test_chunks_include_file_path(self):
        doc = Document(content="Hello world " * 100, metadata={"source": "docs/readme.md"})
        mgr = ChunkManager(ChunkParameters(chunk_size=50, chunk_overlap=10))
        chunks = mgr.split([doc])
        for chunk in chunks:
            assert chunk.metadata.get("file_path") == "docs/readme.md"

    def test_chunks_include_positions(self):
        doc = Document(content="ABCDEFGHIJ" * 10, metadata={"source": "test.txt"})
        mgr = ChunkManager(ChunkParameters(chunk_size=20, chunk_overlap=5))
        chunks = mgr.split([doc])
        for chunk in chunks:
            assert "start_pos" in chunk.metadata
            assert "end_pos" in chunk.metadata
            assert chunk.metadata["start_pos"] >= 0
            assert chunk.metadata["end_pos"] > chunk.metadata["start_pos"]

    def test_chunk_ids_are_unique(self):
        doc = Document(content="A" * 500, metadata={"source": "test.txt"})
        mgr = ChunkManager(ChunkParameters(chunk_size=50, chunk_overlap=10))
        chunks = mgr.split([doc])
        ids = [c.metadata["chunk_id"] for c in chunks]
        assert len(ids) == len(set(ids))

    def test_chunk_ids_deterministic(self):
        doc1 = Document(content="Hello world " * 50, metadata={"source": "test.txt"})
        doc2 = Document(content="Hello world " * 50, metadata={"source": "test.txt"})
        mgr = ChunkManager(ChunkParameters(chunk_size=50, chunk_overlap=10))
        chunks1 = mgr.split([doc1])
        chunks2 = mgr.split([doc2])
        assert [c.metadata["chunk_id"] for c in chunks1] == [
            c.metadata["chunk_id"] for c in chunks2
        ]

    def test_page_number_from_boundaries(self):
        # Simulate a 3-page document with known boundaries
        page_texts = ["Page one content.", "Page two content.", "Page three content."]
        full_text = "\n\n".join(page_texts)
        boundaries = []
        offset = 0
        for t in page_texts:
            boundaries.append(offset)
            offset += len(t) + 2

        doc = Document(
            content=full_text,
            metadata={
                "source": "test.pdf",
                "page_boundaries": boundaries,
            },
        )
        mgr = ChunkManager(ChunkParameters(chunk_size=30, chunk_overlap=5))
        chunks = mgr.split([doc])

        # First chunk should be page 1
        assert chunks[0].metadata.get("page_number") == 1
        # Check that later chunks might have higher page numbers
        pages_seen = {c.metadata.get("page_number") for c in chunks}
        assert 1 in pages_seen

    def test_no_page_number_without_boundaries(self):
        doc = Document(content="Just text " * 20, metadata={"source": "readme.md"})
        mgr = ChunkManager(ChunkParameters(chunk_size=30, chunk_overlap=5))
        chunks = mgr.split([doc])
        for chunk in chunks:
            assert "page_number" not in chunk.metadata


# ── Multi-document citation scenario ─────────────────────────────────


class TestMultiDocumentCitations:
    def test_multiple_documents_unique_ids(self):
        doc1 = Document(content="Document one " * 50, metadata={"source": "file_a.pdf"})
        doc2 = Document(content="Document two " * 50, metadata={"source": "file_b.pdf"})
        mgr = ChunkManager(ChunkParameters(chunk_size=50, chunk_overlap=10))
        chunks = mgr.split([doc1, doc2])

        ids = [c.metadata["chunk_id"] for c in chunks]
        assert len(ids) == len(set(ids)), "Chunk IDs must be globally unique"

    def test_multi_doc_citation_building(self):
        results = [
            {"content": "From doc A", "chunk_id": "a1", "file_path": "A.pdf", "score": 0.95},
            {"content": "From doc B", "chunk_id": "b1", "file_path": "B.pdf", "score": 0.88},
            {"content": "From doc A again", "chunk_id": "a2", "file_path": "A.pdf", "score": 0.75},
        ]
        citations = CitationTracker.build(results)
        assert len(citations) == 3
        assert citations[0].source_file == "A.pdf"  # Highest score
        assert citations[0].score == 0.95


# ── PDF page tracking ────────────────────────────────────────────────


class TestPDFPageTracking:
    def test_page_boundaries_are_generated(self):
        """Verify the PDFParser produces page_boundaries metadata."""
        try:
            from pypdf import PdfWriter
        except ImportError:
            pytest.skip("pypdf not installed")

        import tempfile
        from pathlib import Path

        # Create a minimal 3-page PDF
        writer = PdfWriter()
        for _ in range(3):
            writer.add_blank_page(width=200, height=200)

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            writer.write(tmp.name)
            tmp_path = tmp.name

        from aurora_ext.rag.parser.pdf_parser import PDFParser
        import asyncio

        parser = PDFParser()
        result = asyncio.run(parser.parse(tmp_path))

        assert "page_boundaries" in result.metadata
        boundaries = result.metadata["page_boundaries"]
        assert len(boundaries) == 3
        assert result.metadata["file_path"] == tmp_path

        Path(tmp_path).unlink(missing_ok=True)


# ── EmbeddingRetriever raw results ───────────────────────────────────


class TestEmbeddingRetrieverRaw:
    @pytest.mark.asyncio
    async def test_retrieve_raw_returns_dicts(self):
        mock_vs = MagicMock()
        mock_vs.search.return_value = [
            {
                "content": "chunk text",
                "metadata": {"source": "f.pdf", "chunk_id": "c1"},
                "id": "c1",
                "chunk_id": "c1",
                "file_path": "f.pdf",
                "page_number": 3,
                "distance": 0.2,
                "start_pos": 0,
                "end_pos": 100,
            },
        ]
        mock_emb = MagicMock()
        mock_emb.aembed = AsyncMock(return_value=[[0.1] * 128])

        from aurora_ext.rag.retriever.embedding_retriever import EmbeddingRetriever

        retriever = EmbeddingRetriever(mock_vs, mock_emb, top_k=5)
        raw = await retriever.retrieve_raw("test query")

        assert len(raw) == 1
        assert raw[0]["content"] == "chunk text"
        assert raw[0]["chunk_id"] == "c1"
        assert raw[0]["score"] == pytest.approx(1.0 / 1.2, rel=1e-3)
        assert raw[0]["page_number"] == 3


# ── ChromaVectorStore metadata round-trip ────────────────────────────


class TestChromaMetadataRoundTrip:
    def test_sanitize_metadata_complex_values(self):
        from aurora_ext.storage.chroma_store import ChromaVectorStore

        meta = {
            "str_val": "hello",
            "int_val": 42,
            "float_val": 3.14,
            "bool_val": True,
            "list_val": [1, 2, 3],
            "none_val": None,
        }
        safe = ChromaVectorStore._sanitize_metadata(meta)
        assert safe["str_val"] == "hello"
        assert safe["int_val"] == 42
        assert safe["float_val"] == 3.14
        assert safe["bool_val"] is True
        assert isinstance(safe["list_val"], str)  # JSON-encoded
        assert "none_val" not in safe  # None values are excluded

    def test_build_ids_from_metadata(self):
        from aurora_ext.storage.chroma_store import ChromaVectorStore

        metas = [
            {"chunk_id": "custom_1"},
            {"chunk_id": "custom_2"},
            {"other": "no_chunk_id"},
        ]
        ids = ChromaVectorStore._build_ids(metas, "doc", 3)
        assert ids == ["custom_1", "custom_2", "doc-2"]


# ── QueryEngine citation building ────────────────────────────────────


class TestQueryEngineCitations:
    def test_build_citations_from_result(self):
        from aurora_ext.rag.retrieval.query_engine import QueryEngine, QueryResult

        result = QueryResult(
            response="test answer",
            chunks=[
                {
                    "content": "chunk text A",
                    "file_path": "docs/manual.pdf",
                    "chunk_id": "c_a",
                    "page_number": 15,
                    "rerank_score": 0.95,
                },
                {
                    "content": "chunk text B",
                    "file_path": "docs/guide.md",
                    "chunk_id": "c_b",
                    "score": 0.88,
                },
            ],
        )
        citations = QueryEngine._build_citations(result)
        assert len(citations) == 2
        assert citations[0].score >= citations[1].score  # Sorted
        assert citations[0].source_file == "docs/manual.pdf"
        assert citations[0].page == 15

    def test_build_citations_empty_chunks(self):
        from aurora_ext.rag.retrieval.query_engine import QueryEngine, QueryResult

        result = QueryResult(response="test", chunks=[])
        citations = QueryEngine._build_citations(result)
        assert citations == []
