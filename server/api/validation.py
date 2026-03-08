from fastapi import APIRouter, HTTPException, Depends
import crud
from core.deps import get_db, get_storage_provider, get_file_registry_model
from core.enums import FileStatus
from core.storage import StorageProvider
from sqlalchemy.orm import Session
import logging

router = APIRouter()

logger = logging.getLogger(__name__)

@router.post("/api/validate_schema")
def validate_schema(file_id: str, db: Session = Depends(get_db), storage_service: StorageProvider = Depends(get_storage_provider)):
    logger.info(f"Starting schema validation for file_id: {file_id}")
    try:
        file_record = crud.get_items_by_field(db = db,
                                              model_class=get_file_registry_model(),
                                              field_name = "file_id",
                                              value=file_id) 
        if not file_record:
            logger.warning(f"File ID not found in registry: {file_id}")
            raise HTTPException(status_code = 404, detail="File ID not found in registry")
        
        record = file_record[0]
        object_key = record.object_key
        logger.debug(f"Retrieved file record with object_key: {object_key}")

        file_path = storage_service.get_file_path(object_key)

        if not file_path:
             logger.error(f"File object not found in storage: {object_key}")
             raise HTTPException(status_code=404, detail="File object not found in storage")

        logger.info(f"Inferring schema from file: {file_path}")
        result = crud.infer_from_file(str(file_path))
        fields = result["schema"]["fields"]
        columns = [{"name": f["name"], "type": f["type"]} for f in fields]
        logger.info(f"Schema inferred successfully with {len(columns)} columns")

        crud.update_item_by_field(db = db,
                                  model_class = get_file_registry_model(),
                                  field_name = "file_id",
                                  value=file_id,
                                  update_data = {
                                      "file_schema": {"fields": columns},
                                      "status": FileStatus.SCHEMA_INFERRED
                                  }
                                )
        logger.info(f"File registry updated with inferred schema for file_id: {file_id}")
        return {
            "file_id": file_id,
            "columns": columns
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Schema inference failed for file_id {file_id}: {str(e)}", exc_info=True)
        try:
            crud.update_item_by_field(
                db = db,
                model_class=get_file_registry_model(), 
                field_name="file_id",
                value=file_id,
                update_data = {"status": FileStatus.FRICTIONLESS_FAILED}
            )
            logger.info(f"File status updated to FRICTIONLESS_FAILED for file_id: {file_id}")
        except Exception:
            logger.error(f"Failed to update file status for file_id {file_id}")
            pass

        raise HTTPException(status_code = 500, detail=f"Schema inference failed: {e}")