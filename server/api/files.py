from fastapi import APIRouter, UploadFile, File
import uuid

from core.supabase import supabase

router = APIRouter(prefix="/files", tags=["files"])


# upload file
@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    file_path = f"uploads/{uuid.uuid4()}-{file.filename}"

    content = await file.read()

    res = supabase.storage.from_("files").upload(
        file_path,
        content,
        {"content-type": file.content_type},
    )

    if res.get("error"):
        return {"error": res["error"]["message"]}

    return {
        "path": file_path,
        "status": "uploaded"
    }


# list files
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


# delete file
@router.delete("/")
def delete_file(path: str):
    res = supabase.storage.from_("files").remove([path])

    if res.get("error"):
        return {"error": res["error"]["message"]}

    return {"status": "deleted"}
