from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from chatbi_serve.metadata import EvaluationDatasetEntity, EvaluationTaskEntity

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


class DatasetRequest(BaseModel):
    name: str
    description: str = ""
    data: object = None


class DatasetUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    data: object = None


class TaskRequest(BaseModel):
    name: str
    model: str = ""
    dataset_id: str
    status: str = "pending"
    result: object = None


class TaskUpdateRequest(BaseModel):
    name: str | None = None
    model: str | None = None
    dataset_id: str | None = None
    status: str | None = None
    result: object = None


def _store(request: Request):
    return request.app.state.metadata_store


def dataset_to_dict(entity: EvaluationDatasetEntity) -> dict:
    return {
        "id": entity.id,
        "name": entity.name,
        "description": entity.description,
        "data": entity.data,
        "created_at": entity.created_at,
        "updated_at": entity.updated_at,
    }


def task_to_dict(entity: EvaluationTaskEntity) -> dict:
    return {
        "id": entity.id,
        "name": entity.name,
        "model": entity.model,
        "dataset_id": entity.dataset_id,
        "status": entity.status,
        "result": entity.result,
        "created_at": entity.created_at,
        "updated_at": entity.updated_at,
    }


def _get_or_404(session, model, item_id: str):
    entity = session.get(model, item_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Resource not found")
    return entity


@router.post("/datasets")
async def create_dataset(req: DatasetRequest, request: Request) -> dict:
    with _store(request).session() as session:
        entity = EvaluationDatasetEntity(id=str(uuid4()), **req.model_dump())
        session.add(entity)
        session.commit()
        return dataset_to_dict(entity)


@router.get("/datasets")
async def list_datasets(request: Request) -> dict:
    with _store(request).session() as session:
        return {"items": [dataset_to_dict(item) for item in session.query(EvaluationDatasetEntity).all()]}


@router.get("/datasets/{dataset_id}")
async def get_dataset(dataset_id: str, request: Request) -> dict:
    with _store(request).session() as session:
        return dataset_to_dict(_get_or_404(session, EvaluationDatasetEntity, dataset_id))


@router.put("/datasets/{dataset_id}")
async def update_dataset(dataset_id: str, req: DatasetUpdateRequest, request: Request) -> dict:
    with _store(request).session() as session:
        entity = _get_or_404(session, EvaluationDatasetEntity, dataset_id)
        for key, value in req.model_dump(exclude_unset=True).items():
            setattr(entity, key, value)
        session.commit()
        return dataset_to_dict(entity)


@router.delete("/datasets/{dataset_id}")
async def delete_dataset(dataset_id: str, request: Request) -> dict:
    with _store(request).session() as session:
        entity = _get_or_404(session, EvaluationDatasetEntity, dataset_id)
        session.delete(entity)
        session.commit()
        return {"deleted": True}


@router.post("/tasks")
async def create_task(req: TaskRequest, request: Request) -> dict:
    with _store(request).session() as session:
        entity = EvaluationTaskEntity(id=str(uuid4()), **req.model_dump())
        session.add(entity)
        session.commit()
        return task_to_dict(entity)


@router.get("/tasks")
async def list_tasks(request: Request) -> dict:
    with _store(request).session() as session:
        return {"items": [task_to_dict(item) for item in session.query(EvaluationTaskEntity).all()]}


@router.get("/tasks/{task_id}")
async def get_task(task_id: str, request: Request) -> dict:
    with _store(request).session() as session:
        return task_to_dict(_get_or_404(session, EvaluationTaskEntity, task_id))


@router.put("/tasks/{task_id}")
async def update_task(task_id: str, req: TaskUpdateRequest, request: Request) -> dict:
    with _store(request).session() as session:
        entity = _get_or_404(session, EvaluationTaskEntity, task_id)
        for key, value in req.model_dump(exclude_unset=True).items():
            setattr(entity, key, value)
        session.commit()
        return task_to_dict(entity)


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str, request: Request) -> dict:
    with _store(request).session() as session:
        entity = _get_or_404(session, EvaluationTaskEntity, task_id)
        session.delete(entity)
        session.commit()
        return {"deleted": True}
