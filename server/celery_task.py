from celery import Celery
from services.etl_processor import process_file_task
from typing import Union

import core.config as config
from core.deps import get_db_context, get_storage_provider, init_app_services
from core.database import Base
from core.enums import FileStatus
import crud
import logging
import psycopg2
import json
import requests as http_requests

# Standard service initialization for both API and Worker
init_app_services()

app = Celery('tasks', broker=config.settings.BROKER_URL)


def notify_frontend(event: dict) -> None:
    """Publish an event to Postgres LISTEN/NOTIFY channel for SSE clients."""
    conn = psycopg2.connect(config.settings.DLT_CREDENTIALS)
    try:
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        with conn.cursor() as cur:
            cur.execute("NOTIFY thi_events, %s;", (json.dumps(event),))
    finally:
        conn.close()


def _refresh_api_server(max_retries: int = 2) -> None:
    """Tell the API server to re-reflect the database schema.

    The Celery worker and API server run in different containers, each
    with their own in-memory Base.classes.  After ETL creates new tables
    the API server must re-reflect so it can serve the new data.  We
    achieve this with a simple HTTP POST.
    """
    url = f"{config.settings.API_SERVER_URL}/api/refresh"
    for attempt in range(max_retries):
        try:
            resp = http_requests.post(url, timeout=10)
            resp.raise_for_status()
            logging.info(f"API server schema refresh succeeded (attempt {attempt + 1})")
            return
        except Exception as e:
            logging.warning(f"API server refresh attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                raise RuntimeError(
                    f"API server refresh failed after {max_retries} attempts: {e}"
                )


def update_file_status(file_id: str, status: Union[FileStatus, str], error_message: str = None):
    """Update file status and error tracking in the registry database."""
    with get_db_context() as db:
        update_data = {"status": status}
        if error_message:
            update_data["error_message"] = error_message
        
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
    update_file_status(file_id, FileStatus.PROCESSING)

    try:
        # Get object key from registry
        with get_db_context() as db:
            records = crud.get_items_by_field(
                db=db,
                model_class=Base.classes.file_registry,
                field_name="file_id",
                value=file_id
            )
            if not records:
                raise ValueError(f"File ID {file_id} not found in registry")
            object_key = records[0].object_key

        # Get local file path via StorageProvider
        storage_provider = get_storage_provider()
        file_path = storage_provider.get_file_path(object_key)
        
        if not file_path:
             raise FileNotFoundError(f"Could not resolve path for {object_key}")

        # Run ETL logic
        error_count = process_file_task(str(file_path), proposed_schema)
        
        update_file_status(file_id, FileStatus.SUCCESS)

        # AUTO-CLEANUP: Only on success.
        try:
            # Delete from S3/SeaweedFS
            storage_provider.delete_file(object_key)
            
            # Delete the local temp download to save worker disk space
            if "/tmp/thi-storage" in str(file_path) and file_path.exists():
                file_path.unlink()
                logging.info(f"Cleaned up local file: {file_path}")
                
        except Exception as cleanup_error:
            logging.warning(f"Cleanup failed for {file_id}: {cleanup_error}")

        # Refresh API server schema BEFORE notifying frontend.
        # This ensures the new tables are visible when the frontend navigates.
        _refresh_api_server()

        notify_frontend({
                "type": "celery_success",
                "file_id": file_id,
                "message": "Success",
            })
        
        return {
            "file_id": file_id, 
            "status": FileStatus.SUCCESS, 
            "error_count": error_count
        }

    except Exception as e:
        logging.error(f"Task failed for file_id {file_id}: {e}")
        update_file_status(file_id, FileStatus.FAILED, error_message=str(e))
        try:
            notify_frontend({
                "type": "celery_failed",
                "file_id": file_id,
                "message": "Worker failed while processing file",
                "error": str(e),
            })
        except Exception as notify_err:
            logging.warning(f"Failed to send failure event for {file_id}: {notify_err}")
        raise e
