from fastapi import APIRouter, HTTPException, Depends
from core.deps import get_db, get_storage_provider, get_file_registry_repo
from core.storage import StorageProvider
from crud.base import BaseRepository
from services.file_schema_service import FileSchemaService
from sqlalchemy.orm import Session

router = APIRouter()


@router.post("/api/validate_schema")
def validate_schema(
    file_id: str,
    db: Session = Depends(get_db),
    storage_service: StorageProvider = Depends(get_storage_provider),
    repo: BaseRepository = Depends(get_file_registry_repo),
):
    try:
        return FileSchemaService(db, storage_service, repo).infer_and_persist(file_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
