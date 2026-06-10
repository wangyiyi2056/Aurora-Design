"""High-performance batch processing for RAG operations.

Provides concurrent, cancellable batch insert, extract, and query
operations with progress tracking and memory-aware backpressure.

Quick start::

    from aurora_ext.rag.batch import BatchConfig, BatchProcessor

    config = BatchConfig(max_parallel_insert=20, batch_size=50)
    processor = BatchProcessor(config)
    result = await processor.process(items, my_async_fn)
"""

from aurora_ext.rag.batch.api import AsyncBatchAPI
from aurora_ext.rag.batch.cancellable import BatchCancelledError, CancellableBatch
from aurora_ext.rag.batch.config import (
    BatchConfig,
    BatchItemResult,
    BatchResult,
    ProgressSnapshot,
)
from aurora_ext.rag.batch.processor import (
    BatchProcessor,
    batch_insert,
    batch_transform,
)
from aurora_ext.rag.batch.progress import ProgressTracker

__all__ = [
    "AsyncBatchAPI",
    "BatchCancelledError",
    "BatchConfig",
    "BatchItemResult",
    "BatchProcessor",
    "BatchResult",
    "CancellableBatch",
    "ProgressSnapshot",
    "ProgressTracker",
    "batch_insert",
    "batch_transform",
]
