from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from core.supabase import get_supabase_client
from core.deps import get_db, get_storage_provider
import crud
from core.storage import StorageProvider
from core.database import Base
from services.etl_processor import process_file_task

router = APIRouter(tags=["files"])

class FileUpdate(BaseModel):
    status: Optional[str] = None
    object_key: Optional[str] = None
    file_schema: Optional[dict] = None

@router.post("/api/files/upload")
async def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    storage_provider: StorageProvider = Depends(get_storage_provider)
):
    try:
        file_id = str(uuid.uuid4())
        object_key = f"uploads/{file_id}-{file.filename}"
        content = await file.read()

        presigned_url: Optional[str] = None
        uploaded_to_supabase = False

        try:
            client = get_supabase_client()
            client.storage.from_("files").upload(
                object_key,
                content,
                {"content-type": file.content_type or "application/octet-stream"},
            )
            uploaded_to_supabase = True
        except Exception:
            uploaded_to_supabase = False

        if not uploaded_to_supabase:
            # Local-dev fallback so validate_schema can read from disk.
            local_path = Path.cwd() / object_key
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_bytes(content)
            presigned_url = storage_provider.generate_presigned_url()

        file_registry_model = Base.classes.get("file_registry")
        if not file_registry_model:
            raise HTTPException(status_code=500, detail="file_registry table not reflected")

        crud.create_item(
            db=db,
            model_class=file_registry_model,
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
            "presigned_url": presigned_url,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File upload failed: {e}")


@router.get("/api/files")
def list_files():
    res = (
        get_supabase_client()
        .table("storage.objects")
        .select("id, name, bucket_id, created_at, metadata")
        .eq("bucket_id", "files")
        .execute()
    )
    return res.data

@router.delete("/api/files")
def delete_file(
    file_id: str,
    db: Session = Depends(get_db),
):
    file_registry_model = Base.classes.get("file_registry")
    if not file_registry_model:
        raise HTTPException(status_code=500, detail="file_registry table not reflected")

    file_records = crud.get_items_by_field(
        db=db,
        model_class=file_registry_model,
        field_name="file_id",
        value=file_id,
    )

    if not file_records:
        raise HTTPException(status_code=404, detail="File not found")

    record = file_records[0]
    object_key = record.object_key

    deleted_from_storage = False
    try:
        res = get_supabase_client().storage.from_("files").remove([object_key])
        if res.get("error"):
            raise RuntimeError(res["error"]["message"])
        deleted_from_storage = True
    except Exception:
        deleted_from_storage = False

    if not deleted_from_storage:
        # Local-dev fallback: best-effort remove from disk.
        try:
            local_path = Path.cwd() / object_key
            if local_path.exists():
                local_path.unlink()
        except Exception:
            pass

    crud.delete_item(db, file_registry_model, record.file_id)

    return {"file_id": file_id, "status": "deleted"}

@router.patch("/api/files/{file_id}")
def update_file_registry(
    file_id: str,
    update: FileUpdate,
    db: Session = Depends(get_db),
):
    file_registry_model = Base.classes.get("file_registry")
    if not file_registry_model:
        raise HTTPException(status_code=500, detail="file_registry table not reflected")

    update_data = update.dict(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided to update")

    file_records = crud.get_items_by_field(
        db=db,
        model_class=file_registry_model,
        field_name="file_id",
        value=file_id,
    )
    if not file_records:
        raise HTTPException(status_code=404, detail="File not found")

    record = file_records[0]
    for key, value in update_data.items():
        setattr(record, key, value)

    crud.update_item(db, file_registry_model, record.file_id, record)

    return {"file_id": file_id, "updated_fields": update_data}


class ProcessFileRequest(BaseModel):
    proposed_schema: Dict[str, str]


@router.post("/api/files/{file_id}/process")
def process_file(
    file_id: str,
    body: ProcessFileRequest,
    db: Session = Depends(get_db),
    storage_provider: StorageProvider = Depends(get_storage_provider),
):
    """
    Synchronous ETL: validate + split + load using the user-confirmed schema.
    """
    file_registry_model = Base.classes.get("file_registry")
    if not file_registry_model:
        raise HTTPException(status_code=500, detail="file_registry table not reflected")

    file_records = crud.get_items_by_field(
        db=db,
        model_class=file_registry_model,
        field_name="file_id",
        value=file_id,
    )
    if not file_records:
        raise HTTPException(status_code=404, detail="File not found in registry")

    record = file_records[0]
    object_key = record.object_key

    file_path = storage_provider.get_file_path(object_key)
    if not file_path:
        raise HTTPException(status_code=404, detail="File not found in storage")

    try:
        record.status = "PROCESSING"
        crud.update_item(db, file_registry_model, record.file_id, record)

        process_file_task(str(file_path), body.proposed_schema)

        record.status = "SUCCESS"
        crud.update_item(db, file_registry_model, record.file_id, record)
    except Exception as e:
        record.status = "FAILURE"
        crud.update_item(db, file_registry_model, record.file_id, record)
        raise HTTPException(status_code=500, detail=f"Processing failed: {e}")

    return {"file_id": file_id, "status": "SUCCESS"}
