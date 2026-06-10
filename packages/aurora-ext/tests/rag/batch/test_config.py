"""Tests for batch configuration and result types."""

from __future__ import annotations

import pytest

from aurora_ext.rag.batch.config import (
    BatchConfig,
    BatchItemResult,
    BatchResult,
    ProgressSnapshot,
)


# ── BatchConfig ──────────────────────────────────────────────────


class TestBatchConfig:
    """Test BatchConfig immutable dataclass."""

    def test_defaults(self):
        """Default values are sensible."""
        cfg = BatchConfig()

        assert cfg.max_parallel_insert == 10
        assert cfg.batch_size == 100
        assert cfg.enable_async is True
        assert cfg.max_memory_mb == 2048
        assert cfg.progress_callback_interval == 5.0
        assert cfg.progress_callback is None
        assert cfg.retry_attempts == 3
        assert cfg.retry_backoff == 1.0

    def test_custom_values(self):
        """Custom values are stored correctly."""
        cfg = BatchConfig(
            max_parallel_insert=20,
            batch_size=50,
            enable_async=False,
            max_memory_mb=512,
            retry_attempts=1,
            retry_backoff=0.5,
        )

        assert cfg.max_parallel_insert == 20
        assert cfg.batch_size == 50
        assert cfg.enable_async is False
        assert cfg.max_memory_mb == 512
        assert cfg.retry_attempts == 1
        assert cfg.retry_backoff == 0.5

    def test_frozen(self):
        """BatchConfig is immutable."""
        cfg = BatchConfig()

        with pytest.raises(Exception):
            cfg.max_parallel_insert = 99  # type: ignore[misc]

    def test_invalid_parallel_insert(self):
        """Reject non-positive max_parallel_insert."""
        with pytest.raises(ValueError, match="max_parallel_insert"):
            BatchConfig(max_parallel_insert=0)

    def test_invalid_batch_size(self):
        """Reject non-positive batch_size."""
        with pytest.raises(ValueError, match="batch_size"):
            BatchConfig(batch_size=0)

    def test_invalid_memory(self):
        """Reject memory below 64 MB."""
        with pytest.raises(ValueError, match="max_memory_mb"):
            BatchConfig(max_memory_mb=10)

    def test_invalid_retry(self):
        """Reject negative retry_attempts."""
        with pytest.raises(ValueError, match="retry_attempts"):
            BatchConfig(retry_attempts=-1)

    def test_from_toml_full(self):
        """Build config from a full TOML dict."""
        data = {
            "batch": {
                "max_parallel_insert": 15,
                "batch_size": 200,
                "enable_async": False,
                "max_memory_mb": 1024,
                "progress_callback_interval": 10,
                "retry_attempts": 2,
                "retry_backoff": 0.5,
            }
        }

        cfg = BatchConfig.from_toml(data)

        assert cfg.max_parallel_insert == 15
        assert cfg.batch_size == 200
        assert cfg.enable_async is False
        assert cfg.max_memory_mb == 1024
        assert cfg.retry_attempts == 2

    def test_from_toml_flat(self):
        """Build config from a flat dict (no nested [batch] key)."""
        data = {"max_parallel_insert": 5, "batch_size": 25}

        cfg = BatchConfig.from_toml(data)

        assert cfg.max_parallel_insert == 5
        assert cfg.batch_size == 25

    def test_from_toml_ignores_unknown_keys(self):
        """Unknown keys in TOML are silently ignored."""
        data = {"batch": {"max_parallel_insert": 5, "unknown_key": "x"}}

        cfg = BatchConfig.from_toml(data)
        assert cfg.max_parallel_insert == 5

    def test_from_toml_ignores_progress_callback(self):
        """progress_callback is not settable from TOML."""
        data = {"batch": {"progress_callback": "not_a_callable"}}

        cfg = BatchConfig.from_toml(data)
        assert cfg.progress_callback is None


# ── BatchItemResult ──────────────────────────────────────────────


class TestBatchItemResult:
    """Test BatchItemResult immutable dataclass."""

    def test_success(self):
        r = BatchItemResult(item_id="abc", success=True, duration_seconds=0.5)

        assert r.item_id == "abc"
        assert r.success is True
        assert r.error == ""
        assert r.duration_seconds == 0.5

    def test_failure(self):
        r = BatchItemResult(item_id="xyz", success=False, error="timeout")

        assert r.success is False
        assert r.error == "timeout"

    def test_frozen(self):
        r = BatchItemResult(item_id="a", success=True)

        with pytest.raises(Exception):
            r.success = False  # type: ignore[misc]


# ── BatchResult ──────────────────────────────────────────────────


class TestBatchResult:
    """Test BatchResult aggregated result."""

    def test_throughput(self):
        r = BatchResult(total=100, succeeded=90, failed=10, duration_seconds=10.0)

        assert r.throughput == pytest.approx(10.0)

    def test_throughput_zero_duration(self):
        r = BatchResult(total=100, succeeded=100, failed=0, duration_seconds=0.0)

        assert r.throughput == 0.0

    def test_success_rate(self):
        r = BatchResult(total=100, succeeded=75, failed=25, duration_seconds=5.0)

        assert r.success_rate == pytest.approx(0.75)

    def test_success_rate_empty(self):
        r = BatchResult(total=0, succeeded=0, failed=0)

        assert r.success_rate == 0.0

    def test_to_dict(self):
        errors = [BatchItemResult(item_id="e1", success=False, error="boom")]
        r = BatchResult(
            total=10,
            succeeded=9,
            failed=1,
            duration_seconds=2.5,
            errors=errors,
        )

        d = r.to_dict()

        assert d["total"] == 10
        assert d["succeeded"] == 9
        assert d["failed"] == 1
        assert d["throughput"] == 4.0
        assert len(d["errors"]) == 1
        assert d["errors"][0]["item_id"] == "e1"
        assert d["errors"][0]["error"] == "boom"

    def test_frozen(self):
        r = BatchResult(total=1, succeeded=1, failed=0)

        with pytest.raises(Exception):
            r.total = 2  # type: ignore[misc]


# ── ProgressSnapshot ─────────────────────────────────────────────


class TestProgressSnapshot:
    """Test ProgressSnapshot immutable dataclass."""

    def test_creation(self):
        s = ProgressSnapshot(
            total=100,
            completed=50,
            failed=5,
            progress_pct=55.0,
            elapsed_seconds=10.0,
            estimated_remaining_seconds=8.18,
            throughput=5.5,
        )

        assert s.total == 100
        assert s.completed == 50
        assert s.failed == 5
        assert s.progress_pct == 55.0

    def test_to_dict(self):
        s = ProgressSnapshot(
            total=100,
            completed=80,
            failed=20,
            progress_pct=100.0,
            elapsed_seconds=20.0,
            estimated_remaining_seconds=0.0,
            throughput=5.0,
        )

        d = s.to_dict()

        assert d["total"] == 100
        assert d["progress_pct"] == 100.0
        assert d["throughput"] == 5.0

    def test_frozen(self):
        s = ProgressSnapshot(
            total=1, completed=0, failed=0,
            progress_pct=0.0, elapsed_seconds=0.0,
            estimated_remaining_seconds=-1.0, throughput=0.0,
        )

        with pytest.raises(Exception):
            s.completed = 1  # type: ignore[misc]
