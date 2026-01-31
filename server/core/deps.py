from typing import Generator, Any, Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session
from .database import SessionLocal, Base
from .storage import StorageProvider

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

_storage_instance: Optional[StorageProvider] = None

def init_storage_provider(provider: StorageProvider) -> None:
    global _storage_instance
    _storage_instance = provider

def get_storage_provider() -> StorageProvider:
    if _storage_instance is None:
        raise RuntimeError("Storage provider not initialized. Call init_storage_provider() first.")
    return _storage_instance

