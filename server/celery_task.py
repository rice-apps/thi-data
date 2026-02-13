from celery import Celery
from services.etl_processor import process_file_task
from typing import Literal
import core.config as config

from core.deps import get_db_context, get_storage_provider
from core.database import Base, reflect_db
import crud
import logging

# Ensure models are reflected for background worker
reflect_db()

app = Celery('tasks', broker=config.settings.BROKER_URL)

def update_file_status(file_id: str, status: str, error_msg: str = None):
    """Update file status in the registry database."""
    with next(get_db_context()) as db:
        update_data = {"status": status}
        if error_msg:
            # Note: We might want a dedicated error field in the model later
            pass
        crud.update_item_by_field(
            db=db,
            model_class=Base.classes.file_registry,
            field_name="file_id",
            value=file_id,
            update_data=update_data
        )

@app.task(bind=True, acks_late=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def process_patient_file(self, file_id: str, proposed_schema: dict) -> dict:
    """
    Celery task to process a patient data file.
    """
    logging.info(f"Starting processing for file_id: {file_id}")
    update_file_status(file_id, "PROCESSING")

    try:
        # 1. Get object key from registry
        with next(get_db_context()) as db:
            records = crud.get_items_by_field(
                db=db,
                model_class=Base.classes.file_registry,
                field_name="file_id",
                value=file_id
            )
            if not records:
                raise ValueError(f"File ID {file_id} not found in registry")
            object_key = records[0].object_key

        # 2. Get local file path via StorageProvider
        storage_provider = get_storage_provider()
        file_path = storage_provider.get_file_path(object_key)
        
        if not file_path:
             # In a real S3 scenario, the provider might download it to a temp path here
             raise FileNotFoundError(f"Could not resolve path for {object_key}")

        # 3. Run ETL logic
        error_count = process_file_task(str(file_path), proposed_schema)
        
        update_file_status(file_id, "SUCCESS")
        return {
            "file_id": file_id, 
            "status": "SUCCESS", 
            "error_count": error_count
        }

    except Exception as e:
        logging.error(f"Task failed for file_id {file_id}: {e}")
        update_file_status(file_id, "FAILED")
        raise e
