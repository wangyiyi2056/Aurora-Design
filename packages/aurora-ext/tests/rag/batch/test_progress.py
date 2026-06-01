"""Tests for progress tracking."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from aurora_ext.rag.batch.config import ProgressSnapshot
from aurora_ext.rag.batch.progress import ProgressTracker


class TestProgressTracker:
    """Test thread-safe progress tracker."""

    def test_initial_state(self):
        tracker = ProgressTracker(total=100)

        assert tracker.total == 100
        assert tracker.completed == 0
        assert tracker.failed == 0

    def test_invalid_total(self):
        with pytest.raises(ValueError, match="total"):
            ProgressTracker(total=-1)

    def test_update_success(self):
        tracker = ProgressTracker(total=10)

        snapshot = tracker.update(success=True)

        assert tracker.completed == 1
        assert tracker.failed == 0
        assert snapshot.completed == 1
        assert snapshot.total == 10

    def test_update_failure(self):
        tracker = ProgressTracker(total=10)

        snapshot = tracker.update(success=False)

        assert tracker.completed == 0
        assert tracker.failed == 1
        assert snapshot.failed == 1

    def test_update_multiple(self):
        tracker = ProgressTracker(total=10)

        tracker.update(success=True, count=5)
        tracker.update(success=False, count=2)

        assert tracker.completed == 5
        assert tracker.failed == 2

    def test_get_progress(self):
        tracker = ProgressTracker(total=100)

        tracker.update(success=True, count=30)
        tracker.update(success=False, count=10)

        progress = tracker.get_progress()

        assert isinstance(progress, ProgressSnapshot)
        assert progress.total == 100
        assert progress.completed == 30
        assert progress.failed == 10
        assert progress.progress_pct == pytest.approx(40.0)

    def test_progress_pct_full(self):
        tracker = ProgressTracker(total=10)

        for _ in range(10):
            tracker.update(success=True)

        progress = tracker.get_progress()
        assert progress.progress_pct == pytest.approx(100.0)

    def test_progress_pct_zero_total(self):
        tracker = ProgressTracker(total=0)

        progress = tracker.get_progress()
        assert progress.progress_pct == 100.0

    def test_elapsed_time(self):
        tracker = ProgressTracker(total=10)
        time.sleep(0.05)
        tracker.update(success=True)

        progress = tracker.get_progress()
        assert progress.elapsed_seconds >= 0.04

    def test_throughput(self):
        tracker = ProgressTracker(total=100)

        # Simulate processing 50 items
        for _ in range(50):
            tracker.update(success=True)

        progress = tracker.get_progress()
        assert progress.throughput > 0

    def test_estimated_remaining(self):
        tracker = ProgressTracker(total=100)

        for _ in range(50):
            tracker.update(success=True)

        progress = tracker.get_progress()
        # Should have a positive estimate since items remain
        if progress.throughput > 0:
            assert progress.estimated_remaining_seconds > 0

    def test_estimated_remaining_complete(self):
        tracker = ProgressTracker(total=5)

        for _ in range(5):
            tracker.update(success=True)

        progress = tracker.get_progress()
        assert progress.estimated_remaining_seconds == 0.0

    def test_reset(self):
        tracker = ProgressTracker(total=10)
        tracker.update(success=True, count=5)

        tracker.reset(total=20)

        assert tracker.total == 20
        assert tracker.completed == 0
        assert tracker.failed == 0

    def test_callback_invoked(self):
        callback = MagicMock()
        tracker = ProgressTracker(total=10, callback=callback, callback_interval=0.0)

        tracker.update(success=True)

        callback.assert_called_once()
        arg = callback.call_args[0][0]
        assert isinstance(arg, ProgressSnapshot)

    def test_callback_rate_limited(self):
        callback = MagicMock()
        tracker = ProgressTracker(total=100, callback=callback, callback_interval=10.0)

        # Multiple rapid updates
        for _ in range(10):
            tracker.update(success=True)

        # Callback should only fire once (first call always fires)
        assert callback.call_count == 1

    def test_callback_error_swallowed(self):
        """Callback errors must not break the tracker."""
        def bad_callback(snapshot: ProgressSnapshot) -> None:
            raise RuntimeError("callback boom")

        tracker = ProgressTracker(total=10, callback=bad_callback, callback_interval=0.0)

        # Should not raise
        tracker.update(success=True)
        assert tracker.completed == 1

    def test_concurrent_updates(self):
        """Multiple threads updating simultaneously stay consistent."""
        import threading

        tracker = ProgressTracker(total=1000)

        def worker(count: int, success: bool) -> None:
            for _ in range(count):
                tracker.update(success=success)

        threads = [
            threading.Thread(target=worker, args=(500, True)),
            threading.Thread(target=worker, args=(200, True)),
            threading.Thread(target=worker, args=(300, False)),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert tracker.completed == 700
        assert tracker.failed == 300
