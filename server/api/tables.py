from fastapi import APIRouter, HTTPException, Depends
import crud
from typing import Any
from sqlalchemy.orm import Session
from core.database import Base
from core.deps import get_db, get_model_class, get_internal_model_class
from sqlalchemy import inspect
import logging

from core.constants import HIDDEN_TABLES

router = APIRouter()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(module)s:%(lineno)d -%(levelname)s - %(message)s"
)

@router.get("/api/tables")
def get_all_tables():
    """
    Get a list of all table names reflected from the database,
    excluding internal metadata tables.
    """
    logging.info("Getting all tables from database")
    all_tables = list(Base.classes.keys())
    visible_tables = [t for t in all_tables if t not in HIDDEN_TABLES]
    logging.info(f"Retrieved {len(visible_tables)} visible tables out of {len(all_tables)} total tables")
    return {"tables": visible_tables}


@router.get("/api/tables_with_metadata")
def get_tables_with_metadata(db: Session = Depends(get_db)):
    """
    Get all tables with their metadata (uploaded by, date uploaded, date modified, size).
    Excludes internal metadata tables.
    Uses bulk fetching for performance.
    """
    logging.info("Getting all tables with metadata")
    all_tables = list(Base.classes.keys())
    visible_tables = [t for t in all_tables if t not in HIDDEN_TABLES]
    logging.debug(f"Found {len(visible_tables)} visible tables")
    
    creation_model = get_internal_model_class("metadata_creation")
    updates_model = get_internal_model_class("metadata_updates")
    
    # Bulk fetch all metadata in one go
    # This matches the function defined in crud.py
    results = crud.get_tables_metadata(db, visible_tables, creation_model, updates_model)
    logging.info(f"Retrieved metadata for {len(results)} tables")
    
    return {"tables": results}


@router.get("/api/schema/{table_name}")
def get_table_schema(
    table_name: str,
    model_class: Any = Depends(get_model_class)
) -> dict:
    """
    Get the column names for a table (excluding 'id').
    """
    logging.info(f"Getting schema for table: {table_name}")
    mapper = inspect(model_class)
    columns = [c.key for c in mapper.column_attrs if c.key != "id"]
    logging.info(f"Retrieved {len(columns)} columns for table {table_name}")
    return {"columns": columns}


@router.get("/api/get_size/{table_name}")
def get_size(
    table_name: str,
    db: Session = Depends(get_db)
) -> dict:
    """
    Get the size of a specific table.
    """
    logging.info(f"Getting size for table: {table_name}")
    try:
        size_info = crud.get_database_size(table_name, db)
        if not size_info:
            logging.warning(f"Table not found: {table_name}")
            raise HTTPException(status_code=404, detail="Table not found")
        logging.info(f"Size info retrieved for table {table_name}")
        return size_info
    except Exception as e:
        logging.error(f"Error getting size for table {table_name}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Error getting size: {e}")