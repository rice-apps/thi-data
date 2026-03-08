from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from sqlalchemy import inspect as sa_inspect, Integer, Float, Numeric, Boolean, DateTime, Date, BigInteger, SmallInteger
from core.deps import get_db, get_internal_model_class, get_repository
from crud.base import BaseRepository, model_to_dict
from datetime import datetime
import logging

router = APIRouter()

logger = logging.getLogger(__name__)

# Constants
CORRUPTED_ROWS_TABLE = "corrupted_rows"

class CorruptedRowCreate(BaseModel):
    """Schema for creating a corrupted row entry."""
    target_table: str
    row_id: str
    error_reason: Optional[str] = None
    error_column: Optional[str] = None
    raw_row: Optional[Dict[str, Any]] = None
    corrected_row: Optional[Dict[str, Any]] = None


class CorruptedRowResponse(BaseModel):
    """Schema for corrupted row response."""
    id: int
    target_table: str
    row_id: str
    error_reason: Optional[str] = None
    error_column: Optional[str] = None
    raw_row: Optional[Dict[str, Any]] = None
    corrected_row: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)

class ResolutionRequest(BaseModel):
    """Schema for resolving a corrupted row."""
    corrections: Dict[str, Any]

def get_corrupted_rows_model():
    """Dependency to get the corrupted_rows model class."""
    return get_internal_model_class(CORRUPTED_ROWS_TABLE)


def _validate_and_cast(column_name: str, value: Any, column_type) -> Any:
    """
    Validate that `value` is castable to the SQLAlchemy `column_type`.
    Returns the cast value or raises ValueError on failure.
    """
    logger.debug(f"Validating column '{column_name}' with value '{value}' for type {column_type}")
    if value is None:
        return None

    if isinstance(column_type, (Integer, BigInteger, SmallInteger)):
        try:
            return int(value)
        except (ValueError, TypeError):
            logger.warning(f"Type validation failed for column '{column_name}': expected integer, got '{value}'")
            raise ValueError(f"Column '{column_name}' expects an integer, got '{value}'")

    if isinstance(column_type, (Float, Numeric)):
        try:
            return float(value)
        except (ValueError, TypeError):
            logger.warning(f"Type validation failed for column '{column_name}': expected number, got '{value}'")
            raise ValueError(f"Column '{column_name}' expects a number, got '{value}'")

    if isinstance(column_type, Boolean):
        if isinstance(value, bool):
            return value
        if str(value).lower() in ('true', '1', 'yes'):
            return True
        if str(value).lower() in ('false', '0', 'no'):
            return False
        logger.warning(f"Type validation failed for column '{column_name}': expected boolean, got '{value}'")
        raise ValueError(f"Column '{column_name}' expects a boolean, got '{value}'")

    if isinstance(column_type, DateTime):
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value))
        except (ValueError, TypeError):
            logger.warning(f"Type validation failed for column '{column_name}': expected datetime (ISO format), got '{value}'")
            raise ValueError(f"Column '{column_name}' expects a datetime (ISO format), got '{value}'")

    if isinstance(column_type, Date):
        try:
            return datetime.fromisoformat(str(value)).date()
        except (ValueError, TypeError):
            logger.warning(f"Type validation failed for column '{column_name}': expected date (ISO format), got '{value}'")
            raise ValueError(f"Column '{column_name}' expects a date (ISO format), got '{value}'")

    # For String/Text and other types, return as-is
    return value


@router.post("/api/corrupted_rows", response_model=Dict[str, Any])
def create_corrupted_row(
    row: CorruptedRowCreate, 
    model_class: Any = Depends(get_corrupted_rows_model),
    db: Session = Depends(get_db)
):
    """Create a new corrupted row entry."""
    data = row.model_dump()
    repo = get_repository(model_class)
    new_item = repo.create(db, data)
    return model_to_dict(new_item)


@router.get("/api/corrupted_rows", response_model=Dict[str, Any])
def get_corrupted_rows(
    skip: int = 0,
    limit: int = 100,
    model_class: Any = Depends(get_corrupted_rows_model),
    db: Session = Depends(get_db)
):
    """Get all corrupted row entries with pagination."""
    logger.info(f"Fetching corrupted rows with skip={skip}, limit={limit}")
    try:
        repo = get_repository(model_class)
        items, total = repo.get_all(db, skip=skip, limit=limit)
        logger.info(f"Successfully retrieved {len(items)} corrupted rows (total: {total})")
        return {
            "data": [model_to_dict(item) for item in items],
            "total": total,
            "page": (skip // limit) + 1,
            "limit": limit
        }
    except Exception as e:
        logger.error(f"Error getting corrupted rows: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Error getting corrupted rows: {e}")


@router.delete("/api/corrupted_rows/{row_id}")
def delete_corrupted_row(
    row_id: int, 
    model_class: Any = Depends(get_corrupted_rows_model),
    db: Session = Depends(get_db)
):
    """Delete a corrupted row entry by ID."""
    logger.info(f"Attempting to delete corrupted row entry with id: {row_id}")
    try:
        repo = get_repository(model_class)
        success = repo.delete(db, row_id)
        if not success:
            logger.warning(f"Corrupted row not found: {row_id}")
            raise HTTPException(status_code=404, detail="Corrupted row not found")
        logger.info(f"Corrupted row deleted successfully: {row_id}")
        return {"message": "Corrupted row deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting corrupted row {row_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Error deleting corrupted row: {e}")

@router.patch("/api/{target_table}/{row_id}/resolve")
def resolve_corrupted_row(
    target_table: str,
    row_id: str,
    resolution: ResolutionRequest,
    db: Session = Depends(get_db)
):
    """
    Resolves a corrupted row by updating the primary record and 
    removing the entry from the corrupted_rows table.
    """
    logger.info(f"Starting resolution for corrupted row - table: {target_table}, row_id: {row_id}")
    logger.debug(f"Resolution corrections: {resolution.corrections}")
    
    try:
        TargetModel = get_internal_model_class(target_table)
    except Exception:
        raise HTTPException(status_code=404, detail=f"Table '{target_table}' not found")

    record = db.query(TargetModel).filter(TargetModel.id == row_id).first()
    
    if not record:
        logger.warning(f"Record not found - table: {target_table}, row_id: {row_id}")
        raise HTTPException(status_code=404, detail=f"Record {row_id} not found in {target_table}")
    
    logger.debug(f"Record found in {target_table} for row_id: {row_id}")

    # Get column type metadata for validation
    mapper = sa_inspect(TargetModel)
    column_types = {c.key: c.columns[0].type for c in mapper.column_attrs if c.columns}
    logger.debug(f"Retrieved column types for validation: {list(column_types.keys())}")

    try:
        for column, value in resolution.corrections.items():
            logger.debug(f"Processing correction for column '{column}' with value '{value}'")
            if not hasattr(record, column):
                logger.warning(f"Column '{column}' does not exist in table {target_table}")
                raise ValueError(f"Column '{column}' does not exist in {target_table}")
            
            # Type-validate and cast the value before setting
            col_type = column_types.get(column)
            if col_type:
                value = _validate_and_cast(column, value, col_type)

            setattr(record, column, value)
            logger.debug(f"Successfully set column '{column}' to value '{value}'")
        
        logger.info(f"All corrections applied successfully for row_id: {row_id}")
    except ValueError as e:
        logger.error(f"Validation error during resolution: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Validation Error: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error during correction application: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Validation Error: {str(e)}")

    CorruptedModel = get_internal_model_class(CORRUPTED_ROWS_TABLE)
    corrupted_entries = db.query(CorruptedModel).filter(
        CorruptedModel.target_table == target_table,
        CorruptedModel.row_id == str(row_id)
    ).all()
    
    logger.info(f"Found {len(corrupted_entries)} corrupted entries to remove for row_id: {row_id}")

    try:
        
        for entry in corrupted_entries:
            logger.debug(f"Deleting corrupted entry with id: {entry.id}")
            db.delete(entry)
            
        db.commit()
        db.refresh(record)
        logger.info(f"Transaction committed successfully - row healed and {len(corrupted_entries)} error log(s) cleared")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Database transaction failed during resolution: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database Transaction Failed: {str(e)}")

    result = {
        "status": "success",
        "message": "Row healed and error log cleared.",
        "updated_record": model_to_dict(record)
    }
    logger.info(f"Corrupted row resolved successfully - table: {target_table}, row_id: {row_id}")
    return result
