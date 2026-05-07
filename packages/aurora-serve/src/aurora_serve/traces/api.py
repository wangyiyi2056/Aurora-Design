from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from aurora_serve.metadata import TraceEventEntity

router = APIRouter(prefix="/traces", tags=["traces"])


class TraceRequest(BaseModel):
    name: str
    span_type: str = "event"
    metadata: dict = Field(default_factory=dict)


class TraceUpdateRequest(BaseModel):
    name: str | None = None
    span_type: str | None = None
    metadata: dict | None = None


def trace_to_dict(entity: TraceEventEntity) -> dict:
    return {
        "id": entity.id,
        "name": entity.name,
        "span_type": entity.span_type,
        "metadata": entity.meta or {},
        "created_at": entity.created_at,
        "updated_at": entity.updated_at,
    }


def _get_trace_or_404(session, trace_id: str) -> TraceEventEntity:
    entity = session.get(TraceEventEntity, trace_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Trace event not found")
    return entity


@router.post("")
async def create_trace(req: TraceRequest, request: Request) -> dict:
    with request.app.state.metadata_store.session() as session:
        payload = req.model_dump()
        entity = TraceEventEntity(
            id=str(uuid4()),
            name=payload["name"],
            span_type=payload["span_type"],
            meta=payload["metadata"],
        )
        session.add(entity)
        session.commit()
        return trace_to_dict(entity)


@router.get("")
async def list_traces(request: Request) -> dict:
    with request.app.state.metadata_store.session() as session:
        return {"items": [trace_to_dict(item) for item in session.query(TraceEventEntity).all()]}


@router.get("/{trace_id}")
async def get_trace(trace_id: str, request: Request) -> dict:
    with request.app.state.metadata_store.session() as session:
        return trace_to_dict(_get_trace_or_404(session, trace_id))


@router.put("/{trace_id}")
async def update_trace(trace_id: str, req: TraceUpdateRequest, request: Request) -> dict:
    with request.app.state.metadata_store.session() as session:
        entity = _get_trace_or_404(session, trace_id)
        payload = req.model_dump(exclude_unset=True)
        if "metadata" in payload:
            entity.meta = payload.pop("metadata")
        for key, value in payload.items():
            setattr(entity, key, value)
        session.commit()
        return trace_to_dict(entity)


@router.delete("/{trace_id}")
async def delete_trace(trace_id: str, request: Request) -> dict:
    with request.app.state.metadata_store.session() as session:
        entity = _get_trace_or_404(session, trace_id)
        session.delete(entity)
        session.commit()
        return {"deleted": True}
