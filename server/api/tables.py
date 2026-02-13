from fastapi import APIRouter, HTTPException, Depends
import crud
from typing import Any
from sqlalchemy.orm import Session
from core.database import Base
from core.deps import get_db, get_model_class, get_internal_model_class
from sqlalchemy import inspect

from core.constants import HIDDEN_TABLES

router = APIRouter()

@router.get("/api/tables")
def get_all_tables():
    """
    Get a list of all table names reflected from the database,
    excluding internal metadata tables.
    """
    all_tables = list(Base.classes.keys())
    visible_tables = [t for t in all_tables if t not in HIDDEN_TABLES]
    return {"tables": visible_tables}


@router.get("/api/tables_with_metadata")
def get_tables_with_metadata(db: Session = Depends(get_db)):
    """
    Get all tables with their metadata (uploaded by, date uploaded, date modified, size).
    Excludes internal metadata tables.
    Uses bulk fetching for performance.
    """
    all_tables = list(Base.classes.keys())
    visible_tables = [t for t in all_tables if t not in HIDDEN_TABLES]
    
    creation_model = get_internal_model_class("metadata_creation")
    updates_model = get_internal_model_class("metadata_updates")
    
    # Bulk fetch all metadata in one go
    # This matches the function defined in crud.py
    results = crud.get_tables_metadata(db, visible_tables, creation_model, updates_model)
    
    return {"tables": results}


@router.get("/api/schema/{table_name}")
def get_table_schema(
    table_name: str,
    model_class: Any = Depends(get_model_class)
) -> dict:
    """
    Get the column names for a table (excluding 'id').
    """
    mapper = inspect(model_class)
    columns = [c.key for c in mapper.column_attrs if c.key != "id"]
    return {"columns": columns}


@router.get("/api/get_size/{table_name}")
def get_size(
    table_name: str,
    db: Session = Depends(get_db)
) -> dict:
    """
    Get the size of a specific table.
    """
    try:
        size_info = crud.get_database_size(table_name, db)
        if not size_info:
            raise HTTPException(status_code=404, detail="Table not found")
        return size_info
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error getting size: {e}")