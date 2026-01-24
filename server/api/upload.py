from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from core.deps import get_fake_s3, get_db
from core.database import Base
from FakeS3.fakeS3 import FakeS3
from sqlalchemy.orm import Session
import uuid

router = APIRouter()

@router.post("/api/files/upload")
async def upload_file(
    file: UploadFile = File(...), 
    fake_s3: FakeS3 = Depends(get_fake_s3),
    db: Session = Depends(get_db)
):
    try:
        file_id = uuid.uuid4()
        object_key = f"uploads/{file_id}/{file.filename}"
        FileUploads = Base.classes.get("file_registry")
        if not FileUploads:
            raise HTTPException(status_code=500, detail="Configuration error: 'file_registry' table not found.")
        
        new_record = FileUploads(
            file_id=file_id,
            object_key=object_key,
            status="UPLOADED"
        )
        db.add(new_record)
        db.commit()


        presigned_url = fake_s3.generatePresignedURL()
        file_content = await file.read()
        stored = fake_s3.storeFile(presigned_url, file_content)
        if not stored:
            raise HTTPException(status_code=500, detail="Failed to store file.")
        return {"presigned_url": presigned_url, "file_id": str(file_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File upload failed: {e}")
    
