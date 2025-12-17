from fastapi import APIRouter, HTTPException, Depends
import crud
from typing import Any, List
from sqlalchemy.orm import Session
from database import Base
from deps import get_db, get_model_class
from sqlalchemy import select, inspect, desc, func

router = APIRouter()

# Tables to hide from the user-facing list
HIDDEN_TABLES = ["alembic_version", "metadata_creation", "metadata_updates"]


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
    """
    all_tables = list(Base.classes.keys())
    visible_tables = [t for t in all_tables if t not in HIDDEN_TABLES]
    
    creation_model = Base.classes.get("metadata_creation")
    updates_model = Base.classes.get("metadata_updates")
    
    result = []
    
    for table_name in visible_tables:
        table_info = {
            "name": table_name,
            "uploadedBy": None,
            "dateUploaded": None,
            "dateModified": None,
            "size": None,
        }
        
        # Get table size
        try:
            size_stmt = select(
                func.pg_size_pretty(func.pg_total_relation_size(table_name))
            )
            size = db.execute(size_stmt).scalar()
            table_info["size"] = size
        except Exception:
            pass
        
        # Look up creation metadata
        if creation_model:
            try:
                stmt = select(creation_model).where(creation_model.table_name == table_name)
                creation_record = db.execute(stmt).scalars().first()
                if creation_record:
                    table_info["uploadedBy"] = getattr(creation_record, "created_by", None)
                    created_at = getattr(creation_record, "created_at", None)
                    if created_at:
                        table_info["dateUploaded"] = created_at.strftime("%m-%d-%Y")
            except Exception:
                pass
        
        # Look up the most recent update metadata
        if updates_model:
            try:
                if creation_model:
                    creation_stmt = select(creation_model).where(creation_model.table_name == table_name)
                    creation_record = db.execute(creation_stmt).scalars().first()
                    if creation_record:
                        creation_id = getattr(creation_record, "id", None)
                        if creation_id:
                            update_stmt = (
                                select(updates_model)
                                .where(updates_model.foreign_key == creation_id)
                                .order_by(desc(updates_model.updated_at))
                                .limit(1)
                            )
                            update_record = db.execute(update_stmt).scalars().first()
                            if update_record:
                                updated_at = getattr(update_record, "updated_at", None)
                                if updated_at:
                                    table_info["dateModified"] = updated_at.strftime("%m-%d-%Y")
            except Exception:
                pass
        
        if not table_info["dateModified"] and table_info["dateUploaded"]:
            table_info["dateModified"] = table_info["dateUploaded"]
        
        result.append(table_info)
    
    return {"tables": result}


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
        return size_info
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error getting size: {e}")