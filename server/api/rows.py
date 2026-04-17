from typing import Any, Dict, List, Optional, Tuple
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session
from core.deps import get_db, get_model_class, get_internal_model_class, get_repository
from core.database import get_class_strict, is_dlt_table
from core.config import settings
from crud.base import model_to_dict
from datetime import datetime
import logging

router = APIRouter()

logger = logging.getLogger(__name__)


def _build_corruption_join_rows(
    results: List[Tuple[Any, Any]],
    model_class: Any,
    main_columns: set,
) -> List[Dict[str, Any]]:
    pk_key = inspect(model_class).primary_key[0].key
    aggregated: Dict[Any, Dict[str, Any]] = {}
    order: List[Any] = []

    for main_row, corrupted_row in results:
        pk_val = getattr(main_row, pk_key)
        if pk_val not in aggregated:
            order.append(pk_val)
            aggregated[pk_val] = {"main_row": main_row, "corrupted_rows": []}
        if corrupted_row is not None:
            aggregated[pk_val]["corrupted_rows"].append(corrupted_row)

    data: List[Dict[str, Any]] = []
    for pk_val in order:
        bundle = aggregated[pk_val]
        main_row = bundle["main_row"]
        item_dict = model_to_dict(main_row)
        error_context: Dict[str, Any] = {}
        for corrupted_row in bundle["corrupted_rows"]:
            corrupted_dict = model_to_dict(corrupted_row)
            for col in main_columns:
                if col in ("id", "original_csv_row_id"):
                    continue
                if item_dict.get(col) is None and corrupted_dict.get(col) is not None:
                    if col not in error_context:
                        error_context[col] = {
                            "raw_value": str(corrupted_dict[col]),
                            "error": getattr(corrupted_row, "error_reason", None)
                            or "Validation failed",
                        }
        if error_context:
            item_dict["_is_corrupted"] = True
            item_dict["_error_context"] = error_context
        else:
            item_dict["_is_corrupted"] = False
            item_dict["_error_context"] = None
        data.append(item_dict)
    return data


def log_metadata_update(db: Session, table_name: str, user_name: str = "system"):
    """
    Helper to update metadata_updates table when a row is changed.
    """
    logger.debug(f"Logging metadata update for table: {table_name}, user: {user_name}")
    try:
        MetadataCreation = get_internal_model_class("metadata_creation")
        MetadataUpdates = get_internal_model_class("metadata_updates")

        # Find the creation record ID for this table
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

        # Create the update record
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

    # Try per-table corrupted sidecar first, fall back to legacy name
    CorruptedRows = (
        get_class_strict(f"{table_name}__corrupted", schema=settings.DLT_DATASET)
        or get_class_strict("corrupted_rows", schema=settings.DLT_DATASET)
    )

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

        mapper = inspect(model_class)
        main_columns = {c.key for c in mapper.column_attrs}
        data = _build_corruption_join_rows(results, model_class, main_columns)

        logger.info(f"Retrieved {len(data)} items from {table_name}, total: {total}")
        return {
            "data": data,
            "total": total,
            "page": (skip // limit) + 1,
            "limit": limit
        }

    else:
        repo = get_repository(model_class)
        items, total = repo.get_all(db, skip=skip, limit=limit)
        logger.info(f"Retrieved {len(items)} items from {table_name}, total: {total}")
        data = [model_to_dict(item) for item in items]
        return {
            "data": data,
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
    item_data = dict(item_data)
    item_data.pop("id", None)
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
        repo = get_repository(model_class)
        new_item = repo.create(db, item_data)
        log_metadata_update(db, table_name, user_name=x_user_name or "system")
        logger.info(f"Item created successfully in table {table_name} with id: {new_item.id}")
        return model_to_dict(new_item)
    except Exception as e:
        logger.error(f"Error creating item in table {table_name}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail="Could not create the row. Please check your input values.")

@router.get("/api/{table_name}/search/{column}/{match}")
def match_items(
    table_name: str,
    column: str,
    match: str,
    skip: int = 0,
    limit: int = 100,
    model_class: Any = Depends(get_model_class), 
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    logger.info(f"Searching table {table_name} for column '{column}' matching '{match}' (skip={skip}, limit={limit})")
    try:
        repo = get_repository(model_class)
        results, total = repo.filter_text(db, column, match, skip=skip, limit=limit)
        logger.info(f"Found {total} matching items, returning {len(results)} results")
        return {
            "data": [model_to_dict(item) for item in results],
            "total": total,
            "page": (skip // limit) + 1,
            "limit": limit
        }
    except Exception as e:
        logger.error(f"Error matching items in column {column}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail="Search failed. Please try a different query.")

@router.get("/api/{table_name}/{item_id}")
def get_one_item(
    item_id: str,
    model_class: Any = Depends(get_model_class),
    db: Session = Depends(get_db)
) -> dict:
    logger.info(f"Getting item {item_id} from table")
    repo = get_repository(model_class)
    item = repo.get_by_id(db, item_id)
    if not item:
        logger.warning(f"Item {item_id} not found")
        raise HTTPException(status_code=404, detail="Item not found")
    logger.info(f"Item {item_id} retrieved successfully")
    return model_to_dict(item)

@router.put("/api/{table_name}/{item_id}")
def update_item(
    table_name: str, # Capture table_name from path
    item_id: str,
    item_data: dict,
    x_user_name: Optional[str] = Header(None, alias="X-User-Name"),
    model_class: Any = Depends(get_model_class),
    db: Session = Depends(get_db)
) -> dict:
    logger.info(f"Updating item {item_id} in table: {table_name}, user: {x_user_name or 'system'}")
    repo = get_repository(model_class)
    item = repo.get_by_id(db, item_id)
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
    
    try:
        new_item = repo.update(db=db, db_obj=item, obj_in=item_data)
        log_metadata_update(db, table_name, user_name=x_user_name or "system")
        
        # Cleanup sidecar error record if it exists
        if is_dlt_table(model_class) and hasattr(new_item, 'original_csv_row_id'):
            CorruptedRows = (
                get_class_strict(f"{table_name}__corrupted", schema=settings.DLT_DATASET)
                or get_class_strict("corrupted_rows", schema=settings.DLT_DATASET)
            )
            if CorruptedRows:
                try:
                    db.query(CorruptedRows).filter(CorruptedRows.original_csv_row_id == new_item.original_csv_row_id).delete()
                    db.commit()
                except Exception as cleanup_err:
                    logger.warning(f"Failed to cleanup corrupted_rows for {item_id}: {cleanup_err}")
                
        logger.info(f"Item {item_id} updated successfully in table {table_name}")
        return model_to_dict(new_item)
    except Exception as e:
        logger.error(f"Error updating item {item_id} in table {table_name}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail="Could not update the row. Please check your input values.")

@router.delete("/api/{table_name}/{item_id}")
def delete_item(
    table_name: str, # Capture table_name from path
    item_id: str,
    x_user_name: Optional[str] = Header(None, alias="X-User-Name"),
    model_class: Any = Depends(get_model_class),
    db: Session = Depends(get_db)
):
    logger.info(f"Deleting item {item_id} from table: {table_name}, user: {x_user_name or 'system'}")
    
    # Needs the item's details before deleting it
    repo = get_repository(model_class)
    item = repo.get_by_id(db, item_id)
    if not item:
        logger.warning(f"Item {item_id} not found in table {table_name}")
        raise HTTPException(status_code=404, detail="Item not found")

    row_id_to_cleanup = getattr(item, 'original_csv_row_id', None)
    is_dlt = is_dlt_table(model_class)
    
    success = repo.delete(db, item_id)
    if not success:
        logger.warning(f"Item {item_id} not found in table {table_name}")
        raise HTTPException(status_code=404, detail="Item not found")
    
    # Cleanup sidecar error record if it exists
    if is_dlt and row_id_to_cleanup is not None:
        CorruptedRows = (
            get_class_strict(f"{table_name}__corrupted", schema=settings.DLT_DATASET)
            or get_class_strict("corrupted_rows", schema=settings.DLT_DATASET)
        )
        if CorruptedRows:
            try:
                db.query(CorruptedRows).filter(CorruptedRows.original_csv_row_id == row_id_to_cleanup).delete()
                db.commit()
            except Exception as cleanup_err:
                logger.warning(f"Failed to cleanup corrupted_rows after delete for {item_id}: {cleanup_err}")
                
    log_metadata_update(db, table_name, user_name=x_user_name or "system")
    logger.info(f"Item {item_id} deleted successfully from table {table_name}")
    return {"message": "Item deleted successfully"}
