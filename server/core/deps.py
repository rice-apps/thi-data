from typing import Generator, Any
from fastapi import HTTPException
from sqlalchemy.orm import Session
from .database import SessionLocal, Base

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_model_class(table_name: str) -> Any:
    model_class = Base.classes.get(table_name)
    if not model_class:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found.")
    return model_class


def get_internal_model_class(table_name: str) -> Any:
    """
    Get model class for internal/system tables (e.g., corrupted_rows, metadata_*).
    Returns 500 error instead of 404 since these are configuration errors, not user errors.
    """
    model_class = Base.classes.get(table_name)
    if not model_class:
        raise HTTPException(
            status_code=500, 
            detail=f"Configuration error: '{table_name}' table not found."
        )
    return model_class

