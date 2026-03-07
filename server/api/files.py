from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
import uuid
from sqlalchemy.orm import Session
import logging

from core.deps import get_db, get_storage_provider
from core.enums import FileStatus
import crud
from core.storage import StorageProvider
from core.database import Base

router = APIRouter(prefix="/files", tags=["files"])

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(module)s:%(lineno)d - %(levelname)s - %(message)s"
)
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
    logging.info(f"Starting file upload: {file.filename} with file_id: {file_id}")

    try:
        content = await file.read()
        logging.debug(f"File content read successfully: {len(content)} bytes")

        # Use the storage provider exclusively for file storage
        stored = storage_provider.upload_file(object_key, content)
        
        if not stored:
            logging.error(f"Failed to store file: {file_id}")
            raise HTTPException(status_code=500, detail="Failed to store file via storage provider")
        
        logging.info(f"File stored successfully in storage provider: {object_key}")

        presigned_url = storage_provider.generate_presigned_url(object_key)
        logging.debug(f"Generated presigned URL for file: {file_id}")

        crud.create_item(
            db=db,
            model_class=Base.classes.file_registry,
            item_data={
                "file_id": file_id,
                "object_key": object_key,
                "status": FileStatus.UPLOADED,
            },
        )
        logging.info(f"File registry entry created for file_id: {file_id}")

        logging.info(f"File upload completed successfully: {file_id}")
        return {
            "file_id": file_id,
            "object_key": object_key,
            "status": FileStatus.UPLOADED,
            "presigned_url": presigned_url
        }

    except Exception as e:
        logging.error(f"File upload failed for {file.filename}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"File upload failed: {e}")

@router.get("/")
def list_files(
    storage_provider: StorageProvider = Depends(get_storage_provider)
):
    """List files using the storage provider abstraction."""
    logging.info("Listing files using storage provider")
    return storage_provider.list_files()

@router.delete("/")
def delete_file(
    file_id: str,
    db: Session = Depends(get_db),
    storage_provider: StorageProvider = Depends(get_storage_provider)
):
    logging.info(f"Attempting to delete file: {file_id}")
    file_records = crud.get_items_by_field(
        db=db,
        model_class=Base.classes.file_registry,
        field_name="file_id",
        value=file_id,
    )

    if not file_records:
        logging.warning(f"File not found: {file_id}")
        raise HTTPException(status_code=404, detail="File not found")

    record = file_records[0]
    object_key = record.object_key
    
    # Delete from storage provider
    storage_provider.delete_file(object_key)
    logging.info(f"File deleted from storage provider: {object_key}")

    # Delete from database registry
    crud.delete_item_by_field(
        db=db,
        model_class=Base.classes.file_registry,
        field_name="file_id",
        value=file_id,
    )
    logging.info(f"File registry entry deleted for file_id: {file_id}")

    logging.info(f"File deleted successfully: {file_id}")
    return {"file_id": file_id, "status": FileStatus.DELETED}

@router.patch("/{file_id}")
def update_file_registry(
    file_id: str,
    update: FileUpdate,
    db: Session = Depends(get_db),
):
    update_data = update.dict(exclude_unset=True)
    logging.info(f"Updating file registry for {file_id} with data: {update_data}")
    if not update_data:
        logging.warning(f"No valid fields provided for updating file: {file_id}")
        raise HTTPException(status_code=400, detail="No fields provided to update")

    updated = crud.update_item_by_field(
        db=db,
        model_class=Base.classes.file_registry,
        field_name="file_id",
        value=file_id,
        update_data=update_data,
    )
    if not updated:
        logging.warning(f"File not found for update: {file_id}")
        raise HTTPException(status_code=404, detail="File not found")

    logging.info(f"File updated successfully: {file_id}")
    return {"file_id": file_id, "updated_fields": update_data}
