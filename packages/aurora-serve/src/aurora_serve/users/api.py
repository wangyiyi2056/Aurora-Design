from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from aurora_serve.metadata import UserEntity

router = APIRouter(prefix="/users", tags=["users"])


class UserRequest(BaseModel):
    username: str
    display_name: str = ""
    role: str = "admin"
    enabled: bool = True


class UserUpdateRequest(BaseModel):
    username: str | None = None
    display_name: str | None = None
    role: str | None = None
    enabled: bool | None = None


def user_to_dict(entity: UserEntity) -> dict:
    return {
        "id": entity.id,
        "username": entity.username,
        "display_name": entity.display_name,
        "role": entity.role,
        "enabled": entity.enabled,
        "created_at": entity.created_at,
        "updated_at": entity.updated_at,
    }


def _get_user_or_404(session, user_id: str) -> UserEntity:
    entity = session.get(UserEntity, user_id)
    if not entity:
        raise HTTPException(status_code=404, detail="User not found")
    return entity


@router.post("")
async def create_user(req: UserRequest, request: Request) -> dict:
    with request.app.state.metadata_store.session() as session:
        entity = UserEntity(id=str(uuid4()), **req.model_dump())
        session.add(entity)
        session.commit()
        return user_to_dict(entity)


@router.get("")
async def list_users(request: Request) -> dict:
    with request.app.state.metadata_store.session() as session:
        return {"items": [user_to_dict(item) for item in session.query(UserEntity).all()]}


@router.get("/{user_id}")
async def get_user(user_id: str, request: Request) -> dict:
    with request.app.state.metadata_store.session() as session:
        return user_to_dict(_get_user_or_404(session, user_id))


@router.put("/{user_id}")
async def update_user(user_id: str, req: UserUpdateRequest, request: Request) -> dict:
    with request.app.state.metadata_store.session() as session:
        entity = _get_user_or_404(session, user_id)
        for key, value in req.model_dump(exclude_unset=True).items():
            setattr(entity, key, value)
        session.commit()
        return user_to_dict(entity)


@router.delete("/{user_id}")
async def delete_user(user_id: str, request: Request) -> dict:
    with request.app.state.metadata_store.session() as session:
        entity = _get_user_or_404(session, user_id)
        session.delete(entity)
        session.commit()
        return {"deleted": True}
