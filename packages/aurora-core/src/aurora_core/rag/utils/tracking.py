"""Track-ID generation for pipeline operations — migrated from LightRAG."""

from __future__ import annotations

import uuid


def generate_track_id() -> str:
    """Generate a unique tracking ID for a pipeline operation.

    Every upload, scan, text-insert, or reprocess call receives a
    ``track_id`` so callers can poll the processing status of their
    specific batch.

    Returns
    -------
    str
        A UUID-4 hex string (32 characters, no dashes).
    """
    return uuid.uuid4().hex
