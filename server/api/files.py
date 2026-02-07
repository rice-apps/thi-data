from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
import uuid

from sqlalchemy.orm import Session

from core.supabase import supabase
from core.deps import get_db
import crud

router = APIRouter(prefix="/files", tags=["files"])
@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
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
        raise HTTPException(status_code=500, detail=res["error"]["message"])

    # Insert metadata into file_registry
    crud.create_item(
        db=db,
        model_class=db.Base.classes.file_registry,
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
    }
@router.get("/")
def list_files():
    res = (
        supabase
        .table("storage.objects")
        .select("id, name, bucket_id, created_at, metadata")
        .eq("bucket_id", "files")
        .execute()
    )

    return res.data

@router.delete("/")
def delete_file(
    file_id: str,
    db: Session = Depends(get_db),
):
    # Look up file in registry
    file_records = crud.get_items_by_field(
        db=db,
        model_class=db.Base.classes.file_registry,
        field="file_id",
        value=file_id,
    )

    if not file_records:
        raise HTTPException(status_code=404, detail="File not found")

    record = file_records[0]
    object_key = record.object_key

    # Delete from Supabase storage
    res = supabase.storage.from_("files").remove([object_key])

    if res.get("error"):
        raise HTTPException(status_code=500, detail=res["error"]["message"])

    # Delete from file_registry
    crud.delete_item_by_field(
        db=db,
        model_class=db.Base.classes.file_registry,
        field="file_id",
        value=file_id,
    )

    return {
        "file_id": file_id,
        "status": "deleted",
    }

class FileUpdate(BaseModel):
    status: Optional[str] = None
    object_key: Optional[str] = None
    file_schema: Optional[dict] = None

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
        model_class=db.Base.classes.file_registry,
        field="file_id",
        value=file_id,
        update_data=update_data,
    )

    if not updated:
        raise HTTPException(status_code=404, detail="File not found")

    return {
        "file_id": file_id,
        "updated_fields": update_data,
    }