"""RAGASEvaluator — RAG quality evaluation via the RAGAS framework.

Wraps ``ragas`` to compute:
  - faithfulness       (is the answer grounded in the retrieved context?)
  - answer_relevancy   (does the answer address the question?)
  - context_precision  (is the retrieved context relevant?)
  - context_recall     (does the context cover the ground truth?)

Ground truth is **optional** — when provided, ``context_recall`` is also
computed; otherwise only faithfulness, answer_relevancy, and
context_precision are returned.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

logger = logging.getLogger(__name__)

# ── Metric name constants ──────────────────────────────────────────

METRIC_FAITHFULNESS = "faithfulness"
METRIC_ANSWER_RELEVANCY = "answer_relevancy"
METRIC_CONTEXT_PRECISION = "context_precision"
METRIC_CONTEXT_RECALL = "context_recall"

ALL_METRICS: frozenset[str] = frozenset(
    [
        METRIC_FAITHFULNESS,
        METRIC_ANSWER_RELEVANCY,
        METRIC_CONTEXT_PRECISION,
        METRIC_CONTEXT_RECALL,
    ]
)

# Metrics that require ground truth
_GT_REQUIRED_METRICS: frozenset[str] = frozenset([METRIC_CONTEXT_RECALL])


# ── Data structures ────────────────────────────────────────────────


@dataclass(frozen=True)
class EvaluationItem:
    """A single query-answer pair for evaluation.

    Attributes:
        query: The user's question.
        answer: The generated answer from the RAG pipeline.
        contexts: List of retrieved context strings (chunks).
        ground_truth: Optional reference answer for recall scoring.
    """

    query: str
    answer: str
    contexts: list[str]
    ground_truth: Optional[str] = None


@dataclass
class EvaluationReport:
    """Aggregated evaluation results across a batch.

    Attributes:
        scores: Dict mapping metric name → aggregate score (0.0–1.0).
        per_item_scores: List of per-item dicts with individual metric scores.
        num_items: Total number of items evaluated.
        metrics_requested: Which metrics were requested.
        elapsed_seconds: Wall-clock time for the evaluation run.
        errors: List of error messages for items that failed to evaluate.
    """

    scores: dict[str, float] = field(default_factory=dict)
    per_item_scores: list[dict[str, Any]] = field(default_factory=list)
    num_items: int = 0
    metrics_requested: list[str] = field(default_factory=list)
    elapsed_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialise the report to a plain dict."""
        return {
            "scores": self.scores,
            "per_item_scores": self.per_item_scores,
            "num_items": self.num_items,
            "metrics_requested": self.metrics_requested,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "errors": self.errors,
        }

    def to_html(self) -> str:
        """Render a minimal HTML evaluation report."""
        rows = "".join(
            f"<tr><td>{m}</td><td>{v:.4f}</td></tr>"
            for m, v in sorted(self.scores.items())
        )
        errors_html = ""
        if self.errors:
            error_items = "".join(f"<li>{e}</li>" for e in self.errors)
            errors_html = f"<h3>Errors</h3><ul>{error_items}</ul>"

        return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>RAG Evaluation Report</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 640px; margin: 2rem auto; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid #ddd; padding: .5rem .75rem; text-align: left; }}
  th {{ background: #f5f5f5; }}
  .meta {{ color: #666; font-size: .875rem; }}
</style></head>
<body>
<h1>RAG Evaluation Report</h1>
<p class="meta">
  Items evaluated: {self.num_items} &middot;
  Metrics: {', '.join(self.metrics_requested)} &middot;
  Elapsed: {self.elapsed_seconds:.2f}s
</p>
<table><thead><tr><th>Metric</th><th>Score</th></tr></thead>
<tbody>{rows}</tbody></table>
{errors_html}
</body></html>"""


# ── Evaluator ──────────────────────────────────────────────────────


class RAGASEvaluator:
    """Evaluate RAG pipeline quality using the RAGAS framework.

    The evaluator lazily imports ``ragas`` so that the dependency is
    truly optional — it is only resolved when ``evaluate()`` is called,
    not at import time.

    Parameters:
        llm: A LangChain-compatible LLM instance (``BaseChatModel``).
             Required for metrics that use an LLM judge (all four
             core metrics by default).  When *None*, an attempt is made
             to use RAGAS's default model configuration.
        embeddings: A LangChain-compatible embeddings instance.
             Required for answer_relevancy.  Same lazy fallback as *llm*.
    """

    def __init__(
        self,
        llm: Any | None = None,
        embeddings: Any | None = None,
    ) -> None:
        self._llm = llm
        self._embeddings = embeddings

    # ── Public API ─────────────────────────────────────────────────

    def evaluate(
        self,
        items: Sequence[EvaluationItem],
        *,
        metrics: Sequence[str] | None = None,
    ) -> EvaluationReport:
        """Run evaluation over a batch of items.

        Args:
            items: One or more ``EvaluationItem`` instances.
            metrics: Which metrics to compute.  Defaults to all four.
                     Unknown names are silently ignored.

        Returns:
            An ``EvaluationReport`` with aggregate and per-item scores.

        Raises:
            ImportError: If the ``ragas`` package is not installed.
            ValueError: If *items* is empty.
        """
        if not items:
            raise ValueError("At least one EvaluationItem is required")

        start = time.monotonic()

        requested = list(metrics) if metrics else list(ALL_METRICS)

        # Filter out ground-truth-dependent metrics when no GT is provided
        has_any_gt = any(item.ground_truth is not None for item in items)
        effective_metrics = [
            m for m in requested
            if m not in _GT_REQUIRED_METRICS or has_any_gt
        ]

        # Build ragas Dataset
        ragas_dataset = self._build_dataset(items)

        # Build the metric instances
        ragas_metrics = self._build_metrics(effective_metrics)

        # Run ragas evaluation
        try:
            from ragas import evaluate as ragas_evaluate

            result = ragas_evaluate(
                dataset=ragas_dataset,
                metrics=ragas_metrics,
                llm=self._llm,
                embeddings=self._embeddings,
            )
        except ImportError:
            raise ImportError(
                "The 'ragas' package is required for evaluation. "
                "Install it with: pip install 'aurora-ext[ragas]'"
            )
        except Exception as exc:
            logger.exception("RAGAS evaluation failed")
            return EvaluationReport(
                num_items=len(items),
                metrics_requested=requested,
                elapsed_seconds=time.monotonic() - start,
                errors=[f"RAGAS evaluation error: {exc}"],
            )

        # Extract scores
        aggregate = self._extract_aggregate(result, effective_metrics)
        per_item = self._extract_per_item(result, effective_metrics, items)

        skipped = [m for m in requested if m not in effective_metrics]
        errors: list[str] = []
        if skipped:
            errors.append(
                f"Skipped metrics requiring ground_truth: {', '.join(skipped)}"
            )

        return EvaluationReport(
            scores=aggregate,
            per_item_scores=per_item,
            num_items=len(items),
            metrics_requested=requested,
            elapsed_seconds=time.monotonic() - start,
            errors=errors,
        )

    # ── Internals ──────────────────────────────────────────────────

    @staticmethod
    def _build_dataset(items: Sequence[EvaluationItem]) -> Any:
        """Convert ``EvaluationItem`` list to a ``ragas.Dataset``."""
        from datasets import Dataset as HFDataset

        data: dict[str, list] = {
            "user_input": [],
            "response": [],
            "retrieved_contexts": [],
            "reference": [],
        }
        for item in items:
            data["user_input"].append(item.query)
            data["response"].append(item.answer)
            data["retrieved_contexts"].append(item.contexts)
            data["reference"].append(item.ground_truth or "")

        return HFDataset.from_dict(data)

    @staticmethod
    def _build_metrics(metric_names: list[str]) -> list:
        """Instantiate ragas metric objects for the requested names."""
        from ragas.metrics import (
            answer_relevancy,
            context_precision,
            context_recall,
            faithfulness,
        )

        registry: dict[str, Any] = {
            METRIC_FAITHFULNESS: faithfulness,
            METRIC_ANSWER_RELEVANCY: answer_relevancy,
            METRIC_CONTEXT_PRECISION: context_precision,
            METRIC_CONTEXT_RECALL: context_recall,
        }
        return [registry[name] for name in metric_names if name in registry]

    @staticmethod
    def _extract_aggregate(result: Any, metrics: list[str]) -> dict[str, float]:
        """Pull aggregate scores from the ragas ``EvaluationResult``."""
        scores: dict[str, float] = {}
        try:
            result_dict = result.to_dict() if hasattr(result, "to_dict") else {}
            # ragas stores aggregate scores at the top level of the result
            for m in metrics:
                val = getattr(result, m, None)
                if val is None and isinstance(result_dict, dict):
                    val = result_dict.get(m)
                if val is not None:
                    scores[m] = float(val)
        except Exception as exc:
            logger.warning("Failed to extract aggregate scores: %s", exc)
        return scores

    @staticmethod
    def _extract_per_item(
        result: Any,
        metrics: list[str],
        items: Sequence[EvaluationItem],
    ) -> list[dict[str, Any]]:
        """Pull per-item scores from the ragas ``EvaluationResult``."""
        per_item: list[dict[str, Any]] = []
        try:
            df = result.to_pandas() if hasattr(result, "to_pandas") else None
            if df is not None:
                for idx, row in df.iterrows():
                    item_scores: dict[str, Any] = {
                        "index": int(idx),
                        "query": items[idx].query if idx < len(items) else "",
                    }
                    for m in metrics:
                        if m in row.index:
                            val = row[m]
                            item_scores[m] = None if val != val else float(val)
                        else:
                            item_scores[m] = None
                    per_item.append(item_scores)
        except Exception as exc:
            logger.warning("Failed to extract per-item scores: %s", exc)
        return per_item
