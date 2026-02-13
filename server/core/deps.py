from typing import Generator, Any, Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session
from .database import SessionLocal, Base
from .storage import StorageProvider
from .constants import HIDDEN_TABLES

def get_db() -> Generator[Session, None, None]:
    """
    Provides a transactional database session.
    
    - Auto-commits on successful request completion.
    - Auto-rollbacks on any unhandled exception.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def get_model_class(table_name: str) -> Any:
    if table_name in HIDDEN_TABLES:
        raise HTTPException(status_code=403, detail=f"Access to table '{table_name}' is restricted.")
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

def get_internal_model_class(table_name: str) -> Any:
    """
    Get model class for internal/system tables (e.g., corrupted_rows, metadata_*).
    Returns 500 error instead of 404 since these are configuration errors, not user errors.
    """
    model_class = Base.classes.get(table_name)
    if not model_class:
        raise HTTPException(
            status_code=500, 
            detail=f"Configuration error: '{table_name}' table not found. Ensure reflect_db() was called."
        )
    return model_class

def get_db_context() -> Generator[Session, None, None]:
    """
    Context manager version of get_db for use in background tasks or scripts.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

