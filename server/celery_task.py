from celery import Celery
from celery.exceptions import MaxRetriesExceededError
from typing import Union

import core.config as config
from core.logging_config import configure_logging
from core.deps import (
    get_db_context,
    get_storage_provider,
    init_app_services,
)
from services.etl_processor import process_file as run_etl, ETLError
from services.etl_success_orchestration import finalize_successful_etl
from services.file_registry_workflow import get_upload_context, update_file_status
from services.pg_notify_events import publish_thi_event
from services.api_reflection_client import refresh_api_server_schema as _refresh_api_server
from core.enums import FileStatus
import logging

configure_logging()
logger = logging.getLogger(__name__)


def notify_frontend(event: dict, dsn: str = None) -> None:
    """Backward-compatible name for tests and callers."""
    publish_thi_event(event, dsn)


init_app_services()

app = Celery("tasks", broker=config.settings.BROKER_URL)


@app.task(bind=True, acks_late=True, max_retries=3)
def process_patient_file(self, file_id: str, proposed_schema: dict) -> dict:
    logger.info("Starting processing for file_id: %s", file_id)
    update_file_status(file_id, FileStatus.PROCESSING)

    try:
        try:
            with get_db_context() as db:
                ctx = get_upload_context(db, file_id)
        except LookupError:
            raise ValueError("File not found in registry.")

        storage_provider = get_storage_provider()
        file_path = storage_provider.get_file_path(ctx.object_key)

        if not file_path:
            raise FileNotFoundError(
                f"Could not resolve file path for object_key: {ctx.object_key}"
            )

        error_count = run_etl(
            str(file_path),
            proposed_schema,
            target_table_name=ctx.target_table_name,
        )

        return finalize_successful_etl(
            file_id,
            ctx,
            file_path,
            storage_provider,
            error_count,
        )

    except ETLError as e:
        logger.error("ETL error for file_id %s: %s", file_id, e)
        update_file_status(file_id, FileStatus.FAILED, error_message=str(e))
        try:
            publish_thi_event(
                {
                    "type": "celery_failed",
                    "file_id": file_id,
                    "message": "Processing failed",
                    "error": str(e),
                }
            )
        except Exception as notify_err:
            logger.warning("Failed to send failure event for %s: %s", file_id, notify_err)
        return {"file_id": file_id, "status": FileStatus.FAILED, "error": str(e)}

    except Exception as e:
        logger.error("Task failed for file_id %s: %s", file_id, e, exc_info=True)
        try:
            raise self.retry(
                exc=e,
                countdown=min(120, 2 ** self.request.retries),
            )
        except MaxRetriesExceededError:
            update_file_status(file_id, FileStatus.FAILED, error_message=str(e))
            try:
                publish_thi_event(
                    {
                        "type": "celery_failed",
                        "file_id": file_id,
                        "message": "Processing failed",
                        "error": str(e),
                    }
                )
            except Exception as notify_err:
                logger.warning(
                    "Failed to send failure event for %s: %s", file_id, notify_err
                )
            raise e
