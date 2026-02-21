from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
import uuid
from sqlalchemy.orm import Session

from core.supabase import supabase
from core.deps import get_db, get_storage_provider
import crud
from core.storage import StorageProvider
from core.database import Base

router = APIRouter(prefix="/files", tags=["files"])

class FileUpdate(BaseModel):
    status: Optional[str] = None
    object_key: Optional[str] = None
    file_schema: Optional[dict] = None

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    storage_provider: StorageProvider = Depends(get_storage_provider)
):
    file_id = str(uuid.uuid4())
    object_key = f"uploads/{file_id}-{file.filename}"

    content = await file.read()

    res = supabase.storage.from_("files").upload(
        object_key,
        content,
        {"content-type": file.content_type},
    )

    if res.get("error"):
        presigned_url = storage_provider.generatePresignedURL()
        stored = storage_provider.storeFile(presigned_url, content)
        if not stored:
            raise HTTPException(status_code=500, detail="Failed to store file")
    else:
        presigned_url = None

    crud.create_item(
        db=db,
        model_class=Base.classes.file_registry,
        data={
            "file_id": file_id,
            "object_key": object_key,
            "status": "UPLOADED",
        },
    )

    return {
        "file_id": file_id,
        "object_key": object_key,
        "status": "UPLOADED",
        "presigned_url": presigned_url
    }