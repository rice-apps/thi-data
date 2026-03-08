from typing import Generator, Any, Optional
from contextlib import contextmanager
from fastapi import HTTPException
from sqlalchemy.orm import Session
from .database import SessionLocal, Base, reflect_db, run_migrations
from .storage import StorageProvider
from .s3_storage import S3StorageProvider
from FakeS3.fakeS3 import FakeS3
from .constants import HIDDEN_TABLES
from .config import settings

_storage_instance: Optional[StorageProvider] = None

def init_app_services(storage_provider: StorageProvider = None) -> None:
    """
    Centralized initialization for BOTH FastAPI and Celery Workers.
    Ensures DB reflection is complete and storage is ready.
    """
    global _storage_instance
    
    # Run Migrations before reflecting
    run_migrations()
    
    # Reflect Database Models
    reflect_db()
    
    # Initialize Storage
    if _storage_instance is None:
        if storage_provider:
            _storage_instance = storage_provider
        elif settings.USE_S3:
            _storage_instance = S3StorageProvider(
                endpoint_url=settings.S3_ENDPOINT,
                access_key=settings.S3_KEY,
                secret_key=settings.S3_SECRET,
                bucket_name=settings.S3_BUCKET,
                region_name=settings.S3_REGION
            )
        else:
            _storage_instance = FakeS3()

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

@contextmanager
def get_db_context():
    """
    Context manager version of get_db for use in Celery tasks or scripts.
    
    Usage:
        with get_db_context() as db:
            crud.get_items_by_field(db, ...)
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

def get_storage_provider() -> StorageProvider:
    if _storage_instance is None:
        raise RuntimeError("Storage provider not initialized. Call init_app_services() first.")
    return _storage_instance

def get_file_registry_model() -> Any:
    """Get the reflected file_registry model. Centralized to avoid scattered string lookups."""
    return get_internal_model_class("file_registry")

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
