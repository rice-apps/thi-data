from typing import Generator, Any
from fastapi import HTTPException
from sqlalchemy.orm import Session
from .database import SessionLocal, Base
from FakeS3.fakeS3 import FakeS3

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

#Creates a FakeS3 instance
_fake_s3_instance = FakeS3()

def get_fake_s3() -> FakeS3:
    return _fake_s3_instance

