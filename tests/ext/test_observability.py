"""Tests for the RAG observability modules (metrics + tracing)."""

from __future__ import annotations

import time

import pytest

from aurora_ext.rag.observability.metrics import MetricsCollector, get_metrics
from aurora_ext.rag.observability.tracing import (
    PipelineSpan,
    PipelineTrace,
    SpanStatus,
    TraceStore,
    get_trace_store,
)


# ── MetricsCollector Tests ────────────────────────────────────────────


class TestMetricsCollector:
    """Unit tests for :class:`MetricsCollector`."""

    def setup_method(self):
        self.m = MetricsCollector()

    def test_inc_counter_default(self):
        self.m.inc("test_counter")
        assert self.m.get_counter("test_counter") == 1.0

    def test_inc_counter_custom_amount(self):
        self.m.inc("test_counter", 5.0)
        assert self.m.get_counter("test_counter") == 5.0

    def test_inc_counter_accumulates(self):
        self.m.inc("test_counter", 3.0)
        self.m.inc("test_counter", 7.0)
        assert self.m.get_counter("test_counter") == 10.0

    def test_counter_with_labels(self):
        self.m.inc("test_counter", labels={"model": "gpt-4o"})
        self.m.inc("test_counter", labels={"model": "claude"})
        assert self.m.get_counter("test_counter", labels={"model": "gpt-4o"}) == 1.0
        assert self.m.get_counter("test_counter", labels={"model": "claude"}) == 1.0
        # Without labels should be 0 (separate key)
        assert self.m.get_counter("test_counter") == 0.0

    def test_set_gauge(self):
        self.m.set_gauge("test_gauge", 42.0)
        assert self.m.get_gauge("test_gauge") == 42.0

    def test_set_gauge_overwrites(self):
        self.m.set_gauge("test_gauge", 10.0)
        self.m.set_gauge("test_gauge", 20.0)
        assert self.m.get_gauge("test_gauge") == 20.0

    def test_gauge_with_labels(self):
        self.m.set_gauge("test_gauge", 5.0, labels={"kb": "default"})
        assert self.m.get_gauge("test_gauge", labels={"kb": "default"}) == 5.0
        assert self.m.get_gauge("test_gauge") == 0.0

    def test_observe_histogram(self):
        for val in [0.1, 0.5, 1.0, 2.5, 5.0]:
            self.m.observe("pipeline_stage_duration_seconds", val)
        snap = self.m.snapshot()
        key = "pipeline_stage_duration_seconds"
        assert key in snap["histograms"]
        assert snap["histograms"][key]["count"] == 5
        assert snap["histograms"][key]["sum"] == pytest.approx(9.1)

    def test_observe_unknown_histogram_noop(self):
        # Observing an unregistered histogram should not crash
        self.m.observe("nonexistent_histogram", 1.0)
        snap = self.m.snapshot()
        assert "nonexistent_histogram" not in snap["histograms"]

    def test_snapshot_structure(self):
        self.m.inc("llm_calls_total")
        self.m.set_gauge("pipeline_active_jobs", 1)
        snap = self.m.snapshot()
        assert "counters" in snap
        assert "gauges" in snap
        assert "histograms" in snap
        assert "derived" in snap
        assert "boot_time" in snap
        assert "uptime_seconds" in snap["derived"]
        assert "cache_hit_rate" in snap["derived"]

    def test_cache_hit_rate_derived(self):
        self.m.inc("cache_hits_total", 3)
        self.m.inc("cache_misses_total", 1)
        snap = self.m.snapshot()
        assert snap["derived"]["cache_hit_rate"] == pytest.approx(0.75)

    def test_cache_hit_rate_zero_when_no_lookups(self):
        snap = self.m.snapshot()
        assert snap["derived"]["cache_hit_rate"] == 0.0

    def test_reset(self):
        self.m.inc("test_counter", 100)
        self.m.set_gauge("test_gauge", 50)
        self.m.reset()
        assert self.m.get_counter("test_counter") == 0.0
        assert self.m.get_gauge("test_gauge") == 0.0

    # ── Convenience Methods ──────────────────────────────────────────

    def test_record_pipeline_doc_processed(self):
        self.m.record_pipeline_doc_processed(2.5, kb_name="kb1")
        assert self.m.get_counter(
            "pipeline_docs_processed_total", labels={"kb": "kb1"}
        ) == 1.0

    def test_record_pipeline_doc_failed(self):
        self.m.record_pipeline_doc_failed(kb_name="kb1", stage="parse")
        assert self.m.get_counter(
            "pipeline_docs_failed_total", labels={"kb": "kb1", "stage": "parse"}
        ) == 1.0

    def test_record_pipeline_stage(self):
        self.m.record_pipeline_stage("extract", 3.5, kb_name="kb1")
        snap = self.m.snapshot()
        key = 'pipeline_stage_duration_seconds{kb="kb1",stage="extract"}'
        assert key in snap["histograms"]

    def test_record_llm_call(self):
        self.m.record_llm_call(
            "gpt-4o", 1500, 500, 1.23, role="extract"
        )
        labels = {"model": "gpt-4o", "role": "extract"}
        assert self.m.get_counter("llm_calls_total", labels=labels) == 1.0
        assert self.m.get_counter("llm_tokens_input_total", labels=labels) == 1500.0
        assert self.m.get_counter("llm_tokens_output_total", labels=labels) == 500.0

    def test_record_llm_call_error(self):
        self.m.record_llm_call("gpt-4o", 0, 0, 0.1, success=False)
        labels = {"model": "gpt-4o"}
        assert self.m.get_counter("llm_errors_total", labels=labels) == 1.0

    def test_record_cache_result(self):
        self.m.record_cache_result(hit=True)
        self.m.record_cache_result(hit=True)
        self.m.record_cache_result(hit=False)
        assert self.m.get_counter("cache_hits_total") == 2.0
        assert self.m.get_counter("cache_misses_total") == 1.0

    def test_record_embedding_call(self):
        self.m.record_embedding_call(100, 0.05, model="text-embedding-3-small")
        labels = {"model": "text-embedding-3-small"}
        assert self.m.get_counter("embedding_calls_total", labels=labels) == 1.0
        assert self.m.get_counter("embedding_tokens_total", labels=labels) == 100.0

    # ── Prometheus Export ─────────────────────────────────────────────

    def test_prometheus_export_counters(self):
        self.m.inc("pipeline_docs_processed_total")
        output = self.m.export_prometheus()
        assert "# TYPE pipeline_docs_processed_total counter" in output
        assert "pipeline_docs_processed_total 1.0" in output

    def test_prometheus_export_gauges(self):
        self.m.set_gauge("pipeline_active_jobs", 3)
        output = self.m.export_prometheus()
        assert "# TYPE pipeline_active_jobs gauge" in output
        assert "pipeline_active_jobs 3" in output

    def test_prometheus_export_histograms(self):
        self.m.observe("pipeline_stage_duration_seconds", 0.5)
        output = self.m.export_prometheus()
        assert "# TYPE pipeline_stage_duration_seconds histogram" in output
        assert "pipeline_stage_duration_seconds_bucket" in output
        assert "pipeline_stage_duration_seconds_sum" in output
        assert "pipeline_stage_duration_seconds_count" in output
        assert 'le="+Inf"' in output

    def test_prometheus_export_with_labels(self):
        self.m.inc("llm_calls_total", labels={"model": "gpt-4o"})
        output = self.m.export_prometheus()
        assert 'llm_calls_total{model="gpt-4o"} 1.0' in output

    def test_prometheus_export_empty(self):
        output = self.m.export_prometheus()
        # Should still have uptime_seconds gauge
        assert "uptime_seconds" in output
        assert output.endswith("\n")


# ── Singleton Tests ───────────────────────────────────────────────────


class TestMetricsSingleton:
    def test_get_metrics_returns_same_instance(self):
        m1 = get_metrics()
        m2 = get_metrics()
        assert m1 is m2

    def test_get_metrics_is_metrics_collector(self):
        assert isinstance(get_metrics(), MetricsCollector)


# ── PipelineSpan Tests ────────────────────────────────────────────────


class TestPipelineSpan:
    def test_start_sets_running(self):
        span = PipelineSpan(span_id="s1", stage="parse")
        span.start()
        assert span.status == SpanStatus.RUNNING
        assert span.started_at > 0

    def test_finish_sets_completed(self):
        span = PipelineSpan(span_id="s1", stage="parse")
        span.start()
        time.sleep(0.01)
        span.finish()
        assert span.status == SpanStatus.COMPLETED
        assert span.duration_ms > 0

    def test_finish_with_error(self):
        span = PipelineSpan(span_id="s1", stage="parse")
        span.start()
        span.finish(error="something broke")
        assert span.status == SpanStatus.FAILED
        assert span.error_message == "something broke"

    def test_skip(self):
        span = PipelineSpan(span_id="s1", stage="extract")
        span.skip(reason="skip_kg flag")
        assert span.status == SpanStatus.SKIPPED
        assert span.metadata["skip_reason"] == "skip_kg flag"

    def test_to_dict(self):
        span = PipelineSpan(
            span_id="s1",
            track_id="t1",
            doc_id="d1",
            stage="parse",
        )
        span.start()
        span.finish()
        d = span.to_dict()
        assert d["span_id"] == "s1"
        assert d["track_id"] == "t1"
        assert d["stage"] == "parse"
        assert d["status"] == "completed"
        assert d["duration_ms"] >= 0


# ── PipelineTrace Tests ──────────────────────────────────────────────


class TestPipelineTrace:
    def test_add_span(self):
        trace = PipelineTrace(track_id="t1")
        span = trace.add_span(doc_id="d1", stage="parse")
        assert span.status == SpanStatus.RUNNING
        assert len(trace.spans) == 1

    def test_finish(self):
        trace = PipelineTrace(track_id="t1")
        trace.finish()
        assert trace.status == "completed"
        assert trace.finished_at > 0

    def test_finish_with_status(self):
        trace = PipelineTrace(track_id="t1")
        trace.finish(status="cancelled")
        assert trace.status == "cancelled"

    def test_duration_ms(self):
        trace = PipelineTrace(track_id="t1")
        time.sleep(0.01)
        assert trace.duration_ms > 0

    def test_to_dict_includes_stage_summary(self):
        trace = PipelineTrace(track_id="t1")
        s1 = trace.add_span(doc_id="d1", stage="parse")
        s1.finish()
        s2 = trace.add_span(doc_id="d1", stage="extract")
        s2.finish()
        d = trace.to_dict(include_spans=True)
        assert "stage_summary" in d
        assert "parse" in d["stage_summary"]
        assert "extract" in d["stage_summary"]
        assert d["stage_summary"]["parse"]["count"] == 1
        assert len(d["spans"]) == 2

    def test_to_dict_without_spans(self):
        trace = PipelineTrace(track_id="t1")
        trace.add_span(doc_id="d1", stage="parse").finish()
        d = trace.to_dict(include_spans=False)
        assert "spans" not in d
        assert d["span_count"] == 1


# ── TraceStore Tests ──────────────────────────────────────────────────


class TestTraceStore:
    def setup_method(self):
        self.store = TraceStore(max_traces=10)

    def test_create_and_get_trace(self):
        trace = self.store.create_trace("t1", kb_name="kb1")
        assert trace.track_id == "t1"
        retrieved = self.store.get_trace("t1")
        assert retrieved is trace

    def test_get_trace_returns_none_for_missing(self):
        assert self.store.get_trace("nonexistent") is None

    def test_list_traces_pagination(self):
        for i in range(8):
            t = self.store.create_trace(f"t{i}")
            t.finish()

        page1, total1 = self.store.list_traces(page=1, page_size=3)
        assert len(page1) == 3
        assert total1 == 8

        page2, total2 = self.store.list_traces(page=2, page_size=3)
        assert len(page2) == 3

        page3, total3 = self.store.list_traces(page=3, page_size=3)
        assert len(page3) == 2

    def test_list_traces_filter_by_status(self):
        t1 = self.store.create_trace("t1")
        t1.finish(status="completed")
        t2 = self.store.create_trace("t2")
        t2.finish(status="failed")
        t3 = self.store.create_trace("t3")  # still running

        completed, _ = self.store.list_traces(status="completed")
        assert len(completed) == 1
        assert completed[0]["track_id"] == "t1"

        running, _ = self.store.list_traces(status="running")
        assert len(running) == 1

    def test_list_traces_filter_by_kb_name(self):
        self.store.create_trace("t1", kb_name="kb_a")
        self.store.create_trace("t2", kb_name="kb_b")
        self.store.create_trace("t3", kb_name="kb_a")

        filtered, total = self.store.list_traces(kb_name="kb_a")
        assert total == 2

    def test_list_traces_newest_first(self):
        t1 = self.store.create_trace("t1")
        t1.created_at = 1000
        t2 = self.store.create_trace("t2")
        t2.created_at = 2000

        traces, _ = self.store.list_traces()
        assert traces[0]["track_id"] == "t2"

    def test_eviction(self):
        store = TraceStore(max_traces=3)
        for i in range(5):
            store.create_trace(f"t{i}")

        assert store.get_trace("t0") is None
        assert store.get_trace("t1") is None
        assert store.get_trace("t2") is not None
        assert store.get_trace("t3") is not None
        assert store.get_trace("t4") is not None

    def test_get_trace_detail(self):
        trace = self.store.create_trace("t1")
        trace.add_span(doc_id="d1", stage="parse").finish()
        detail = self.store.get_trace_detail("t1")
        assert detail is not None
        assert detail["track_id"] == "t1"
        assert len(detail["spans"]) == 1

    def test_get_trace_detail_returns_none(self):
        assert self.store.get_trace_detail("nonexistent") is None

    def test_stats(self):
        t1 = self.store.create_trace("t1", total_docs=5)
        t1.processed_docs = 3
        t1.finish(status="completed")
        t2 = self.store.create_trace("t2", total_docs=2)
        t2.failed_docs = 1
        t2.finish(status="failed")

        stats = self.store.stats()
        assert stats["total_traces"] == 2
        assert stats["by_status"]["completed"] == 1
        assert stats["by_status"]["failed"] == 1
        assert stats["total_docs"] == 7
        assert stats["total_processed"] == 3
        assert stats["total_failed"] == 1

    def test_reset(self):
        self.store.create_trace("t1")
        self.store.reset()
        assert self.store.stats()["total_traces"] == 0

    def test_stats_max_traces(self):
        stats = self.store.stats()
        assert stats["max_traces"] == 10


# ── Singleton Tests ───────────────────────────────────────────────────


class TestTraceStoreSingleton:
    def test_get_trace_store_returns_same_instance(self):
        s1 = get_trace_store()
        s2 = get_trace_store()
        assert s1 is s2

    def test_get_trace_store_is_trace_store(self):
        assert isinstance(get_trace_store(), TraceStore)
