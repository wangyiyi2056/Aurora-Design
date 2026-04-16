import os
import uuid
from pathlib import Path

from fastapi import APIRouter, UploadFile, File

router = APIRouter(prefix="/files", tags=["files"])

UPLOAD_DIR = Path("uploads")


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)) -> dict:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ext = Path(file.filename or "").suffix or ".bin"
    file_name = f"{uuid.uuid4().hex}{ext}"
    file_path = UPLOAD_DIR / file_name

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    return {
        "file_name": file.filename or file_name,
        "file_path": str(file_path),
    }
