from fastapi import APIRouter, HTTPException, Depends
from crud.metadata import get_tables_metadata, get_database_size
from typing import Any
from sqlalchemy.orm import Session
from sqlalchemy import inspect, text
import core.database as db_module
from core.database import get_class, reflect_db
from core.deps import get_db, get_model_class, get_internal_model_class, get_file_registry_model, _repo_cache
from core.config import settings
import logging

from core.constants import UNLISTED_TABLES, HIDDEN_TABLE_SUFFIXES

router = APIRouter()

logger = logging.getLogger(__name__)

@router.get("/api/tables")
def get_all_tables():
    """
    Get a list of all table names reflected from the database,
    excluding internal metadata tables.
    """
    logger.info("Getting all tables from database")
    all_tables = list(db_module.Base.classes.keys())
    visible_tables = [t for t in all_tables if _is_visible(t)]
    logger.info(f"Retrieved {len(visible_tables)} visible tables out of {len(all_tables)} total tables")
    return {"tables": visible_tables}


def _is_visible(table_name: str) -> bool:
    from core.constants import DLT_INTERNAL_TABLE_PREFIX
    if table_name in UNLISTED_TABLES:
        return False
    if table_name.startswith(DLT_INTERNAL_TABLE_PREFIX):
        return False
    return not any(table_name.endswith(s) for s in HIDDEN_TABLE_SUFFIXES)


@router.get("/api/tables_with_metadata")
def get_tables_with_metadata(db: Session = Depends(get_db)):
    """
    Get all tables with their metadata (uploaded by, date uploaded, date modified, size).
    Excludes internal metadata tables.
    Uses bulk fetching for performance.
    """
    logger.info("Getting all tables with metadata")
    all_tables = list(db_module.Base.classes.keys())
    visible_tables = [t for t in all_tables if _is_visible(t)]
    logger.debug(f"Found {len(visible_tables)} visible tables")
    
    creation_model = get_internal_model_class("metadata_creation")
    updates_model = get_internal_model_class("metadata_updates")
    
    # Bulk fetch all metadata in one go
    # This matches the function defined in crud.py
    results = get_tables_metadata(db, visible_tables, creation_model, updates_model)
    logger.info(f"Retrieved metadata for {len(results)} tables")
    
    return {"tables": results}


@router.get("/api/schema/{table_name}")
def get_table_schema(
    table_name: str,
    model_class: Any = Depends(get_model_class)
) -> dict:
    """
    Get the column names for a table.
    """
    logger.info(f"Getting schema for table: {table_name}")
    mapper = inspect(model_class)
    columns = [
        c.key
        for c in mapper.column_attrs
        if c.key not in ("original_csv_row_id", "id")
    ]
    logger.info(f"Retrieved {len(columns)} columns for table {table_name}")
    return {"columns": columns}


@router.delete("/api/tables/{table_name}")
def delete_table(table_name: str, db: Session = Depends(get_db)):
    if not _is_visible(table_name):
        raise HTTPException(status_code=403, detail=f"Deletion of '{table_name}' is not permitted.")

    if not get_class(table_name):
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found.")

    dlt_schema = settings.DLT_DATASET
    MetadataCreation = get_internal_model_class("metadata_creation")
    MetadataUpdates = get_internal_model_class("metadata_updates")
    FileRegistry = get_file_registry_model()

    for record in db.query(MetadataCreation).filter(MetadataCreation.table_name == table_name).all():
        db.query(MetadataUpdates).filter(MetadataUpdates.foreign_key == record.id).delete()
        db.delete(record)

    db.query(FileRegistry).filter(FileRegistry.target_table_name == table_name).delete()

    db.execute(text(f'DROP TABLE IF EXISTS {dlt_schema}."{table_name}"'))
    db.execute(text(f'DROP TABLE IF EXISTS {dlt_schema}."{table_name}__corrupted"'))

    db.commit()
    reflect_db()

    _repo_cache.pop(table_name, None)
    _repo_cache.pop(f"{table_name}__corrupted", None)

    return {"deleted": table_name}


@router.get("/api/get_size/{table_name}")
def get_size(
    table_name: str,
    db: Session = Depends(get_db)
) -> dict:
    """
    Get the size of a specific table.
    """
    logger.info(f"Getting size for table: {table_name}")
    try:
        size_info = get_database_size(table_name, db)
        if not size_info:
            logger.warning(f"Table not found: {table_name}")
            raise HTTPException(status_code=404, detail="Table not found")
        logger.info(f"Size info retrieved for table {table_name}")
        return size_info
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting size for table {table_name}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Error getting size: {e}")