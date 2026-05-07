from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from aurora_serve.metadata import FeedbackEntity

router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackRequest(BaseModel):
    target_type: str
    target_id: str
    rating: int = 0
    comment: str = ""
    extra: dict = Field(default_factory=dict)


class FeedbackUpdateRequest(BaseModel):
    target_type: str | None = None
    target_id: str | None = None
    rating: int | None = None
    comment: str | None = None
    extra: dict | None = None


def feedback_to_dict(entity: FeedbackEntity) -> dict:
    return {
        "id": entity.id,
        "target_type": entity.target_type,
        "target_id": entity.target_id,
        "rating": entity.rating,
        "comment": entity.comment,
        "extra": entity.extra or {},
        "created_at": entity.created_at,
        "updated_at": entity.updated_at,
    }


def _get_feedback_or_404(session, feedback_id: str) -> FeedbackEntity:
    entity = session.get(FeedbackEntity, feedback_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return entity


@router.post("")
async def create_feedback(req: FeedbackRequest, request: Request) -> dict:
    with request.app.state.metadata_store.session() as session:
        entity = FeedbackEntity(id=str(uuid4()), **req.model_dump())
        session.add(entity)
        session.commit()
        return feedback_to_dict(entity)


@router.get("")
async def list_feedback(request: Request) -> dict:
    with request.app.state.metadata_store.session() as session:
        return {"items": [feedback_to_dict(item) for item in session.query(FeedbackEntity).all()]}


@router.get("/{feedback_id}")
async def get_feedback(feedback_id: str, request: Request) -> dict:
    with request.app.state.metadata_store.session() as session:
        return feedback_to_dict(_get_feedback_or_404(session, feedback_id))


@router.put("/{feedback_id}")
async def update_feedback(feedback_id: str, req: FeedbackUpdateRequest, request: Request) -> dict:
    with request.app.state.metadata_store.session() as session:
        entity = _get_feedback_or_404(session, feedback_id)
        for key, value in req.model_dump(exclude_unset=True).items():
            setattr(entity, key, value)
        session.commit()
        return feedback_to_dict(entity)


@router.delete("/{feedback_id}")
async def delete_feedback(feedback_id: str, request: Request) -> dict:
    with request.app.state.metadata_store.session() as session:
        entity = _get_feedback_or_404(session, feedback_id)
        session.delete(entity)
        session.commit()
        return {"deleted": True}
