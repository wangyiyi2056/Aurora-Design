"""Filename sanitisation and content summary — migrated from LightRAG."""

from __future__ import annotations

import os
import re
import unicodedata


def sanitize_filename(filename: str) -> str:
    """Sanitise *filename* to prevent path-traversal attacks.

    Migrated from LightRAG ``utils.sanitize_filename``.

    - Strips directory components (only the basename is kept).
    - Normalises Unicode to NFC.
    - Removes control characters and path separators.
    - Collapses whitespace / dots at boundaries.
    - Returns ``"unnamed"`` when the result is empty.
    """
    name = os.path.basename(filename)
    name = unicodedata.normalize("NFC", name)
    name = re.sub(r"[\x00-\x1f\x7f]", "", name)
    name = re.sub(r"[\\/]", "", name)
    name = name.strip(". ")
    name = re.sub(r"\s+", "_", name)
    if not name:
        return "unnamed"
    return name


def get_content_summary(text: str, max_length: int = 100) -> str:
    """Return the first *max_length* characters of *text* as a summary.

    Collapses whitespace and strips leading/trailing newlines.
    """
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) <= max_length:
        return cleaned
    return cleaned[:max_length] + "..."
