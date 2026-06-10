"""Tests for cancellation support."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from aurora_ext.rag.batch.cancellable import BatchCancelledError, CancellableBatch


class TestBatchCancelledError:
    """Test the cancellation exception."""

    def test_is_exception(self):
        err = BatchCancelledError("cancelled")
        assert isinstance(err, Exception)

    def test_message(self):
        err = BatchCancelledError("custom message")
        assert str(err) == "custom message"


class TestCancellableBatch:
    """Test cooperative cancellation."""

    def test_initial_state(self):
        batch = CancellableBatch()
        assert batch.is_cancelled is False

    def test_cancel(self):
        batch = CancellableBatch()
        batch.cancel()
        assert batch.is_cancelled is True

    def test_cancel_idempotent(self):
        batch = CancellableBatch()
        batch.cancel()
        batch.cancel()
        assert batch.is_cancelled is True

    def test_reset(self):
        batch = CancellableBatch()
        batch.cancel()
        batch.reset()
        assert batch.is_cancelled is False

    def test_check_not_cancelled(self):
        batch = CancellableBatch()
        batch.check()  # Should not raise

    def test_check_cancelled_raises(self):
        batch = CancellableBatch()
        batch.cancel()

        with pytest.raises(BatchCancelledError):
            batch.check()

    def test_on_cancel_callback(self):
        callback = MagicMock()
        batch = CancellableBatch(on_cancel=callback)

        batch.cancel()

        callback.assert_called_once()

    def test_on_cancel_callback_error_swallowed(self):
        def bad_callback():
            raise RuntimeError("boom")

        batch = CancellableBatch(on_cancel=bad_callback)
        batch.cancel()  # Should not raise
        assert batch.is_cancelled is True

    def test_on_cancel_only_called_once(self):
        callback = MagicMock()
        batch = CancellableBatch(on_cancel=callback)

        batch.cancel()
        batch.cancel()

        callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_all_items(self):
        batch = CancellableBatch()
        results_collector = []

        async def process(item):
            results_collector.append(item)
            return item * 2

        items = [1, 2, 3, 4, 5]
        results, errors = await batch.execute(items, process)

        assert results == [2, 4, 6, 8, 10]
        assert errors == []
        assert results_collector == [1, 2, 3, 4, 5]

    @pytest.mark.asyncio
    async def test_execute_with_failures(self):
        batch = CancellableBatch()

        async def process(item):
            if item == 3:
                raise ValueError("bad item")
            return item

        items = [1, 2, 3, 4, 5]
        results, errors = await batch.execute(items, process)

        assert len(results) == 4
        assert len(errors) == 1
        assert isinstance(errors[0], ValueError)

    @pytest.mark.asyncio
    async def test_execute_cancelled_midway(self):
        batch = CancellableBatch()
        processed = []

        async def process(item):
            processed.append(item)
            if item == 3:
                batch.cancel()
            return item

        items = [1, 2, 3, 4, 5]

        with pytest.raises(BatchCancelledError):
            await batch.execute(items, process)

        # Items 1, 2, 3 were processed; 4 and 5 were not
        assert processed == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_execute_empty_items(self):
        batch = CancellableBatch()

        async def process(item):
            return item

        results, errors = await batch.execute([], process)

        assert results == []
        assert errors == []

    @pytest.mark.asyncio
    async def test_execute_pre_cancelled(self):
        batch = CancellableBatch()
        batch.cancel()

        async def process(item):
            return item

        with pytest.raises(BatchCancelledError):
            await batch.execute([1, 2, 3], process)
