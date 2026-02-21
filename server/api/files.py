from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
import uuid
from sqlalchemy.orm import Session

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

    try:
        content = await file.read()

        # Use the storage provider exclusively for file storage
        stored = storage_provider.upload_file(object_key, content)
        
        if not stored:
            raise HTTPException(status_code=500, detail="Failed to store file via storage provider")

        presigned_url = storage_provider.generate_presigned_url(object_key)

        crud.create_item(
            db=db,
            model_class=Base.classes.file_registry,
            item_data={
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

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File upload failed: {e}")

@router.get("/")
def list_files(
    storage_provider: StorageProvider = Depends(get_storage_provider)
):
    """List files using the storage provider abstraction."""
    return storage_provider.list_files()

@router.delete("/")
def delete_file(
    file_id: str,
    db: Session = Depends(get_db),
    storage_provider: StorageProvider = Depends(get_storage_provider)
):
    file_records = crud.get_items_by_field(
        db=db,
        model_class=Base.classes.file_registry,
        field_name="file_id",
        value=file_id,
    )

    if not file_records:
        raise HTTPException(status_code=404, detail="File not found")

    record = file_records[0]
    object_key = record.object_key
    
    # Delete from storage provider
    storage_provider.delete_file(object_key)

    # Delete from database registry
    crud.delete_item_by_field(
        db=db,
        model_class=Base.classes.file_registry,
        field_name="file_id",
        value=file_id,
    )

    return {"file_id": file_id, "status": "deleted"}

@router.patch("/{file_id}")
def update_file_registry(
    file_id: str,
    update: FileUpdate,
    db: Session = Depends(get_db),
):
    update_data = update.dict(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided to update")

    updated = crud.update_item_by_field(
        db=db,
        model_class=Base.classes.file_registry,
        field_name="file_id",
        value=file_id,
        update_data=update_data,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="File not found")

    return {"file_id": file_id, "updated_fields": update_data}
