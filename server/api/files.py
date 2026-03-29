from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Optional, Dict
import re
import uuid

from sqlalchemy.orm import Session
import logging

from core.deps import get_db, get_storage_provider, get_file_registry_repo
from core.enums import FileStatus
from crud.base import BaseRepository
from core.storage import StorageProvider
from celery_task import process_patient_file

router = APIRouter(tags=["files"])

logger = logging.getLogger(__name__)


def derive_table_name(filename: str) -> str:
    """Derive a SQL-safe table name from a filename (without extension)."""
    stem = filename.rsplit(".", 1)[0] if "." in filename else filename
    table_name = re.sub(r"[^a-zA-Z0-9_]", "_", stem).strip("_").lower()
    if not table_name or table_name[0].isdigit():
        table_name = f"t_{table_name}"
    return table_name


class FileUpdate(BaseModel):
    status: Optional[str] = None
    object_key: Optional[str] = None
    file_schema: Optional[dict] = None

@router.get("/api/files/check-duplicate")
def check_duplicate(
    table_name: str,
    db: Session = Depends(get_db),
    repo: BaseRepository = Depends(get_file_registry_repo),
):
    """Check if a table name is already in use by an active file."""
    existing = repo.get_by_field(db=db, field_name="target_table_name", value=table_name)
    terminal_statuses = {FileStatus.DELETED, FileStatus.FAILED}
    active = [r for r in existing if r.status not in terminal_statuses]
    return {"table_name": table_name, "exists": len(active) > 0}


@router.post("/api/files/upload")
async def upload_file(
    file: UploadFile = File(...),
    table_name: Optional[str] = None,
    x_user_name: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
    storage_provider: StorageProvider = Depends(get_storage_provider),
    repo: BaseRepository = Depends(get_file_registry_repo),
):
    file_id = str(uuid.uuid4())
    object_key = f"uploads/{file_id}-{file.filename}"
    content = await file.read()
    logger.info("Starting upload: %s  file_id=%s", file.filename, file_id)

    table_name = table_name or derive_table_name(file.filename)

    try:
        # Upload via the configured StorageProvider (S3/SeaweedFS or FakeS3)
        uploaded = storage_provider.upload_file(object_key, content)
        if not uploaded:
            raise RuntimeError("StorageProvider.upload_file returned False")

        repo.create(db=db, obj_in={
                "file_id": file_id,
                "object_key": object_key,
                "status": FileStatus.UPLOADED,
                "target_table_name": table_name,
                "uploaded_by": x_user_name,
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
        raise HTTPException(status_code=500, detail="File upload failed. Please try again.")


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
    update_data = update.model_dump(exclude_unset=True)
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
    repo: BaseRepository = Depends(get_file_registry_repo),
):
    """Queue async ETL via Celery using the user-confirmed schema."""
    file_records = repo.get_by_field(
        db=db,
        field_name="file_id",
        value=file_id,
    )
    if not file_records:
        raise HTTPException(status_code=404, detail="File not found in registry")

    task = process_patient_file.delay(file_id, body.proposed_schema)
    return {"file_id": file_id, "task_id": task.id, "status": "PROCESSING"}
