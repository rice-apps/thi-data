from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session
from core.deps import get_db, get_model_class
from core.database import Base
import crud
from datetime import datetime
import logging

router = APIRouter()

def log_metadata_update(db: Session, table_name: str, user_name: str = "system"):
    """
    Helper to update metadata_updates table when a row is changed.
    """
    try:
        MetadataCreation = Base.classes.get("metadata_creation")
        MetadataUpdates = Base.classes.get("metadata_updates")

        if not MetadataCreation or not MetadataUpdates:
            logging.warning("Metadata tables not found in automap.")
            return

        # 1. Find the creation record ID for this table
        stmt = select(MetadataCreation).where(MetadataCreation.table_name == table_name)
        creation_record = db.execute(stmt).scalars().first()

        creation_id = None
        if not creation_record:
            # Optionally create it if it doesn't exist
            try:
                new_creation = MetadataCreation(
                    table_name=table_name,
                    created_by="system", # Default since we don't have auth context here
                    created_at=datetime.now()
                )
                db.add(new_creation)
                db.flush() # Flush to get the ID
                creation_id = new_creation.id
            except Exception as e:
                logging.error(f"Failed to auto-create metadata_creation record: {e}")
                return
        else:
            creation_id = creation_record.id

        # 2. Create the update record
        new_update = MetadataUpdates(
            foreign_key=creation_id,
            updated_by=user_name,
            updated_at=datetime.now()
        )
        db.add(new_update)
        db.commit() # Commit the log

    except Exception as e:
        logging.error(f"Failed to log metadata update: {e}")
        # We don't want to fail the main request if logging fails, so we catch all

@router.get("/api/{table_name}")
def get_all_items(
    table_name: str,
    skip: int = 0,
    limit: int = 100,
    model_class: Any = Depends(get_model_class), 
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    
    CorruptedRows = Base.classes.get("corrupted_rows")

    if CorruptedRows and hasattr(model_class, 'original_csv_row_id') and hasattr(CorruptedRows, 'original_csv_row_id'):
        stmt = (
            select(model_class, CorruptedRows)
            .outerjoin(
                CorruptedRows, 
                model_class.original_csv_row_id == CorruptedRows.original_csv_row_id
            )
            .offset(skip)
            .limit(limit)
        )

        total = db.query(model_class).count()
        results = db.execute(stmt).all()

        data = []
        for main_row, corrupted_row in results:
            item_dict = crud.model_to_dict(main_row)

            if corrupted_row:
                item_dict['corrupted'] = True
                item_dict['corruption_reason'] = {
                    "reason": getattr(corrupted_row, "corruption_reason", "Unknown Error"),
                    "raw_values": crud.model_to_dict(corrupted_row)
                }
            else:
                item_dict['corrupted'] = False
                item_dict['corruption_reason'] = None

            data.append(item_dict)

    else:
        items, total = crud.get_all_items(db, model_class, skip=skip, limit=limit)
        data = [crud.model_to_dict(item) for item in items]
        return {
            "data": [crud.model_to_dict(item) for item in items],
            "total": total,
            "page": (skip // limit) + 1,
            "limit": limit
    }

@router.post("/api/{table_name}")
def create_item(
    item_data: dict, 
    table_name: str, # Capture table_name from path
    x_user_name: Optional[str] = Header(None, alias="X-User-Name"),
    model_class: Any = Depends(get_model_class), 
    db: Session = Depends(get_db)
) -> dict:
    # Dynamic Validation
    mapper = inspect(model_class)
    valid_keys = {c.key for c in mapper.column_attrs}
    
    for key in item_data:
        if key not in valid_keys:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid field: '{key}'. Valid fields are: {list(valid_keys)}"
            )
            
    try:
        new_item = crud.create_item(db, model_class, item_data)
        log_metadata_update(db, table_name, user_name=x_user_name or "system")
        return crud.model_to_dict(new_item)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error creating item: {e}")

@router.get("/api/{table_name}/search/{column}/{match}")
def match_items(
    column: str,
    match: str,
    skip: int = 0,
    limit: int = 100,
    model_class: Any = Depends(get_model_class), 
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    try:
        results, total = crud.filter_text(db, model_class, column, match, skip=skip, limit=limit)
        return {
            "data": [crud.model_to_dict(item) for item in results],
            "total": total,
            "page": (skip // limit) + 1,
            "limit": limit
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error matching items: {e}")

@router.get("/api/{table_name}/{item_id}")
def get_one_item(
    item_id: int, 
    model_class: Any = Depends(get_model_class), 
    db: Session = Depends(get_db)
) -> dict:
    item = crud.get_one_item(db, model_class, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return crud.model_to_dict(item)

@router.put("/api/{table_name}/{item_id}")
def update_item(
    table_name: str, # Capture table_name from path
    item_id: int,
    item_data: dict, 
    x_user_name: Optional[str] = Header(None, alias="X-User-Name"),
    model_class: Any = Depends(get_model_class), 
    db: Session = Depends(get_db)
) -> dict:
    item = crud.get_one_item(db, model_class, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    mapper = inspect(model_class)
    valid_keys = {c.key for c in mapper.column_attrs}
    pk_keys = {c.key for c in mapper.primary_key}

    for key, value in item_data.items():
        if key not in valid_keys:
            raise HTTPException(status_code=400, detail=f"Invalid field: '{key}'")
        if key in pk_keys:
            raise HTTPException(status_code=400, detail=f"Cannot update primary key field: '{key}'")
        setattr(item, key, value)
    
    try:
        new_item = crud.update_item(db, model_class, item_id, item)
        log_metadata_update(db, table_name, user_name=x_user_name or "system")
        return crud.model_to_dict(new_item)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error updating item: {e}")

@router.delete("/api/{table_name}/{item_id}")
def delete_item(
    table_name: str, # Capture table_name from path
    item_id: int, 
    x_user_name: Optional[str] = Header(None, alias="X-User-Name"),
    model_class: Any = Depends(get_model_class), 
    db: Session = Depends(get_db)
):
    success = crud.delete_item(db, model_class, item_id)
    if not success:
        raise HTTPException(status_code=404, detail="Item not found")
    
    log_metadata_update(db, table_name, user_name=x_user_name or "system")
    return {"message": "Item deleted successfully"}
