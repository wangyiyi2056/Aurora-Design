from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response
from pydantic import BaseModel, Field

from aurora_serve.files.preview_service import get_preview_service
from aurora_serve.files.workspace_service import WorkspaceFileService, infer_mime, infer_kind

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
    """Return file metadata and preview availability."""
    meta = service.file_meta(workspace_id, file_path)
    preview_svc = get_preview_service()
    path = service.resolve_path(workspace_id, file_path)
    kind = meta["kind"]

    preview_available = {
        "document": preview_svc.is_soffice_available(),
        "presentation": preview_svc.is_soffice_available(),
        "spreadsheet": True,  # Always available via ExcelReader
    }

    metadata: dict = {}
    if kind == "spreadsheet":
        try:
            from aurora_serve.excel.reader import ExcelReader
            with ExcelReader(str(path)) as reader:
                col_names, col_data = reader.get_columns()
                columns = [{"name": r[0], "type": r[1]} for r in col_data]
                count_sql = f"SELECT COUNT(*) FROM {reader.temp_table}"
                _, count_result = reader.run_sql(count_sql)
                total_rows = count_result[0][0] if count_result else 0
                metadata["columns"] = columns
                metadata["totalRows"] = total_rows
        except Exception:
            pass

    return {
        "kind": kind,
        "title": meta["name"],
        "previewAvailable": preview_available.get(kind, False),
        "metadata": metadata,
        "sections": [
            {
                "title": "File Info",
                "lines": [f"Type: {kind}", f"Size: {meta['size']} bytes"],
            }
        ],
    }


@router.get("/{workspace_id}/files/{file_path:path}/preview/pdf")
async def preview_file_pdf(
    workspace_id: str,
    file_path: str,
    service: WorkspaceFileService = Depends(get_workspace_file_service),
) -> Response:
    """Return PDF preview for Word/PowerPoint documents."""
    meta = service.file_meta(workspace_id, file_path)
    kind = meta["kind"]

    if kind not in {"document", "presentation"}:
        raise HTTPException(
            status_code=400,
            detail="PDF preview only available for documents and presentations",
        )

    preview_svc = get_preview_service()
    path = service.resolve_path(workspace_id, file_path)

    if kind == "document":
        result = preview_svc.preview_document(path)
    else:
        result = preview_svc.preview_presentation(path)

    if result.format != "pdf":
        raise HTTPException(
            status_code=503,
            detail="LibreOffice not available for PDF conversion. Please download the file to view.",
        )

    filename = path.stem + ".pdf"
    return Response(
        content=result.content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.get("/{workspace_id}/files/{file_path:path}/preview/html")
async def preview_file_html(
    workspace_id: str,
    file_path: str,
    service: WorkspaceFileService = Depends(get_workspace_file_service),
) -> HTMLResponse:
    """Return HTML preview for Excel spreadsheets."""
    meta = service.file_meta(workspace_id, file_path)
    kind = meta["kind"]

    if kind != "spreadsheet":
        raise HTTPException(
            status_code=400,
            detail="HTML preview only available for spreadsheets",
        )

    preview_svc = get_preview_service()
    path = service.resolve_path(workspace_id, file_path)
    result = preview_svc.preview_excel(path)

    return HTMLResponse(content=result.content)
