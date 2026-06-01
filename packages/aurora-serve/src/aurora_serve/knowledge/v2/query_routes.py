"""RAG query routes — non-streaming, streaming (NDJSON), and structured data.

Supports all 6 retrieval modes: local, global, hybrid, naive, mix, bypass.
All routes receive ``name: str`` as a path parameter.
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from aurora_serve.knowledge.v2.schemas import (
    QueryDataResponse,
    QueryRequest,
    QueryResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["query"])


def get_knowledge_v2_service(request: Request) -> Any:
    """Resolve the KnowledgeV2Service from the system app registry."""
    from aurora_serve.knowledge.v2.service import KnowledgeV2Service

    return request.app.state.system_app.get_component(
        "knowledge_v2_service", KnowledgeV2Service
    )


def _build_query_kwargs(name: str, req: QueryRequest, stream: bool) -> dict[str, Any]:
    """Build the keyword arguments dict for ``service.query()``."""
    return dict(
        kb_name=name,
        query=req.query,
        mode=req.mode,
        only_need_context=req.only_need_context,
        only_need_prompt=req.only_need_prompt,
        response_type=req.response_type,
        top_k=req.top_k,
        chunk_top_k=req.chunk_top_k,
        max_entity_tokens=req.max_entity_tokens,
        max_relation_tokens=req.max_relation_tokens,
        max_total_tokens=req.max_total_tokens,
        hl_keywords=req.hl_keywords,
        ll_keywords=req.ll_keywords,
        conversation_history=req.conversation_history,
        user_prompt=req.user_prompt,
        enable_rerank=req.enable_rerank,
        include_references=req.include_references,
        include_chunk_content=req.include_chunk_content,
        stream=stream,
    )


@router.post("/query/", response_model=QueryResponse)
async def query(
    name: str,
    req: QueryRequest,
    service: Any = Depends(get_knowledge_v2_service),
) -> QueryResponse:
    """Execute a non-streaming RAG query."""
    try:
        result = await service.query(**_build_query_kwargs(name, req, stream=False))
        return QueryResponse(
            response=result.get("response", ""),
            references=result.get("references"),
        )
    except Exception as exc:
        logger.exception("Query failed: %s", req.query[:100])
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/query/stream")
async def query_stream(
    name: str,
    req: QueryRequest,
    service: Any = Depends(get_knowledge_v2_service),
) -> StreamingResponse:
    """Execute a streaming RAG query via NDJSON."""

    async def _ndjson_stream() -> AsyncGenerator[str, None]:
        try:
            result = await service.query(**_build_query_kwargs(name, req, stream=True))

            stream_iter = result.get("stream_iterator")
            if stream_iter is None:
                yield json.dumps({"response": result.get("response", "")}) + "\n"
                return

            # First line: references (if available)
            references = result.get("references")
            if references:
                yield json.dumps({"references": references}) + "\n"

            async for chunk_text in stream_iter:
                yield json.dumps({"response": chunk_text}) + "\n"

        except Exception as exc:
            logger.exception("Stream query failed: %s", req.query[:100])
            yield json.dumps({"error": str(exc)}) + "\n"

    return StreamingResponse(
        _ndjson_stream(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/query/data", response_model=QueryDataResponse)
async def query_data(
    name: str,
    req: QueryRequest,
    service: Any = Depends(get_knowledge_v2_service),
) -> QueryDataResponse:
    """Execute a structured data retrieval query (entities, relationships, chunks)."""
    try:
        result = await service.query(**_build_query_kwargs(name, req, stream=False))
        return QueryDataResponse(
            status="success",
            message="Data retrieved",
            data={
                "entities": result.get("entities", []),
                "relationships": result.get("relationships", []),
                "chunks": result.get("chunks", []),
                "references": result.get("references", []),
            },
            metadata={
                "query_mode": req.mode.value,
                "hl_keywords": result.get("hl_keywords", []),
                "ll_keywords": result.get("ll_keywords", []),
            },
        )
    except Exception as exc:
        logger.exception("Data query failed: %s", req.query[:100])
        raise HTTPException(status_code=500, detail=str(exc)) from exc
