from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from aurora_serve.files.workspace_service import WorkspaceFileService, infer_mime

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


class WorkspaceWriteRequest(BaseModel):
    name: str
    content: str
    encoding: Literal["utf8", "utf-8", "base64"] = "utf8"
    overwrite: bool = True


class WorkspaceRenameRequest(BaseModel):
    from_: str = Field(alias="from")
    to: str


def get_workspace_file_service() -> WorkspaceFileService:
    return WorkspaceFileService()


@router.get("/{workspace_id}/files")
async def list_workspace_files(
    workspace_id: str,
    service: WorkspaceFileService = Depends(get_workspace_file_service),
) -> dict:
    return {"files": service.list_files(workspace_id)}


@router.post("/{workspace_id}/files")
async def write_workspace_file(
    workspace_id: str,
    req: WorkspaceWriteRequest,
    service: WorkspaceFileService = Depends(get_workspace_file_service),
) -> dict:
    return {
        "file": service.write_file(
            workspace_id,
            req.name,
            req.content,
            encoding=req.encoding,
            overwrite=req.overwrite,
        )
    }


@router.post("/{workspace_id}/upload")
async def upload_workspace_files(
    workspace_id: str,
    base_dir: str = Form(""),
    files: list[UploadFile] = File(...),
    service: WorkspaceFileService = Depends(get_workspace_file_service),
) -> dict:
    return {
        "files": await service.upload_files(workspace_id, files, base_dir=base_dir),
        "failed": [],
    }


@router.post("/{workspace_id}/files/rename")
async def rename_workspace_file(
    workspace_id: str,
    req: WorkspaceRenameRequest,
    service: WorkspaceFileService = Depends(get_workspace_file_service),
) -> dict:
    return service.rename_file(workspace_id, req.from_, req.to)


@router.get("/{workspace_id}/raw/{file_path:path}")
async def read_workspace_raw_file(
    workspace_id: str,
    file_path: str,
    service: WorkspaceFileService = Depends(get_workspace_file_service),
) -> FileResponse:
    path = service.resolve_path(workspace_id, file_path)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(path), media_type=infer_mime(file_path))


@router.get("/{workspace_id}/archive")
async def archive_workspace_files(
    workspace_id: str,
    root: str = Query(""),
    service: WorkspaceFileService = Depends(get_workspace_file_service),
) -> Response:
    body, filename = service.build_archive(workspace_id, root)
    return Response(
        content=body,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/{workspace_id}/raw/{file_path:path}")
async def delete_workspace_raw_file(
    workspace_id: str,
    file_path: str,
    service: WorkspaceFileService = Depends(get_workspace_file_service),
) -> dict:
    service.delete_file(workspace_id, file_path)
    return {"ok": True}


@router.get("/{workspace_id}/files/{file_path:path}/preview")
async def preview_workspace_file(
    workspace_id: str,
    file_path: str,
    service: WorkspaceFileService = Depends(get_workspace_file_service),
) -> dict:
    meta = service.file_meta(workspace_id, file_path)
    return {
        "kind": meta["kind"],
        "title": meta["name"],
        "sections": [
            {
                "title": "Preview unavailable",
                "lines": ["Use Download or raw preview to inspect this file."],
            }
        ],
    }
