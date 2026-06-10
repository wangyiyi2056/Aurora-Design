"""RAGAS evaluation routes — POST /evaluate for RAG quality scoring.

Provides a single endpoint that evaluates query-answer-context triples
using the RAGAS framework, returning per-metric scores and an aggregate
report.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

from aurora_serve.knowledge.v2.schemas import (
    EvaluationRequest,
    EvaluationResponse,
    EvaluationScoreDetail,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["evaluation"])


def get_knowledge_v2_service(request: Request) -> Any:
    """Resolve the KnowledgeV2Service from the system app registry."""
    from aurora_serve.knowledge.v2.service import KnowledgeV2Service

    return request.app.state.system_app.get_component(
        "knowledge_v2_service", KnowledgeV2Service
    )


@router.post("/evaluate/", response_model=EvaluationResponse)
async def evaluate(
    name: str,
    req: EvaluationRequest,
    service: Any = Depends(get_knowledge_v2_service),
) -> EvaluationResponse:
    """Evaluate RAG quality for a batch of query-answer pairs.

    Uses the RAGAS framework to compute:
    - ``faithfulness`` — is the answer grounded in the context?
    - ``answer_relevancy`` — does the answer address the question?
    - ``context_precision`` — is the retrieved context relevant?
    - ``context_recall`` — does the context cover the ground truth?

    ``ground_truth`` is optional per item — when absent, ``context_recall``
    is skipped.

    When ``auto_retrieve`` is True and an item has empty ``contexts``,
    the service will query this knowledge base to populate them.
    """
    try:
        report = await service.evaluate(
            kb_name=name,
            items=[item.model_dump() for item in req.items],
            metrics=req.metrics,
            auto_retrieve=req.auto_retrieve,
            query_mode=req.query_mode,
        )
        return EvaluationResponse(
            scores=report.get("scores", {}),
            per_item_scores=[
                EvaluationScoreDetail(
                    index=p.get("index", i),
                    query=p.get("query", ""),
                    scores={
                        k: v
                        for k, v in p.items()
                        if k not in ("index", "query")
                    },
                )
                for i, p in enumerate(report.get("per_item_scores", []))
            ],
            num_items=report.get("num_items", 0),
            metrics_requested=report.get("metrics_requested", []),
            elapsed_seconds=report.get("elapsed_seconds", 0.0),
            errors=report.get("errors", []),
        )
    except ImportError as exc:
        raise HTTPException(
            status_code=501,
            detail=(
                "RAGAS evaluation dependencies not installed. "
                "Install with: pip install 'aurora-ext[ragas]'. "
                f"Original error: {exc}"
            ),
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Evaluation failed for KB '%s'", name)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/evaluate/html")
async def evaluate_html(
    name: str,
    req: EvaluationRequest,
    service: Any = Depends(get_knowledge_v2_service),
) -> HTMLResponse:
    """Evaluate RAG quality and return an HTML report."""
    try:
        report = await service.evaluate(
            kb_name=name,
            items=[item.model_dump() for item in req.items],
            metrics=req.metrics,
            auto_retrieve=req.auto_retrieve,
            query_mode=req.query_mode,
        )
        from aurora_ext.rag.evaluation import EvaluationReport

        eval_report = EvaluationReport(
            scores=report.get("scores", {}),
            per_item_scores=report.get("per_item_scores", []),
            num_items=report.get("num_items", 0),
            metrics_requested=report.get("metrics_requested", []),
            elapsed_seconds=report.get("elapsed_seconds", 0.0),
            errors=report.get("errors", []),
        )
        return HTMLResponse(content=eval_report.to_html())
    except ImportError as exc:
        raise HTTPException(
            status_code=501,
            detail=f"RAGAS not installed: {exc}",
        ) from exc
    except Exception as exc:
        logger.exception("HTML evaluation failed for KB '%s'", name)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
