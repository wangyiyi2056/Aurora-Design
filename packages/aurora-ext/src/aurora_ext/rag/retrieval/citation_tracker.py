"""Citation tracking — trace query results back to source documents.

Provides immutable data structures for associating retrieved chunks with
their originating files, page numbers, and relevance scores.  The
``CitationTracker`` utility builds, filters, sorts, and deduplicates
citation lists.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence


@dataclass(frozen=True)
class Citation:
    """A single source reference pointing back to an original document chunk.

    Attributes
    ----------
    content:
        The verbatim text of the retrieved chunk.
    source_file:
        Path (or name) of the file the chunk was extracted from.
    page:
        Page number inside the source file (``None`` for non-paginated
        formats such as Markdown or plain text).
    chunk_id:
        Unique identifier for the chunk inside the vector store.
    score:
        Relevance score — higher is better.  Typically the similarity
        score returned by the vector store, optionally overwritten by a
        reranker score.
    start_pos:
        Character offset where the chunk begins inside the source
        document text (when available).
    end_pos:
        Character offset where the chunk ends inside the source
        document text (when available).
    """

    content: str
    source_file: str
    page: Optional[int]
    chunk_id: str
    score: float
    start_pos: Optional[int] = None
    end_pos: Optional[int] = None


@dataclass(frozen=True)
class QueryResultWithCitations:
    """Complete query response with answer text and source citations.

    Attributes
    ----------
    answer:
        The generated answer text.
    citations:
        Ordered list of source citations (highest score first).
    metadata:
        Arbitrary extra data (query mode, timing, token counts …).
    """

    answer: str
    citations: tuple[Citation, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


# ── Helpers ──────────────────────────────────────────────────────────


def generate_chunk_id(file_path: str, chunk_index: int) -> str:
    """Produce a deterministic, unique chunk identifier.

    Combines the source file path with the positional index so that
    re-indexing the same file yields the same IDs (idempotent), while
    different files never collide.
    """

    raw = f"{file_path}::{chunk_index}"
    short_hash = hashlib.sha256(raw.encode()).hexdigest()[:12]
    return f"chunk_{short_hash}"


def distance_to_score(distance: float | None) -> float:
    """Convert a vector-store distance into a 0-1 similarity score.

    ChromaDB returns L2 distances (lower = more similar).  We invert
    into a 0-1 range where 1.0 means a perfect match.  ``None`` or
    negative values map to ``0.0``.
    """

    if distance is None or distance < 0:
        return 0.0
    return 1.0 / (1.0 + distance)


# ── Tracker ──────────────────────────────────────────────────────────


class CitationTracker:
    """Build, sort, deduplicate, and filter a list of citations."""

    @staticmethod
    def from_retrieval_results(
        results: Sequence[dict[str, Any]],
    ) -> list[Citation]:
        """Convert raw retrieval result dicts into ``Citation`` objects.

        Each dict is expected to carry at minimum ``content`` and may
        include ``chunk_id``, ``file_path`` / ``source``, ``page`` /
        ``page_number``, ``score`` / ``distance``, ``start_pos``, and
        ``end_pos``.
        """

        citations: list[Citation] = []
        for r in results:
            content = r.get("content", "")
            if not content:
                continue

            score = r.get("score")
            if score is None:
                score = distance_to_score(r.get("distance"))

            source = (
                r.get("file_path")
                or r.get("source")
                or r.get("metadata", {}).get("source", "")
            )

            page = r.get("page") or r.get("page_number")
            if page is None:
                page = r.get("metadata", {}).get("page_number")

            chunk_id = (
                r.get("chunk_id")
                or r.get("id")
                or r.get("metadata", {}).get("chunk_id", "")
            )

            citations.append(
                Citation(
                    content=content,
                    source_file=str(source) if source else "",
                    page=int(page) if page is not None else None,
                    chunk_id=str(chunk_id),
                    score=float(score),
                    start_pos=r.get("start_pos"),
                    end_pos=r.get("end_pos"),
                )
            )
        return citations

    @staticmethod
    def sort_by_score(citations: Sequence[Citation]) -> list[Citation]:
        """Return citations ordered by descending score."""
        return sorted(citations, key=lambda c: c.score, reverse=True)

    @staticmethod
    def deduplicate(
        citations: Sequence[Citation],
        similarity_threshold: float = 0.95,
    ) -> list[Citation]:
        """Remove near-duplicate citations.

        Two citations are considered duplicates when they share the same
        ``chunk_id`` **or** their content overlap exceeds the
        *similarity_threshold* (simple Jaccard on character-level
        shingles).
        """

        seen_ids: set[str] = set()
        seen_shingles: list[set[str]] = []
        unique: list[Citation] = []

        for c in citations:
            if c.chunk_id and c.chunk_id in seen_ids:
                continue

            shingles = _shingle(c.content)
            is_dup = False
            for prev_shingles in seen_shingles:
                if _jaccard(shingles, prev_shingles) >= similarity_threshold:
                    is_dup = True
                    break
            if is_dup:
                continue

            seen_ids.add(c.chunk_id)
            seen_shingles.append(shingles)
            unique.append(c)

        return unique

    @staticmethod
    def filter_by_source(
        citations: Sequence[Citation],
        source_file: str,
    ) -> list[Citation]:
        """Keep only citations originating from *source_file*."""
        return [c for c in citations if c.source_file == source_file]

    @staticmethod
    def filter_by_min_score(
        citations: Sequence[Citation],
        min_score: float,
    ) -> list[Citation]:
        """Keep only citations whose score is >= *min_score*."""
        return [c for c in citations if c.score >= min_score]

    @classmethod
    def build(
        cls,
        results: Sequence[dict[str, Any]],
        min_score: float = 0.0,
        source_filter: str | None = None,
        deduplicate: bool = True,
    ) -> list[Citation]:
        """One-shot convenience: parse → deduplicate → filter → sort."""

        citations = cls.from_retrieval_results(results)

        if deduplicate:
            citations = cls.deduplicate(citations)

        if min_score > 0.0:
            citations = cls.filter_by_min_score(citations, min_score)

        if source_filter:
            citations = cls.filter_by_source(citations, source_filter)

        return cls.sort_by_score(citations)


# ── Internal utilities ───────────────────────────────────────────────


def _shingle(text: str, width: int = 5) -> set[str]:
    """Return a set of character-level shingles for near-dup detection."""
    cleaned = text.strip().lower()
    if len(cleaned) < width:
        return {cleaned}
    return {cleaned[i : i + width] for i in range(len(cleaned) - width + 1)}


def _jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity between two shingle sets."""
    if not a and not b:
        return 1.0
    intersection = len(a & b)
    union = len(a | b)
    if union == 0:
        return 1.0
    return intersection / union
