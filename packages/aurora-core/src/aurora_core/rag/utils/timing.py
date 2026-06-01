"""Performance timing helper — migrated from LightRAG ``utils.py``."""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Generator

logger = logging.getLogger(__name__)


@contextmanager
def performance_timing_log(label: str) -> Generator[None, None, None]:
    """Context manager that logs wall-clock elapsed time.

    Usage::

        with performance_timing_log("entity extraction"):
            await extract_entities(chunks)

    Produces a log line: ``[PERF] entity extraction: 1234.5ms``
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info("[PERF] %s: %.1fms", label, elapsed_ms)
