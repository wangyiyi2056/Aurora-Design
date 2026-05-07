from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse

from chatbi_serve.files.service import FileService
from chatbi_serve.metadata import FileEntity

router = APIRouter(prefix="/files", tags=["files"])


def get_file_service(request: Request) -> FileService:
    return request.app.state.system_app.get_component("file_service", FileService)


def file_to_dict(entity: FileEntity) -> dict:
    return {
        "file_id": entity.id,
        "file_name": entity.file_name,
        "file_path": entity.file_path,
        "content_type": entity.content_type,
        "size": entity.size,
        "purpose": entity.purpose,
        "sha256": entity.sha256,
        "created_at": entity.created_at,
        "updated_at": entity.updated_at,
    }

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    purpose: str = "general",
    service: FileService = Depends(get_file_service),
) -> dict:
    return file_to_dict(await service.upload(file, purpose=purpose))


@router.get("")
async def list_files(service: FileService = Depends(get_file_service)) -> dict:
    return {"items": [file_to_dict(entity) for entity in service.list()]}


@router.get("/{file_id}")
async def get_file(file_id: str, service: FileService = Depends(get_file_service)) -> dict:
    try:
        return file_to_dict(service.get(file_id))
    except KeyError:
        raise HTTPException(status_code=404, detail="File not found")


@router.get("/{file_id}/download")
async def download_file(
    file_id: str, service: FileService = Depends(get_file_service)
) -> FileResponse:
    try:
        entity = service.get(file_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        entity.file_path,
        media_type=entity.content_type,
        filename=entity.file_name,
    )


@router.delete("/{file_id}")
async def delete_file(file_id: str, service: FileService = Depends(get_file_service)) -> dict:
    return {"success": service.delete(file_id)}
