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
