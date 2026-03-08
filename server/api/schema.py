from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List
from sqlalchemy.orm import Session
import crud
from core.deps import get_db, get_storage_provider, get_file_registry_model
from core.enums import FileStatus
from core.storage import StorageProvider
import services.etl_processor as etl_processor
import logging

router = APIRouter(prefix="/api/schema", tags=["schema"])

logger = logging.getLogger(__name__)

class Column(BaseModel):
    name: str
    type: str

class SchemaUpdate(BaseModel):
    columns: List[Column]

@router.patch("/{file_id}")
def confirm_schema(
    file_id: str,
    schema: SchemaUpdate,
    db: Session = Depends(get_db),
    storage: StorageProvider = Depends(get_storage_provider),
):
    logger.info(f"Confirming schema for file_id: {file_id}")
    logger.debug(f"Schema columns: {[c.name for c in schema.columns]}")
    file_records = crud.get_items_by_field(
        db=db,
        model_class=get_file_registry_model(),
        field_name="file_id",
        value=file_id
    )
    if not file_records:
        logger.warning(f"File not found: {file_id}")
        raise HTTPException(status_code=404, detail="File not found")

    clean_schema = {"fields": [c.model_dump() for c in schema.columns]}
    schema_map = {c.name: c.type for c in schema.columns}
    logger.debug(f"Clean schema created with {len(schema.columns)} columns")

    crud.update_item_by_field(
        db=db,
        model_class=get_file_registry_model(),
        field_name="file_id",
        value=file_id,
        update_data={
            "file_schema": clean_schema,
            "status": FileStatus.SCHEMA_CONFIRMED
        }
    )
    logger.info(f"File registry updated with schema for file_id: {file_id}")

    try:
        logger.info(f"Starting ETL pipeline for file_id: {file_id}")
        etl_processor.run_pipeline_with_schema(file_id, schema_map, db=db, storage=storage)
        logger.info(f"ETL pipeline completed successfully for file_id: {file_id}")
    except Exception as e:
        logger.error(f"ETL pipeline failed for file_id {file_id}: {str(e)}", exc_info=True)

    logger.info(f"Schema confirmation completed for file_id: {file_id}")
    return {
        "file_id": file_id,
        "status": FileStatus.SCHEMA_CONFIRMED,
        "schema": clean_schema
    }