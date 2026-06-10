"""Pipeline status tracking and management.

Migrated from LightRAG pipeline status system.  Manages the global
pipeline state (busy/idle/cancelled) and per-batch progress.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from aurora_ext.rag.storage.base import BaseDocStatusStorage, DocStatus

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PipelineStatus:
    """Global pipeline state."""

    busy: bool = False
    job_name: str = ""
    job_start: str = ""
    total_docs: int = 0
    processed_docs: int = 0
    failed_docs: int = 0
    pending_docs: int = 0
    parsing_count: int = 0
    analyzing_count: int = 0
    processing_count: int = 0
    total_batches: int = 0
    current_batch: int = 0
    request_pending: bool = False
    latest_message: str = ""
    history_messages: list[str] = field(default_factory=list)
    cancelled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "busy": self.busy,
            "job_name": self.job_name,
            "job_start": self.job_start,
            "docs": {
                "total": self.total_docs,
                "processed": self.processed_docs,
                "failed": self.failed_docs,
                "pending": self.pending_docs,
            },
            "stages": {
                "parsing": self.parsing_count,
                "analyzing": self.analyzing_count,
                "processing": self.processing_count,
            },
            "batches": {
                "total": self.total_batches,
                "current": self.current_batch,
            },
            "cur_batch": self.current_batch,
            "request_pending": self.request_pending,
            "latest_message": self.latest_message,
            "history_messages": self.history_messages[-20:],
            "update_status": "processing" if self.busy else "idle",
        }


class PipelineManager:
    """Manages the document ingestion pipeline lifecycle.

    Provides:
    - Busy/idle locking
    - Cancellation
    - Progress tracking
    - Concurrent upload handling via ``request_pending`` flag
    """

    def __init__(self, doc_status_storage: BaseDocStatusStorage) -> None:
        self._status = PipelineStatus()
        self._lock = asyncio.Lock()
        self._doc_status = doc_status_storage

    @property
    def status(self) -> PipelineStatus:
        return self._status

    @property
    def is_busy(self) -> bool:
        return self._status.busy

    @property
    def is_cancelled(self) -> bool:
        return self._status.cancelled

    async def start_job(self, job_name: str, total_docs: int, total_batches: int = 1) -> None:
        """Mark the pipeline as busy with a new job."""
        async with self._lock:
            self._status = PipelineStatus(
                busy=True,
                job_name=job_name,
                job_start=_now_iso(),
                total_docs=total_docs,
                pending_docs=total_docs,
                total_batches=total_batches,
                latest_message=f"Starting: {job_name}",
            )

    async def update_progress(
        self,
        message: str,
        processed: int = 0,
        failed: int = 0,
        current_batch: int = 0,
        parsing_delta: int = 0,
        analyzing_delta: int = 0,
        processing_delta: int = 0,
    ) -> None:
        """Update pipeline progress."""
        self._status.processed_docs += processed
        self._status.failed_docs += failed
        self._status.parsing_count = max(0, self._status.parsing_count + parsing_delta)
        self._status.analyzing_count = max(0, self._status.analyzing_count + analyzing_delta)
        self._status.processing_count = max(0, self._status.processing_count + processing_delta)
        self._status.pending_docs = max(
            0, self._status.total_docs - self._status.processed_docs - self._status.failed_docs
        )
        if current_batch > 0:
            self._status.current_batch = current_batch
        self._status.latest_message = message
        self._status.history_messages.append(f"[{_now_iso()}] {message}")

    async def finish_job(self) -> None:
        """Mark the pipeline as idle."""
        async with self._lock:
            self._status.busy = False
            self._status.cancelled = False
            self._status.latest_message = "Pipeline finished"
            self._status.history_messages.append(f"[{_now_iso()}] Pipeline finished")

    async def cancel(self) -> bool:
        """Request pipeline cancellation.

        Returns ``True`` if the pipeline was running and cancellation
        was requested.
        """
        if not self._status.busy:
            return False
        self._status.cancelled = True
        self._status.latest_message = "Cancellation requested"
        return True

    def check_cancellation(self) -> None:
        """Raise ``PipelineCancelledError`` if cancellation was requested.

        Call this at checkpoints during pipeline processing.
        """
        if self._status.cancelled:
            raise PipelineCancelledError("Pipeline was cancelled by user")

    async def get_status_dict(self) -> dict[str, Any]:
        """Return pipeline status as a dict (for API response)."""
        return self._status.to_dict()

    async def get_doc_status_counts(self, kb_name: str | None = None) -> dict[str, int]:
        """Return document counts grouped by status, optionally scoped to a KB."""
        return await self._doc_status.get_status_counts(kb_name=kb_name)

    async def set_request_pending(self, value: bool) -> None:
        """Flag that new documents are waiting to be picked up."""
        self._status.request_pending = value


class PipelineCancelledError(Exception):
    """Raised when the pipeline is cancelled during processing."""
