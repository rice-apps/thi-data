from fastapi import APIRouter, HTTPException, Depends
import crud
from core.deps import get_db, get_storage_provider
from core.database import Base
from core.storage import StorageProvider
from sqlalchemy.orm import Session

router = APIRouter()

@router.post("/api/validate_schema")
def validate_schema(file_id: str, db: Session = Depends(get_db), storage_service: StorageProvider = Depends(get_storage_provider)):
    try:
        file_record = crud.get_items_by_field(db = db,
                                              model_class=Base.classes.get("file_registry"),
                                              field_name = "file_id",
                                              value=file_id) 
        if not file_record:
            raise HTTPException(status_code = 404, detail="File ID not found in registry")
        
        record = file_record[0]
        object_key = record.object_key

        file_path = storage_service.get_file_path(object_key)

        if not file_path:
             raise HTTPException(status_code=404, detail="File object not found in storage")

        result = crud.infer_from_file(str(file_path))
        fields = result["schema"]["fields"]
        columns = [{"name": f["name"], "type": f["type"]} for f in fields]

        crud.update_item_by_field(db = db,
                                  model_class = Base.classes.get("file_registry"),
                                  field_name = "file_id",
                                  value=file_id,
                                  update_data = {
                                      "file_schema": {"fields": columns},
                                      "status": "SCHEMA_INFERRED"
                                  }
                                ) 
        return {
            "file_id": file_id,
            "columns": columns
        }

    except HTTPException:
        raise

    except Exception as e:
        try:
            crud.update_item_by_field(
                db = db,
                model_class=Base.classes.get("file_registry"), 
                field_name="file_id",
                value=file_id,
                update_data = {"status": "FRICTIONLESS_FAILED"}
            )
        except Exception:
            pass

        raise HTTPException(status_code = 500, detail=f"Schema inference failed: {e}")