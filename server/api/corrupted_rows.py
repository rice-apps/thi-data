from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from core.deps import get_db, get_internal_model_class
import crud

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


def get_corrupted_rows_model():
    """Dependency to get the corrupted_rows model class."""
    return get_internal_model_class(CORRUPTED_ROWS_TABLE)


@router.post("/api/corrupted_rows", response_model=Dict[str, Any])
def create_corrupted_row(
    row: CorruptedRowCreate, 
    model_class: Any = Depends(get_corrupted_rows_model),
    db: Session = Depends(get_db)
):
    """Create a new corrupted row entry."""
    try: 
        data = row.model_dump()
        new_item = crud.create_item(db, model_class, data)
        return crud.model_to_dict(new_item)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error creating corrupted row: {e}")


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
