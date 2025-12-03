from fastapi import APIRouter, HTTPException, Depends
import crud
from typing import Any, List
from sqlalchemy.orm import Session
from database import Base
from deps import get_db, get_model_class
from sqlalchemy import select, inspect, desc, func

router = APIRouter()

HIDDEN_TABLES = ["alembic_version", "metadata_creation", "metadata_updates"]

@router.get("/api/tables_with_metadata")
def get_tables_with_metadata(db: Session = Depends(get_db)):
    """
    Get all tables with their metadata (uploaded by, date uploaded, date modified, size).
    Excludes internal metadata tables.
    """
    all_tables = list(Base.classes.keys())
    visible_tables = [t for t in all_tables if t not in HIDDEN_TABLES]
    
    # Get metadata_creation model for looking up creation info
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
            pass  # Size lookup failed
        
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
                pass  # Table might not have metadata yet
        
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
                pass  # Table might not have update metadata yet
        
        # If no modification date, use upload date
        if not table_info["dateModified"] and table_info["dateUploaded"]:
            table_info["dateModified"] = table_info["dateUploaded"]
        
        result.append(table_info)
    
    return {"tables": result}

@router.get("/api/get_size/{table_name}")
def get_size(
    table_name: str,
    db: Session = Depends(get_db)
) -> dict:
    """
    Get the size of a specific table (e.g. KB, MB, GB).
    """
    try:
        size_info = crud.get_database_size(table_name, db)
        return size_info
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error getting size: {e}")


@router.get("/api/{table_name}")
def get_all_items(
    model_class: Any = Depends(get_model_class), 
    db: Session = Depends(get_db)
) -> List[dict]:
    """
    Get all items from a specified table.
    """
    items = crud.get_all_items(db, model_class)
    return [crud.model_to_dict(item) for item in items]

@router.post("/api/table/{table_name}")
def create_item(
    item_data: dict, 
    model_class: Any = Depends(get_model_class), 
    db: Session = Depends(get_db)
) -> dict:
    """
    Create a new item in a specified table.
    Validation is based on the table's columns, not a Pydantic schema.
    """
    mapper = inspect(model_class)
    valid_keys = {c.key for c in mapper.column_attrs}
    
    # --- Dynamic Validation ---
    for key in item_data:
        if key not in valid_keys:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid field: '{key}'. Valid fields are: {list(valid_keys)}"
            )
            
    try:
        new_item = crud.create_item(db, model_class, item_data)
        return crud.model_to_dict(new_item)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error creating item: {e}")


@router.get("/api/{table_name}/{item_id}")
def get_one_item(
    item_id: int, 
    model_class: Any = Depends(get_model_class), 
    db: Session = Depends(get_db)
) -> dict:
    """
    Get a single item by its ID from a specified table.
    (Note: Assumes an integer primary key)
    """
    item = crud.get_one_item(db, model_class, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return crud.model_to_dict(item)

@router.put("/api/{table_name}/{item_id}")
def update_item(
    item_id: int,
    item_data: dict, 
    model_class: Any = Depends(get_model_class), 
    db: Session = Depends(get_db)
) -> dict:
    """
    Update an item in a specified table.
    Validation is based on the table's columns.
    """
    item = crud.get_one_item(db, model_class, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    mapper = inspect(model_class)
    valid_keys = {c.key for c in mapper.column_attrs}
    pk_keys = {c.key for c in mapper.primary_key}

    for key, value in item_data.items():
        if key not in valid_keys:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid field: '{key}'. Valid fields are: {list(valid_keys)}"
            )
        if key in pk_keys:
            raise HTTPException(
                status_code=400, 
                detail=f"Cannot update primary key field: '{key}'"
            )
        setattr(item, key, value)
    
    try:
        new_item = crud.update_item(db, model_class, item_id, item)
        return crud.model_to_dict(new_item)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error updating item: {e}")

@router.delete("/api/{table_name}/{item_id}")
def delete_item(
    item_id: int, 
    model_class: Any = Depends(get_model_class), 
    db: Session = Depends(get_db)
):
    """
    Delete an item by its ID from a specified table.
    """
    crud.delete_item(db, model_class, item_id)
    return {"message": "Item deleted successfully"}