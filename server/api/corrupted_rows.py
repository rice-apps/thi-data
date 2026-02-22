from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import inspect as sa_inspect, Integer, Float, Numeric, Boolean, DateTime, Date, BigInteger, SmallInteger
from core.deps import get_db, get_internal_model_class
import crud
from datetime import datetime

router = APIRouter()

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

    class Config:
        from_attributes = True

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
    if value is None:
        return None

    if isinstance(column_type, (Integer, BigInteger, SmallInteger)):
        try:
            return int(value)
        except (ValueError, TypeError):
            raise ValueError(f"Column '{column_name}' expects an integer, got '{value}'")

    if isinstance(column_type, (Float, Numeric)):
        try:
            return float(value)
        except (ValueError, TypeError):
            raise ValueError(f"Column '{column_name}' expects a number, got '{value}'")

    if isinstance(column_type, Boolean):
        if isinstance(value, bool):
            return value
        if str(value).lower() in ('true', '1', 'yes'):
            return True
        if str(value).lower() in ('false', '0', 'no'):
            return False
        raise ValueError(f"Column '{column_name}' expects a boolean, got '{value}'")

    if isinstance(column_type, DateTime):
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value))
        except (ValueError, TypeError):
            raise ValueError(f"Column '{column_name}' expects a datetime (ISO format), got '{value}'")

    if isinstance(column_type, Date):
        try:
            return datetime.fromisoformat(str(value)).date()
        except (ValueError, TypeError):
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
    new_item = crud.create_item(db, model_class, data)
    return crud.model_to_dict(new_item)


@router.get("/api/corrupted_rows", response_model=Dict[str, Any])
def get_corrupted_rows(
    skip: int = 0,
    limit: int = 100,
    model_class: Any = Depends(get_corrupted_rows_model),
    db: Session = Depends(get_db)
):
    """Get all corrupted row entries with pagination."""
    try: 
        items, total = crud.get_all_items(db, model_class, skip=skip, limit=limit)
        return {
            "data": [crud.model_to_dict(item) for item in items],
            "total": total,
            "page": (skip // limit) + 1,
            "limit": limit
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error getting corrupted rows: {e}")


@router.delete("/api/corrupted_rows/{row_id}")
def delete_corrupted_row(
    row_id: int, 
    model_class: Any = Depends(get_corrupted_rows_model),
    db: Session = Depends(get_db)
):
    """Delete a corrupted row entry by ID."""
    try:
        success = crud.delete_item(db, model_class, row_id)
        if not success:
            raise HTTPException(status_code=404, detail="Corrupted row not found")
        return {"message": "Corrupted row deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
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
    try:
        TargetModel = get_internal_model_class(target_table)
    except Exception:
        raise HTTPException(status_code=404, detail=f"Table '{target_table}' not found")

    record = db.query(TargetModel).filter(TargetModel.id == row_id).first()
    
    if not record:
        raise HTTPException(status_code=404, detail=f"Record {row_id} not found in {target_table}")

    # Get column type metadata for validation
    mapper = sa_inspect(TargetModel)
    column_types = {c.key: c.columns[0].type for c in mapper.column_attrs if c.columns}

    try:
        for column, value in resolution.corrections.items():
            if not hasattr(record, column):
                raise ValueError(f"Column '{column}' does not exist in {target_table}")
            
            # Type-validate and cast the value before setting
            col_type = column_types.get(column)
            if col_type:
                value = _validate_and_cast(column, value, col_type)

            setattr(record, column, value)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Validation Error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Validation Error: {str(e)}")

    CorruptedModel = get_internal_model_class(CORRUPTED_ROWS_TABLE)
    corrupted_entries = db.query(CorruptedModel).filter(
        CorruptedModel.target_table == target_table,
        CorruptedModel.row_id == str(row_id)
    ).all()

    try:
        
        for entry in corrupted_entries:
            db.delete(entry)
            
        db.commit()
        db.refresh(record)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database Transaction Failed: {str(e)}")

    return {
        "status": "success",
        "message": "Row healed and error log cleared.",
        "updated_record": crud.model_to_dict(record)
    }
