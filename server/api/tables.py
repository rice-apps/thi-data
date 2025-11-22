from fastapi import APIRouter, HTTPException, Depends
import crud
from typing import Any, List
from sqlalchemy.orm import Session
from database import Base
from deps import get_db, get_model_class
from sqlalchemy import select, inspect

router = APIRouter()
@router.get("/api/tables")
def get_all_tables():
    """
    Get a list of all table names reflected from
     the database.
    """
    return {"tables": list(Base.classes.keys())}

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