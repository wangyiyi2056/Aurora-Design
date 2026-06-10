"""In-memory metrics collection for the RAG pipeline.

Thread-safe counters and histograms for pipeline performance, LLM calls,
and cache efficiency.  Supports Prometheus text-format export without
requiring the ``prometheus_client`` library.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Any


@dataclass(frozen=True)
class _Counter:
    """Monotonically increasing counter."""

    name: str
    help_text: str
    labels: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class _Gauge:
    """Point-in-time value that can go up and down."""

    name: str
    help_text: str
    labels: tuple[tuple[str, str], ...] = ()


@dataclass
class _HistogramBucket:
    """Single histogram bucket."""

    le: float
    count: int = 0


@dataclass
class _Histogram:
    """Histogram with predefined buckets."""

    name: str
    help_text: str
    buckets: list[float]
    labels: tuple[tuple[str, str], ...] = ()


class MetricsCollector:
    """Centralised in-memory metrics store.

    All public methods are thread-safe.  The collector is designed to be
    used as a process-wide singleton via :func:`get_metrics`.

    Usage::

        m = get_metrics()
        m.inc("pipeline_docs_processed_total", labels={"kb": "default"})
        m.observe("pipeline_stage_duration_seconds", 1.23, labels={"stage": "parse"})
        text = m.export_prometheus()
    """

    def __init__(self) -> None:
        self._lock = Lock()

        # Counter storage: key → value
        self._counters: dict[str, float] = {}
        self._counter_meta: dict[str, _Counter] = {}

        # Gauge storage: key → value
        self._gauges: dict[str, float] = {}
        self._gauge_meta: dict[str, _Gauge] = {}

        # Histogram storage: key → list of buckets + sum + count
        self._histograms: dict[str, list[_HistogramBucket]] = {}
        self._histogram_sums: dict[str, float] = {}
        self._histogram_counts: dict[str, int] = {}
        self._histogram_meta: dict[str, _Histogram] = {}

        # Boot time for uptime calculation
        self._boot_time: float = time.time()

        # Register well-known metrics metadata
        self._register_defaults()

    # ── Registration ────────────────────────────────────────────────

    def _register_defaults(self) -> None:
        """Pre-register known metric families for metadata."""
        counter_defs = [
            ("pipeline_docs_processed_total", "Total documents successfully processed"),
            ("pipeline_docs_failed_total", "Total documents that failed processing"),
            ("pipeline_docs_skipped_total", "Total documents skipped (empty or duplicate)"),
            ("pipeline_jobs_started_total", "Total pipeline jobs started"),
            ("pipeline_jobs_completed_total", "Total pipeline jobs completed"),
            ("pipeline_jobs_cancelled_total", "Total pipeline jobs cancelled"),
            ("llm_calls_total", "Total LLM API calls made"),
            ("llm_errors_total", "Total LLM API errors"),
            ("llm_tokens_input_total", "Total input tokens consumed by LLM calls"),
            ("llm_tokens_output_total", "Total output tokens produced by LLM calls"),
            ("cache_hits_total", "Total cache hits (LLM response cache)"),
            ("cache_misses_total", "Total cache misses (LLM response cache)"),
            ("embedding_calls_total", "Total embedding API calls"),
            ("embedding_tokens_total", "Total tokens sent to embedding API"),
            ("health_checks_total", "Total health check requests"),
        ]
        for name, help_text in counter_defs:
            self._counter_meta[name] = _Counter(name=name, help_text=help_text)

        gauge_defs = [
            ("pipeline_active_jobs", "Number of currently active pipeline jobs"),
            ("pipeline_pending_docs", "Number of documents waiting to be processed"),
            ("llm_available_models", "Number of available LLM models"),
            ("storage_backend_count", "Number of registered storage backends"),
            ("uptime_seconds", "Server uptime in seconds"),
        ]
        for name, help_text in gauge_defs:
            self._gauge_meta[name] = _Gauge(name=name, help_text=help_text)

        histogram_defs = [
            (
                "pipeline_stage_duration_seconds",
                "Duration of pipeline processing stages",
                [0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0],
            ),
            (
                "llm_call_duration_seconds",
                "Duration of LLM API calls",
                [0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
            ),
            (
                "embedding_call_duration_seconds",
                "Duration of embedding API calls",
                [0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
            ),
            (
                "pipeline_doc_duration_seconds",
                "End-to-end duration per document",
                [1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0],
            ),
        ]
        for name, help_text, buckets in histogram_defs:
            self._histogram_meta[name] = _Histogram(
                name=name, help_text=help_text, buckets=buckets
            )

    # ── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _make_key(name: str, labels: dict[str, str] | None) -> str:
        """Build a flat storage key from metric name + labels."""
        if not labels:
            return name
        parts = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{parts}}}"

    @staticmethod
    def _format_labels(labels: dict[str, str] | None) -> str:
        """Format labels for Prometheus text output."""
        if not labels:
            return ""
        parts = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return "{" + parts + "}"

    # ── Counter Operations ──────────────────────────────────────────

    def inc(
        self, name: str, amount: float = 1.0, *, labels: dict[str, str] | None = None
    ) -> None:
        """Increment a counter."""
        key = self._make_key(name, labels)
        with self._lock:
            if name not in self._counter_meta:
                self._counter_meta[name] = _Counter(name=name, help_text="")
            self._counters[key] = self._counters.get(key, 0.0) + amount

    def get_counter(
        self, name: str, *, labels: dict[str, str] | None = None
    ) -> float:
        """Read a counter value."""
        key = self._make_key(name, labels)
        with self._lock:
            return self._counters.get(key, 0.0)

    # ── Gauge Operations ────────────────────────────────────────────

    def set_gauge(
        self, name: str, value: float, *, labels: dict[str, str] | None = None
    ) -> None:
        """Set a gauge value."""
        key = self._make_key(name, labels)
        with self._lock:
            if name not in self._gauge_meta:
                self._gauge_meta[name] = _Gauge(name=name, help_text="")
            self._gauges[key] = value

    def get_gauge(
        self, name: str, *, labels: dict[str, str] | None = None
    ) -> float:
        """Read a gauge value."""
        key = self._make_key(name, labels)
        with self._lock:
            return self._gauges.get(key, 0.0)

    # ── Histogram Operations ────────────────────────────────────────

    def observe(
        self,
        name: str,
        value: float,
        *,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Record a histogram observation."""
        key = self._make_key(name, labels)
        with self._lock:
            if name not in self._histogram_meta:
                return
            meta = self._histogram_meta[name]

            if key not in self._histograms:
                self._histograms[key] = [
                    _HistogramBucket(le=b) for b in meta.buckets
                ]
                self._histogram_sums[key] = 0.0
                self._histogram_counts[key] = 0

            for bucket in self._histograms[key]:
                if value <= bucket.le:
                    bucket.count += 1
            self._histogram_sums[key] += value
            self._histogram_counts[key] += 1

    # ── Convenience Methods ──────────────────────────────────────────

    def record_pipeline_doc_processed(
        self, duration_seconds: float = 0.0, *, kb_name: str = ""
    ) -> None:
        """Record a successfully processed document."""
        labels = {"kb": kb_name} if kb_name else None
        self.inc("pipeline_docs_processed_total", labels=labels)
        if duration_seconds > 0:
            self.observe(
                "pipeline_doc_duration_seconds",
                duration_seconds,
                labels=labels,
            )

    def record_pipeline_doc_failed(self, *, kb_name: str = "", stage: str = "") -> None:
        """Record a failed document."""
        labels: dict[str, str] = {}
        if kb_name:
            labels["kb"] = kb_name
        if stage:
            labels["stage"] = stage
        self.inc("pipeline_docs_failed_total", labels=labels or None)

    def record_pipeline_stage(
        self,
        stage: str,
        duration_seconds: float,
        *,
        kb_name: str = "",
    ) -> None:
        """Record a pipeline stage duration."""
        labels: dict[str, str] = {"stage": stage}
        if kb_name:
            labels["kb"] = kb_name
        self.observe("pipeline_stage_duration_seconds", duration_seconds, labels=labels)

    def record_llm_call(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        duration_seconds: float,
        *,
        success: bool = True,
        role: str = "",
    ) -> None:
        """Record an LLM API call."""
        labels: dict[str, str] = {"model": model}
        if role:
            labels["role"] = role
        self.inc("llm_calls_total", labels=labels)
        self.inc("llm_tokens_input_total", input_tokens, labels=labels)
        self.inc("llm_tokens_output_total", output_tokens, labels=labels)
        self.observe("llm_call_duration_seconds", duration_seconds, labels=labels)
        if not success:
            self.inc("llm_errors_total", labels=labels)

    def record_cache_result(self, *, hit: bool) -> None:
        """Record a cache lookup result."""
        self.inc("cache_hits_total" if hit else "cache_misses_total")

    def record_embedding_call(
        self,
        token_count: int,
        duration_seconds: float,
        *,
        model: str = "",
    ) -> None:
        """Record an embedding API call."""
        labels = {"model": model} if model else None
        self.inc("embedding_calls_total", labels=labels)
        self.inc("embedding_tokens_total", token_count, labels=labels)
        self.observe(
            "embedding_call_duration_seconds", duration_seconds, labels=labels
        )

    # ── Snapshot ─────────────────────────────────────────────────────

    def snapshot(self) -> dict[str, Any]:
        """Return a JSON-serialisable snapshot of all metrics."""
        with self._lock:
            counters: dict[str, float] = dict(self._counters)
            gauges: dict[str, float] = dict(self._gauges)

            histograms: dict[str, dict[str, Any]] = {}
            for key in self._histograms:
                base_name = key.split("{")[0]
                meta = self._histogram_meta.get(base_name)
                histograms[key] = {
                    "buckets": [
                        {"le": b.le, "count": b.count}
                        for b in self._histograms[key]
                    ],
                    "sum": self._histogram_sums.get(key, 0.0),
                    "count": self._histogram_counts.get(key, 0),
                }

        # Auto-computed gauges
        gauges["uptime_seconds"] = time.time() - self._boot_time

        # Derived rates
        total_cache = counters.get("cache_hits_total", 0.0) + counters.get(
            "cache_misses_total", 0.0
        )
        cache_hit_rate = (
            counters.get("cache_hits_total", 0.0) / total_cache
            if total_cache > 0
            else 0.0
        )

        return {
            "counters": counters,
            "gauges": gauges,
            "histograms": histograms,
            "derived": {
                "cache_hit_rate": round(cache_hit_rate, 4),
                "uptime_seconds": round(time.time() - self._boot_time, 2),
            },
            "boot_time": self._boot_time,
        }

    # ── Prometheus Export ────────────────────────────────────────────

    def export_prometheus(self) -> str:
        """Export metrics in Prometheus text exposition format.

        Produces output compatible with ``text/plain; version=0.0.4``.
        """
        lines: list[str] = []
        snap = self.snapshot()

        # Counters
        emitted_counter_names: set[str] = set()
        for key, value in snap["counters"].items():
            base_name = key.split("{")[0]
            if base_name not in emitted_counter_names:
                meta = self._counter_meta.get(base_name)
                help_text = meta.help_text if meta else ""
                if help_text:
                    lines.append(f"# HELP {base_name} {help_text}")
                lines.append(f"# TYPE {base_name} counter")
                emitted_counter_names.add(base_name)
            lines.append(f"{key} {value}")

        # Gauges
        emitted_gauge_names: set[str] = set()
        for key, value in snap["gauges"].items():
            base_name = key.split("{")[0]
            if base_name not in emitted_gauge_names:
                meta = self._gauge_meta.get(base_name)
                help_text = meta.help_text if meta else ""
                if help_text:
                    lines.append(f"# HELP {base_name} {help_text}")
                lines.append(f"# TYPE {base_name} gauge")
                emitted_gauge_names.add(base_name)
            lines.append(f"{key} {value}")

        # Histograms
        emitted_hist_names: set[str] = set()
        for key, data in snap["histograms"].items():
            base_name = key.split("{")[0]
            label_part = key[len(base_name):]
            if base_name not in emitted_hist_names:
                meta = self._histogram_meta.get(base_name)
                help_text = meta.help_text if meta else ""
                if help_text:
                    lines.append(f"# HELP {base_name} {help_text}")
                lines.append(f"# TYPE {base_name} histogram")
                emitted_hist_names.add(base_name)
            for bucket in data["buckets"]:
                le_label = f'le="{bucket["le"]}"'
                if label_part:
                    inner = label_part.strip("{}")
                    full_labels = "{" + inner + "," + le_label + "}"
                else:
                    full_labels = "{" + le_label + "}"
                lines.append(f"{base_name}_bucket{full_labels} {bucket['count']}")
            # +Inf bucket
            inf_label = 'le="+Inf"'
            if label_part:
                inner = label_part.strip("{}")
                full_inf = "{" + inner + "," + inf_label + "}"
            else:
                full_inf = "{" + inf_label + "}"
            lines.append(f"{base_name}_bucket{full_inf} {data['count']}")
            lines.append(f"{base_name}_sum{label_part} {data['sum']}")
            lines.append(f"{base_name}_count{label_part} {data['count']}")

        lines.append("")
        return "\n".join(lines)

    def reset(self) -> None:
        """Reset all metrics (useful for testing)."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._histogram_sums.clear()
            self._histogram_counts.clear()
            self._boot_time = time.time()


# ── Singleton Access ─────────────────────────────────────────────────

_instance: MetricsCollector | None = None
_instance_lock = Lock()


def get_metrics() -> MetricsCollector:
    """Return the process-wide :class:`MetricsCollector` singleton."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = MetricsCollector()
    return _instance
