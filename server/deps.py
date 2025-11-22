from fastapi import HTTPException
from sqlalchemy.orm import Session

from database import SessionLocal, Base

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_model_class(table_name: str):
    """
    FastAPI dependency to get the SQLAlchemy model class from a table name.
    """
    model_class = Base.classes.get(table_name)
    if not model_class:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found.")
    return model_class
