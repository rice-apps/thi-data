from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict
import uuid
from pathlib import Path

from sqlalchemy.orm import Session
import logging

from core.deps import get_db, get_storage_provider, get_file_registry_repo
from core.enums import FileStatus
from crud.base import BaseRepository, model_to_dict
from core.storage import StorageProvider
from services.etl_processor import process_file as run_etl

router = APIRouter(tags=["files"])

logger = logging.getLogger(__name__)


class FileUpdate(BaseModel):
    status: Optional[str] = None
    object_key: Optional[str] = None
    file_schema: Optional[dict] = None

@router.post("/api/files/upload")
async def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    storage_provider: StorageProvider = Depends(get_storage_provider),
    repo: BaseRepository = Depends(get_file_registry_repo),
):
    file_id = str(uuid.uuid4())
    object_key = f"uploads/{file_id}-{file.filename}"
    content = await file.read()
    logger.info("Starting upload: %s  file_id=%s", file.filename, file_id)

    try:
        # Upload via the configured StorageProvider (S3/SeaweedFS or FakeS3)
        uploaded = storage_provider.upload_file(object_key, content)
        if not uploaded:
            raise RuntimeError("StorageProvider.upload_file returned False")

        repo.create(db=db, obj_in={
                "file_id": file_id,
                "object_key": object_key,
                "status": FileStatus.UPLOADED,
            },
        )

        logger.info("Upload complete: file_id=%s", file_id)
        return {
            "file_id": file_id,
            "object_key": object_key,
            "status": "UPLOADED",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Upload failed for %s: %s", file.filename, e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"File upload failed: {e}")


@router.get("/api/files")
def list_files(
    storage_provider: StorageProvider = Depends(get_storage_provider),
):
    """List files from the configured storage provider."""
    return storage_provider.list_files(prefix="uploads/")

@router.delete("/api/files")
def delete_file(
    file_id: str,
    db: Session = Depends(get_db),
    storage_provider: StorageProvider = Depends(get_storage_provider),
    repo: BaseRepository = Depends(get_file_registry_repo),
):
    file_records = repo.get_by_field(
        db=db,
        field_name="file_id",
        value=file_id,
    )
    if not file_records:
        raise HTTPException(status_code=404, detail="File not found")

    record = file_records[0]
    object_key = record.object_key

    # Remove from storage provider
    storage_provider.delete_file(object_key)

    repo.delete_by_field(
        db=db,
        field_name="file_id",
        value=file_id,
    )

    logger.info("Deleted file_id=%s", file_id)
    return {"file_id": file_id, "status": FileStatus.DELETED}

@router.patch("/api/files/{file_id}")
def update_file_registry(
    file_id: str,
    update: FileUpdate,
    db: Session = Depends(get_db),
    repo: BaseRepository = Depends(get_file_registry_repo),
):
    update_data = update.dict(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided to update")

    updated_count = repo.update_by_field(
        db=db,
        search_field="file_id",
        search_value=file_id,
        update_data=update_data,
    )
    if not updated_count:
        raise HTTPException(status_code=404, detail="File not found")

    return {"file_id": file_id, "updated_fields": update_data}

class ProcessFileRequest(BaseModel):
    proposed_schema: Dict[str, str]


@router.post("/api/files/{file_id}/process")
def process_file(
    file_id: str,
    body: ProcessFileRequest,
    db: Session = Depends(get_db),
    storage_provider: StorageProvider = Depends(get_storage_provider),
    repo: BaseRepository = Depends(get_file_registry_repo),
):
    """Synchronous ETL: validate + split + load using the user-confirmed schema."""
    file_records = repo.get_by_field(
        db=db,
        field_name="file_id",
        value=file_id,
    )
    if not file_records:
        raise HTTPException(status_code=404, detail="File not found in registry")

    record = file_records[0]
    file_path = storage_provider.get_file_path(record.object_key)
    if not file_path:
        raise HTTPException(status_code=404, detail="File not found in storage")

    try:
        repo.update_by_field(
            db=db,
            search_field="file_id",
            search_value=file_id,
            update_data={"status": FileStatus.PROCESSING},
        )

        run_etl(str(file_path), body.proposed_schema)

        repo.update_by_field(
            db=db,
            search_field="file_id",
            search_value=file_id,
            update_data={"status": FileStatus.SUCCESS},
        )
        return {"file_id": file_id, "status": FileStatus.SUCCESS}
    except Exception as e:
        repo.update_by_field(
            db=db,
            search_field="file_id",
            search_value=file_id,
            update_data={"status": FileStatus.FAILED},
        )
        raise HTTPException(status_code=500, detail=f"Processing failed: {e}")
