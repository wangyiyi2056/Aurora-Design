from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from aurora_serve.awel.service import FlowService
from aurora_serve.metadata import FlowEntity, FlowRunEntity

router = APIRouter(prefix="/awel", tags=["awel"])


class FlowCreate(BaseModel):
    name: str
    description: str = ""
    nodes: list[dict] = Field(default_factory=list)
    edges: list[dict] = Field(default_factory=list)
    variables: dict = Field(default_factory=dict)
    enabled: bool = True


class FlowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    nodes: list[dict] | None = None
    edges: list[dict] | None = None
    variables: dict | None = None
    enabled: bool | None = None


class FlowRunRequest(BaseModel):
    initial_input: object = None


def get_flow_service(request: Request) -> FlowService:
    return request.app.state.system_app.get_component("flow_service", FlowService)


def flow_to_dict(entity: FlowEntity) -> dict:
    return {
        "id": entity.id,
        "name": entity.name,
        "description": entity.description,
        "nodes": entity.nodes or [],
        "edges": entity.edges or [],
        "variables": entity.variables or {},
        "enabled": entity.enabled,
        "created_at": entity.created_at,
        "updated_at": entity.updated_at,
    }


def run_to_dict(entity: FlowRunEntity) -> dict:
    return {
        "id": entity.id,
        "flow_id": entity.flow_id,
        "status": entity.status,
        "input": entity.input,
        "output": entity.output,
        "error": entity.error,
        "created_at": entity.created_at,
        "updated_at": entity.updated_at,
    }


@router.get("/operators")
async def list_operators(service: FlowService = Depends(get_flow_service)) -> list[dict]:
    return service.operators()


@router.post("/run")
async def run_legacy_awel(
    req: FlowRunRequest,
    service: FlowService = Depends(get_flow_service),
) -> dict:
    return service.run_legacy(req.initial_input)


@router.get("/flows")
async def list_flows(service: FlowService = Depends(get_flow_service)) -> dict:
    return {"items": [flow_to_dict(item) for item in service.list()]}


@router.post("/flows")
async def create_flow(
    req: FlowCreate,
    service: FlowService = Depends(get_flow_service),
) -> dict:
    return flow_to_dict(service.create(**req.model_dump()))


@router.get("/flows/{flow_id}")
async def get_flow(
    flow_id: str,
    service: FlowService = Depends(get_flow_service),
) -> dict:
    try:
        return flow_to_dict(service.get(flow_id))
    except KeyError:
        raise HTTPException(status_code=404, detail="Flow not found")


@router.put("/flows/{flow_id}")
async def update_flow(
    flow_id: str,
    req: FlowUpdate,
    service: FlowService = Depends(get_flow_service),
) -> dict:
    try:
        return flow_to_dict(service.update(flow_id, **req.model_dump(exclude_unset=True)))
    except KeyError:
        raise HTTPException(status_code=404, detail="Flow not found")


@router.delete("/flows/{flow_id}")
async def delete_flow(
    flow_id: str,
    service: FlowService = Depends(get_flow_service),
) -> dict:
    return {"success": service.delete(flow_id)}


@router.post("/flows/{flow_id}/run")
async def run_flow(
    flow_id: str,
    req: FlowRunRequest,
    service: FlowService = Depends(get_flow_service),
) -> dict:
    try:
        run = service.run(flow_id, req.initial_input)
    except KeyError:
        raise HTTPException(status_code=404, detail="Flow not found")
    return run_to_dict(run)


@router.get("/flows/{flow_id}/runs")
async def list_flow_runs(
    flow_id: str,
    service: FlowService = Depends(get_flow_service),
) -> dict:
    return {"items": [run_to_dict(item) for item in service.list_runs(flow_id)]}


@router.get("/runs/{run_id}")
async def get_flow_run(
    run_id: str,
    service: FlowService = Depends(get_flow_service),
) -> dict:
    try:
        return run_to_dict(service.get_run(run_id))
    except KeyError:
        raise HTTPException(status_code=404, detail="Flow run not found")
