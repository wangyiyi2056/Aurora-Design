from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel

from aurora_serve.design_systems.preview import render_design_system_preview, render_design_system_showcase
from aurora_serve.design_systems.service import DesignSystemService

router = APIRouter(prefix="/design-systems", tags=["design-systems"])


class DesignSystemInput(BaseModel):
    id: str | None = None
    title: str | None = None
    name: str | None = None
    summary: str | None = None
    category: str | None = None
    surface: str | None = None
    status: str | None = None
    body: str | None = None


class DesignSystemRevisionInput(BaseModel):
    feedback: str
    baseBody: str | None = None
    proposedBody: str | None = None
    sectionTitle: str | None = None


class DesignSystemRevisionStatusInput(BaseModel):
    status: str


def get_design_system_service(request: Request) -> DesignSystemService:
    return request.app.state.design_system_service


@router.get("")
def list_design_systems(service: DesignSystemService = Depends(get_design_system_service)):
    systems = [system.to_dict(include_body=False) for system in service.list_systems()]
    return {"designSystems": systems, "total": len(systems)}


@router.post("", status_code=201)
def create_design_system(input_data: DesignSystemInput, service: DesignSystemService = Depends(get_design_system_service)):
    try:
        system = service.create_system(input_data.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return system.to_dict(include_body=True)


@router.get("/{system_id}")
def get_design_system(system_id: str, service: DesignSystemService = Depends(get_design_system_service)):
    system = service.get_system(system_id)
    if system is None:
        raise HTTPException(status_code=404, detail="Design system not found")
    return system.to_dict(include_body=True, files=service.list_files(system_id))


@router.patch("/{system_id}")
def update_design_system(system_id: str, input_data: DesignSystemInput, service: DesignSystemService = Depends(get_design_system_service)):
    try:
        system = service.update_system(system_id, input_data.model_dump(exclude_none=True))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if system is None:
        raise HTTPException(status_code=404, detail="Design system not found")
    return system.to_dict(include_body=True)


@router.post("/{system_id}/toggle")
def toggle_design_system(system_id: str, service: DesignSystemService = Depends(get_design_system_service)):
    system = service.toggle_system(system_id)
    if system is None:
        raise HTTPException(status_code=404, detail="Design system not found")
    return system.to_dict(include_body=False)


@router.delete("/{system_id}", status_code=204)
def delete_design_system(system_id: str, service: DesignSystemService = Depends(get_design_system_service)):
    try:
        ok = service.delete_system(system_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if not ok:
        raise HTTPException(status_code=404, detail="Design system not found")
    return Response(status_code=204)


@router.get("/{system_id}/files")
def list_design_system_files(system_id: str, service: DesignSystemService = Depends(get_design_system_service)):
    if service.get_system(system_id) is None:
        raise HTTPException(status_code=404, detail="Design system not found")
    return {"files": service.list_files(system_id)}


@router.get("/{system_id}/file")
def read_design_system_file(
    system_id: str,
    path: str = Query(...),
    service: DesignSystemService = Depends(get_design_system_service),
):
    file = service.read_file(system_id, path)
    if file is None:
        raise HTTPException(status_code=404, detail="Design system file not found")
    return {"file": file}


@router.get("/{system_id}/preview")
def preview_design_system(system_id: str, service: DesignSystemService = Depends(get_design_system_service)):
    system = service.get_system(system_id)
    if system is None:
        raise HTTPException(status_code=404, detail="Design system not found")
    return Response(render_design_system_preview(system_id, system.body), media_type="text/html")


@router.get("/{system_id}/showcase")
def showcase_design_system(system_id: str, service: DesignSystemService = Depends(get_design_system_service)):
    system = service.get_system(system_id)
    if system is None:
        raise HTTPException(status_code=404, detail="Design system not found")
    return Response(render_design_system_showcase(system_id, system.body), media_type="text/html")


@router.post("/{system_id}/revisions", status_code=201)
def create_design_system_revision(
    system_id: str,
    input_data: DesignSystemRevisionInput,
    service: DesignSystemService = Depends(get_design_system_service),
):
    revision = service.create_revision(system_id, input_data.model_dump())
    if revision is None:
        raise HTTPException(status_code=404, detail="Editable design system not found")
    return {"revision": revision}


@router.get("/{system_id}/revisions")
def list_design_system_revisions(system_id: str, service: DesignSystemService = Depends(get_design_system_service)):
    revisions = service.list_revisions(system_id)
    if revisions is None:
        raise HTTPException(status_code=404, detail="Editable design system not found")
    return {"revisions": revisions}


@router.patch("/{system_id}/revisions/{revision_id}")
def update_design_system_revision(
    system_id: str,
    revision_id: str,
    input_data: DesignSystemRevisionStatusInput,
    service: DesignSystemService = Depends(get_design_system_service),
):
    if input_data.status not in {"accepted", "rejected"}:
        raise HTTPException(status_code=400, detail="status must be accepted or rejected")
    revision = service.update_revision_status(system_id, revision_id, input_data.status)
    if revision is None:
        raise HTTPException(status_code=404, detail="Design system revision not found")
    return {"revision": revision}
