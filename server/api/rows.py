from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session
from core.deps import get_db, get_model_class, get_internal_model_class
from core.database import Base
import crud
from datetime import datetime
import logging

router = APIRouter()

logger = logging.getLogger(__name__)

def log_metadata_update(db: Session, table_name: str, user_name: str = "system"):
    """
    Helper to update metadata_updates table when a row is changed.
    """
    logger.debug(f"Logging metadata update for table: {table_name}, user: {user_name}")
    try:
        MetadataCreation = get_internal_model_class("metadata_creation")
        MetadataUpdates = get_internal_model_class("metadata_updates")

        # 1. Find the creation record ID for this table
        stmt = select(MetadataCreation).where(MetadataCreation.table_name == table_name)
        creation_record = db.execute(stmt).scalars().first()

        creation_id = None
        if not creation_record:
            logger.debug(f"No creation record found for table {table_name}, creating one")
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
                logger.debug(f"Created metadata_creation record with id: {creation_id}")
            except Exception as e:
                logger.error(f"Failed to auto-create metadata_creation record: {e}")
                return
        else:
            creation_id = creation_record.file_id
            logger.debug(f"Found existing creation record with id: {creation_id}")

        # 2. Create the update record
        new_update = MetadataUpdates(
            foreign_key=creation_id,
            updated_by=user_name,
            updated_at=datetime.now()
        )
        db.add(new_update)
        db.flush() # Flush instead of commit
        logger.debug(f"Metadata update logged successfully for table: {table_name}")

    except Exception as e:
        logger.error(f"Failed to log metadata update: {e}")
        # We don't want to fail the main request if logging fails, so we catch all

@router.get("/api/{table_name}")
def get_all_items(
    table_name: str,
    skip: int = 0,
    limit: int = 100,
    model_class: Any = Depends(get_model_class), 
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    logger.info(f"Getting all items from table: {table_name} (skip={skip}, limit={limit})")
    
    CorruptedRows = Base.classes.get("corrupted_rows")

    if CorruptedRows and hasattr(model_class, 'original_csv_row_id') and hasattr(CorruptedRows, 'original_csv_row_id'):
        logger.debug(f"Using corrupted rows join for table: {table_name}")
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

        # Get the column names from the main model for COALESCE logic
        mapper = inspect(model_class)
        main_columns = {c.key for c in mapper.column_attrs}

        data = []
        for main_row, corrupted_row in results:
            item_dict = crud.model_to_dict(main_row)

            if corrupted_row:
                corrupted_dict = crud.model_to_dict(corrupted_row)
                error_context: Dict[str, Any] = {}

                for col in main_columns:
                    if col in ('id', 'original_csv_row_id'):
                        continue
                    # COALESCE: if main value is NULL and sidecar has the raw text
                    if item_dict.get(col) is None and corrupted_dict.get(col) is not None:
                        error_context[col] = {
                            "raw_value": str(corrupted_dict[col]),
                            "error": getattr(corrupted_row, "error_reason", None) or "Validation failed"
                        }

                item_dict['_is_corrupted'] = len(error_context) > 0
                item_dict['_error_context'] = error_context if error_context else None
            else:
                item_dict['_is_corrupted'] = False
                item_dict['_error_context'] = None

            data.append(item_dict)

        logger.info(f"Retrieved {len(data)} items from {table_name}, total: {total}")
        return {
            "data": data,
            "total": total,
            "page": (skip // limit) + 1,
            "limit": limit
        }

    else:
        items, total = crud.get_all_items(db, model_class, skip=skip, limit=limit)
        logger.info(f"Retrieved {len(items)} items from {table_name}, total: {total}")
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
    logger.info(f"Creating item in table: {table_name}, user: {x_user_name or 'system'}")
    # Dynamic Validation
    mapper = inspect(model_class)
    valid_keys = {c.key for c in mapper.column_attrs}
    
    for key in item_data:
        if key not in valid_keys:
            logger.warning(f"Invalid field '{key}' provided for table {table_name}")
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid field: '{key}'. Valid fields are: {list(valid_keys)}"
            )
            
    try:
        new_item = crud.create_item(db, model_class, item_data)
        log_metadata_update(db, table_name, user_name=x_user_name or "system")
        logger.info(f"Item created successfully in table {table_name} with id: {new_item.id}")
        return crud.model_to_dict(new_item)
    except Exception as e:
        logger.error(f"Error creating item in table {table_name}: {str(e)}", exc_info=True)
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
    logger.info(f"Searching table {table_name} for column '{column}' matching '{match}' (skip={skip}, limit={limit})")
    try:
        results, total = crud.filter_text(db, model_class, column, match, skip=skip, limit=limit)
        logger.info(f"Found {total} matching items, returning {len(results)} results")
        return {
            "data": [crud.model_to_dict(item) for item in results],
            "total": total,
            "page": (skip // limit) + 1,
            "limit": limit
        }
    except Exception as e:
        logger.error(f"Error matching items in column {column}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Error matching items: {e}")

@router.get("/api/{table_name}/{item_id}")
def get_one_item(
    item_id: int, 
    model_class: Any = Depends(get_model_class), 
    db: Session = Depends(get_db)
) -> dict:
    logger.info(f"Getting item {item_id} from table")
    item = crud.get_one_item(db, model_class, item_id)
    if not item:
        logger.warning(f"Item {item_id} not found")
        raise HTTPException(status_code=404, detail="Item not found")
    logger.info(f"Item {item_id} retrieved successfully")
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
    logger.info(f"Updating item {item_id} in table: {table_name}, user: {x_user_name or 'system'}")
    item = crud.get_one_item(db, model_class, item_id)
    if not item:
        logger.warning(f"Item {item_id} not found in table {table_name}")
        raise HTTPException(status_code=404, detail="Item not found")

    mapper = inspect(model_class)
    valid_keys = {c.key for c in mapper.column_attrs}
    pk_keys = {c.key for c in mapper.primary_key}

    for key, value in item_data.items():
        if key not in valid_keys:
            logger.warning(f"Invalid field '{key}' provided for update in table {table_name}")
            raise HTTPException(status_code=400, detail=f"Invalid field: '{key}'")
        if key in pk_keys:
            logger.warning(f"Attempt to update primary key field '{key}' in table {table_name}")
            raise HTTPException(status_code=400, detail=f"Cannot update primary key field: '{key}'")
        setattr(item, key, value)
    
    try:
        new_item = crud.update_item(db, model_class, item_id, item)
        log_metadata_update(db, table_name, user_name=x_user_name or "system")
        logger.info(f"Item {item_id} updated successfully in table {table_name}")
        return crud.model_to_dict(new_item)
    except Exception as e:
        logger.error(f"Error updating item {item_id} in table {table_name}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Error updating item: {e}")

@router.delete("/api/{table_name}/{item_id}")
def delete_item(
    table_name: str, # Capture table_name from path
    item_id: int, 
    x_user_name: Optional[str] = Header(None, alias="X-User-Name"),
    model_class: Any = Depends(get_model_class), 
    db: Session = Depends(get_db)
):
    logger.info(f"Deleting item {item_id} from table: {table_name}, user: {x_user_name or 'system'}")
    success = crud.delete_item(db, model_class, item_id)
    if not success:
        logger.warning(f"Item {item_id} not found in table {table_name}")
        raise HTTPException(status_code=404, detail="Item not found")
    
    log_metadata_update(db, table_name, user_name=x_user_name or "system")
    logger.info(f"Item {item_id} deleted successfully from table {table_name}")
    return {"message": "Item deleted successfully"}
