"""Unit tests for the RAGAS evaluation framework.

Tests cover:
- EvaluationItem and EvaluationReport data structures
- RAGASEvaluator with mocked RAGAS calls
- Metric filtering (ground truth dependencies)
- Error handling and edge cases
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, Mock, patch

import pytest

from aurora_ext.rag.evaluation import (
    EvaluationItem,
    EvaluationReport,
    RAGASEvaluator,
)
from aurora_ext.rag.evaluation.ragas_evaluator import (
    ALL_METRICS,
    METRIC_ANSWER_RELEVANCY,
    METRIC_CONTEXT_PRECISION,
    METRIC_CONTEXT_RECALL,
    METRIC_FAITHFULNESS,
)


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_items() -> list[EvaluationItem]:
    """Sample evaluation items for testing."""
    return [
        EvaluationItem(
            query="What is the capital of France?",
            answer="The capital of France is Paris.",
            contexts=["Paris is the capital and largest city of France."],
            ground_truth="Paris",
        ),
        EvaluationItem(
            query="Who wrote Romeo and Juliet?",
            answer="William Shakespeare wrote Romeo and Juliet.",
            contexts=["Romeo and Juliet is a tragedy by William Shakespeare."],
            ground_truth="William Shakespeare",
        ),
    ]


@pytest.fixture
def sample_items_no_ground_truth() -> list[EvaluationItem]:
    """Sample items without ground truth."""
    return [
        EvaluationItem(
            query="What is the capital of France?",
            answer="The capital of France is Paris.",
            contexts=["Paris is the capital and largest city of France."],
            ground_truth=None,
        ),
    ]


@pytest.fixture
def mock_ragas_result() -> Mock:
    """Mock RAGAS evaluation result."""
    result = Mock()
    result.to_dict = Mock(
        return_value={
            METRIC_FAITHFULNESS: 0.95,
            METRIC_ANSWER_RELEVANCY: 0.88,
            METRIC_CONTEXT_PRECISION: 0.92,
            METRIC_CONTEXT_RECALL: 0.85,
        }
    )
    result.faithfulness = 0.95
    result.answer_relevancy = 0.88
    result.context_precision = 0.92
    result.context_recall = 0.85

    # Mock pandas DataFrame for per-item scores
    import pandas as pd

    df = pd.DataFrame(
        [
            {
                METRIC_FAITHFULNESS: 0.95,
                METRIC_ANSWER_RELEVANCY: 0.88,
                METRIC_CONTEXT_PRECISION: 0.92,
                METRIC_CONTEXT_RECALL: 0.85,
            },
            {
                METRIC_FAITHFULNESS: 0.90,
                METRIC_ANSWER_RELEVANCY: 0.85,
                METRIC_CONTEXT_PRECISION: 0.88,
                METRIC_CONTEXT_RECALL: 0.82,
            },
        ]
    )
    result.to_pandas = Mock(return_value=df)

    return result


# ── Data Structure Tests ────────────────────────────────────────────────────


class TestEvaluationItem:
    """Tests for EvaluationItem dataclass."""

    def test_create_evaluation_item(self):
        """Test creating an EvaluationItem."""
        item = EvaluationItem(
            query="What is AI?",
            answer="AI is artificial intelligence.",
            contexts=["AI stands for artificial intelligence."],
            ground_truth="Artificial Intelligence",
        )
        assert item.query == "What is AI?"
        assert item.answer == "AI is artificial intelligence."
        assert len(item.contexts) == 1
        assert item.ground_truth == "Artificial Intelligence"

    def test_evaluation_item_without_ground_truth(self):
        """Test creating an EvaluationItem without ground truth."""
        item = EvaluationItem(
            query="What is AI?",
            answer="AI is artificial intelligence.",
            contexts=["AI stands for artificial intelligence."],
        )
        assert item.ground_truth is None

    def test_evaluation_item_immutability(self):
        """Test that EvaluationItem is immutable (frozen dataclass)."""
        item = EvaluationItem(
            query="Test",
            answer="Test answer",
            contexts=["context"],
        )
        with pytest.raises(AttributeError):
            item.query = "New query"


class TestEvaluationReport:
    """Tests for EvaluationReport dataclass."""

    def test_create_evaluation_report(self):
        """Test creating an EvaluationReport."""
        report = EvaluationReport(
            scores={METRIC_FAITHFULNESS: 0.95},
            per_item_scores=[{"index": 0, "faithfulness": 0.95}],
            num_items=1,
            metrics_requested=[METRIC_FAITHFULNESS],
            elapsed_seconds=1.23,
            errors=[],
        )
        assert report.scores[METRIC_FAITHFULNESS] == 0.95
        assert report.num_items == 1
        assert report.elapsed_seconds == 1.23

    def test_to_dict(self):
        """Test serializing report to dict."""
        report = EvaluationReport(
            scores={METRIC_FAITHFULNESS: 0.95},
            per_item_scores=[{"index": 0, "faithfulness": 0.95}],
            num_items=1,
            metrics_requested=[METRIC_FAITHFULNESS],
            elapsed_seconds=1.234,
            errors=["Warning: skipped context_recall"],
        )
        result = report.to_dict()
        assert result["scores"] == {METRIC_FAITHFULNESS: 0.95}
        assert result["num_items"] == 1
        assert result["elapsed_seconds"] == 1.234  # Rounded to 3 decimals
        assert len(result["errors"]) == 1

    def test_to_html(self):
        """Test rendering HTML report."""
        report = EvaluationReport(
            scores={
                METRIC_FAITHFULNESS: 0.95,
                METRIC_ANSWER_RELEVANCY: 0.88,
            },
            num_items=2,
            metrics_requested=[METRIC_FAITHFULNESS, METRIC_ANSWER_RELEVANCY],
            elapsed_seconds=2.5,
            errors=["Some error"],
        )
        html = report.to_html()
        assert "<!DOCTYPE html>" in html
        assert "RAG Evaluation Report" in html
        assert METRIC_FAITHFULNESS in html
        assert METRIC_ANSWER_RELEVANCY in html
        assert "0.95" in html or "0.9500" in html
        assert "Some error" in html

    def test_to_html_without_errors(self):
        """Test HTML report without errors."""
        report = EvaluationReport(
            scores={METRIC_FAITHFULNESS: 0.95},
            num_items=1,
            metrics_requested=[METRIC_FAITHFULNESS],
            elapsed_seconds=1.0,
            errors=[],
        )
        html = report.to_html()
        assert "Errors" not in html


# ── Evaluator Tests ─────────────────────────────────────────────────────────


class TestRAGASEvaluator:
    """Tests for RAGASEvaluator."""

    def test_initialization(self):
        """Test evaluator initialization."""
        evaluator = RAGASEvaluator()
        assert evaluator._llm is None
        assert evaluator._embeddings is None

    def test_initialization_with_llm(self):
        """Test evaluator initialization with LLM."""
        mock_llm = Mock()
        evaluator = RAGASEvaluator(llm=mock_llm)
        assert evaluator._llm is mock_llm

    def test_evaluate_empty_items_raises(self):
        """Test that evaluating empty items raises ValueError."""
        evaluator = RAGASEvaluator()
        with pytest.raises(ValueError, match="At least one EvaluationItem"):
            evaluator.evaluate([])

    def test_evaluate_with_all_metrics(
        self, sample_items, mock_ragas_result
    ):
        """Test evaluation with all metrics."""
        # Mock the entire evaluate method to avoid RAGAS dependency
        evaluator = RAGASEvaluator()

        with patch.object(evaluator, '_build_dataset') as mock_build_dataset, \
             patch.object(evaluator, '_build_metrics') as mock_build_metrics:

            mock_build_dataset.return_value = Mock()
            mock_build_metrics.return_value = [Mock()]

            # Mock the ragas import and evaluate call
            import sys
            mock_ragas = Mock()
            mock_ragas.evaluate = Mock(return_value=mock_ragas_result)
            sys.modules['ragas'] = mock_ragas

            try:
                report = evaluator.evaluate(sample_items)
                assert report.num_items == 2
                assert METRIC_FAITHFULNESS in report.scores
                assert METRIC_ANSWER_RELEVANCY in report.scores
                assert METRIC_CONTEXT_PRECISION in report.scores
                assert METRIC_CONTEXT_RECALL in report.scores
                assert report.elapsed_seconds > 0
            finally:
                # Clean up
                if 'ragas' in sys.modules:
                    del sys.modules['ragas']

    def test_evaluate_without_ground_truth(
        self,
        sample_items_no_ground_truth,
        mock_ragas_result,
    ):
        """Test evaluation without ground truth skips context_recall."""
        # Remove context_recall from result
        del mock_ragas_result.context_recall

        evaluator = RAGASEvaluator()

        with patch.object(evaluator, '_build_dataset') as mock_build_dataset, \
             patch.object(evaluator, '_build_metrics') as mock_build_metrics:

            mock_build_dataset.return_value = Mock()
            mock_build_metrics.return_value = [Mock()]

            import sys
            mock_ragas = Mock()
            mock_ragas.evaluate = Mock(return_value=mock_ragas_result)
            sys.modules['ragas'] = mock_ragas

            try:
                report = evaluator.evaluate(sample_items_no_ground_truth)
                # context_recall should be skipped
                assert any("Skipped metrics" in err for err in report.errors)
            finally:
                if 'ragas' in sys.modules:
                    del sys.modules['ragas']

    def test_evaluate_with_specific_metrics(
        self, sample_items, mock_ragas_result
    ):
        """Test evaluation with specific metrics."""
        evaluator = RAGASEvaluator()

        with patch.object(evaluator, '_build_dataset') as mock_build_dataset, \
             patch.object(evaluator, '_build_metrics') as mock_build_metrics:

            mock_build_dataset.return_value = Mock()
            mock_build_metrics.return_value = [Mock()]

            import sys
            mock_ragas = Mock()
            mock_ragas.evaluate = Mock(return_value=mock_ragas_result)
            sys.modules['ragas'] = mock_ragas

            try:
                report = evaluator.evaluate(
                    sample_items,
                    metrics=[METRIC_FAITHFULNESS, METRIC_ANSWER_RELEVANCY],
                )
                assert report.metrics_requested == [
                    METRIC_FAITHFULNESS,
                    METRIC_ANSWER_RELEVANCY,
                ]
            finally:
                if 'ragas' in sys.modules:
                    del sys.modules['ragas']

    def test_evaluate_ragas_not_installed(self, sample_items):
        """Test evaluation when RAGAS is not installed."""
        import builtins

        evaluator = RAGASEvaluator()

        import sys
        # Remove ragas and datasets if they exist
        for mod in ['ragas', 'datasets']:
            if mod in sys.modules:
                del sys.modules[mod]

        # Block ragas import using builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == 'ragas' or name.startswith('ragas.'):
                raise ImportError("No module named 'ragas'")
            if name == 'datasets' or name.startswith('datasets.'):
                raise ImportError("No module named 'datasets'")
            return original_import(name, *args, **kwargs)

        builtins.__import__ = mock_import
        try:
            # Should raise ImportError about ragas being required
            with pytest.raises(ImportError):
                evaluator.evaluate(sample_items)
        finally:
            builtins.__import__ = original_import

    def test_evaluate_ragas_error_handling(self, sample_items):
        """Test error handling during RAGAS evaluation."""
        evaluator = RAGASEvaluator()

        with patch.object(evaluator, '_build_dataset') as mock_build_dataset, \
             patch.object(evaluator, '_build_metrics') as mock_build_metrics:

            mock_build_dataset.return_value = Mock()
            mock_build_metrics.return_value = [Mock()]

            import sys
            mock_ragas = Mock()
            mock_ragas.evaluate = Mock(side_effect=RuntimeError("RAGAS failed"))
            sys.modules['ragas'] = mock_ragas

            try:
                report = evaluator.evaluate(sample_items)
                assert len(report.errors) > 0
                assert "RAGAS evaluation error" in report.errors[0]
            finally:
                if 'ragas' in sys.modules:
                    del sys.modules['ragas']

    def test_build_dataset(self, sample_items):
        """Test building RAGAS dataset from items."""
        try:
            from datasets import Dataset as HFDataset

            dataset = RAGASEvaluator._build_dataset(sample_items)

            assert isinstance(dataset, HFDataset)
            assert len(dataset) == 2
            assert "user_input" in dataset.column_names
            assert "response" in dataset.column_names
            assert "retrieved_contexts" in dataset.column_names
            assert "reference" in dataset.column_names
        except ImportError:
            pytest.skip("datasets package not installed")

    def test_build_metrics(self):
        """Test building RAGAS metrics."""
        try:
            metrics = RAGASEvaluator._build_metrics(
                [METRIC_FAITHFULNESS, METRIC_ANSWER_RELEVANCY]
            )
            assert len(metrics) == 2
        except ImportError:
            pytest.skip("RAGAS not installed")

    def test_extract_aggregate_scores(self, mock_ragas_result):
        """Test extracting aggregate scores from result."""
        scores = RAGASEvaluator._extract_aggregate(
            mock_ragas_result,
            [METRIC_FAITHFULNESS, METRIC_ANSWER_RELEVANCY],
        )
        assert METRIC_FAITHFULNESS in scores
        assert METRIC_ANSWER_RELEVANCY in scores
        assert scores[METRIC_FAITHFULNESS] == 0.95

    def test_extract_per_item_scores(self, sample_items, mock_ragas_result):
        """Test extracting per-item scores."""
        per_item = RAGASEvaluator._extract_per_item(
            mock_ragas_result,
            [METRIC_FAITHFULNESS],
            sample_items,
        )
        assert len(per_item) == 2
        assert per_item[0]["index"] == 0
        assert per_item[0]["query"] == sample_items[0].query
        assert METRIC_FAITHFULNESS in per_item[0]


# ── Metric Constants Tests ──────────────────────────────────────────────────


class TestMetricConstants:
    """Tests for metric constants."""

    def test_all_metrics_defined(self):
        """Test that all expected metrics are defined."""
        assert METRIC_FAITHFULNESS in ALL_METRICS
        assert METRIC_ANSWER_RELEVANCY in ALL_METRICS
        assert METRIC_CONTEXT_PRECISION in ALL_METRICS
        assert METRIC_CONTEXT_RECALL in ALL_METRICS

    def test_all_metrics_frozen(self):
        """Test that ALL_METRICS is immutable."""
        assert isinstance(ALL_METRICS, frozenset)
        with pytest.raises(AttributeError):
            ALL_METRICS.add("new_metric")


# ── Integration Tests ───────────────────────────────────────────────────────


class TestEvaluatorIntegration:
    """Integration tests for the evaluator."""

    @pytest.mark.skipif(
        True,  # Skip by default since it requires real RAGAS + LLM
        reason="Requires RAGAS and LLM configuration",
    )
    def test_evaluate_real_ragas(self, sample_items):
        """Test evaluation with real RAGAS (requires installation)."""
        # This test is skipped by default
        evaluator = RAGASEvaluator()
        try:
            report = evaluator.evaluate(
                sample_items,
                metrics=[METRIC_FAITHFULNESS],
            )
            assert report.num_items == 2
            assert METRIC_FAITHFULNESS in report.scores
        except ImportError:
            pytest.skip("RAGAS not installed")
