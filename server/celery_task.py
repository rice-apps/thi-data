from celery import Celery
from typing import Union

import core.config as config
from core.deps import get_db_context, get_storage_provider, get_file_registry_repo, init_app_services, get_internal_model_class_raw
from services.etl_processor import process_file as run_etl, ETLError
from core.enums import FileStatus
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)
import psycopg2
import json
import requests as http_requests

# Standard service initialization for both API and Worker
init_app_services()

app = Celery('tasks', broker=config.settings.BROKER_URL)



def notify_frontend(event: dict, dsn: str = config.settings.DLT_CREDENTIALS) -> None:
    """Publish an event to Postgres LISTEN/NOTIFY channel for SSE clients."""
    conn = psycopg2.connect(dsn)
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
            logger.info(f"API server schema refresh succeeded (attempt {attempt + 1})")
            return
        except Exception as e:
            logger.warning(f"API server refresh attempt {attempt + 1} failed: {e}")
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
        
        get_file_registry_repo().update_by_field(
            db=db,
            search_field="file_id",
            search_value=file_id,
            update_data=update_data
        )

@app.task(bind=True, acks_late=True, retry_backoff=True, max_retries=3)
def process_patient_file(self, file_id: str, proposed_schema: dict) -> dict:
    """
    Celery task to process a patient data file.
    """
    logger.info(f"Starting processing for file_id: {file_id}")
    update_file_status(file_id, FileStatus.PROCESSING)

    try:
        # Get object key, target table name, and uploader from registry
        with get_db_context() as db:
            records = get_file_registry_repo().get_by_field(
                db=db,
                field_name="file_id",
                value=file_id
            )
            if not records:
                raise ETLError(f"File not found in registry.")
            object_key = records[0].object_key
            target_table_name = records[0].target_table_name
            uploaded_by = records[0].uploaded_by or "unknown"

        # Get local file path via StorageProvider
        storage_provider = get_storage_provider()
        file_path = storage_provider.get_file_path(object_key)

        if not file_path:
            raise ETLError("The uploaded file could not be found. Please try uploading again.")

        # Run ETL logic
        error_count = run_etl(str(file_path), proposed_schema, target_table_name=target_table_name)

        update_file_status(file_id, FileStatus.SUCCESS)

        # Record who uploaded the file so the frontend can display "Uploaded By" / dates
        try:
            MetadataCreation = get_internal_model_class_raw("metadata_creation")
            with get_db_context() as db:
                db.add(MetadataCreation(table_name=target_table_name, created_by=uploaded_by))
                db.flush()
            logger.info(f"metadata_creation record saved for {target_table_name}")
        except Exception as meta_err:
            logger.error(
                f"Failed to create metadata_creation record for {target_table_name}: {meta_err}",
                exc_info=True,
            )

        # AUTO-CLEANUP: Only on success.
        try:
            # Delete from S3/SeaweedFS
            storage_provider.delete_file(object_key)

            # Delete the local temp download to save worker disk space
            if "/tmp/thi-storage" in str(file_path) and file_path.exists():
                file_path.unlink()
                logger.info(f"Cleaned up local file: {file_path}")

        except Exception as cleanup_error:
            logger.warning(f"Cleanup failed for {file_id}: {cleanup_error}")

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

    except ETLError as e:
        # Non-retryable: bad file, schema mismatch, etc. — fail immediately.
        logger.error(f"ETL error for file_id {file_id}: {e}")
        update_file_status(file_id, FileStatus.FAILED, error_message=str(e))
        try:
            notify_frontend({
                "type": "celery_failed",
                "file_id": file_id,
                "message": "Processing failed",
                "error": str(e),
            })
        except Exception as notify_err:
            logging.warning(f"Failed to send failure event for {file_id}: {notify_err}")
        return {"file_id": file_id, "status": FileStatus.FAILED, "error": str(e)}

    except Exception as e:
        # Potentially transient (network, DB connection) — retry with backoff.
        logger.error(f"Task failed for file_id {file_id}: {e}", exc_info=True)
        update_file_status(file_id, FileStatus.FAILED, error_message=str(e))
        try:
            notify_frontend({
                "type": "celery_failed",
                "file_id": file_id,
                "message": "Processing failed",
                "error": "An unexpected error occurred while processing the file. Retrying...",
            })
        except Exception as notify_err:
            logging.warning(f"Failed to send failure event for {file_id}: {notify_err}")
        raise self.retry(exc=e)
