from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List
from sqlalchemy.orm import Session
import crud
from core.deps import get_db
from core.database import Base
from core.enums import FileStatus
import services.etl_processor as etl_processor

router = APIRouter(prefix="/api/schema", tags=["schema"])

class Column(BaseModel):
    name: str
    type: str

class SchemaUpdate(BaseModel):
    columns: List[Column]

@router.patch("/{file_id}")
def confirm_schema(file_id: str, schema: SchemaUpdate, db: Session = Depends(get_db)):
    file_records = crud.get_items_by_field(
        db=db,
        model_class=Base.classes.get("file_registry"),
        field_name="file_id",
        value=file_id
    )
    if not file_records:
        raise HTTPException(status_code=404, detail="File not found")

    clean_schema = {"fields": [c.dict() for c in schema.columns]}
    schema_map = {c.name: c.type for c in schema.columns}

    crud.update_item_by_field(
        db=db,
        model_class=Base.classes.get("file_registry"),
        field_name="file_id",
        value=file_id,
        update_data={
            "file_schema": clean_schema,
            "status": FileStatus.SCHEMA_CONFIRMED
        }
    )

    try:
        if hasattr(etl_processor, "run_pipeline_with_schema"):
            etl_processor.run_pipeline_with_schema(file_id, schema_map)
    except Exception as e:
        print(f"ETL pipeline failed: {e}")

    return {
        "file_id": file_id,
        "status": FileStatus.SCHEMA_CONFIRMED,
        "schema": clean_schema
    }