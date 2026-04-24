"""Post-ETL success path: metadata row, storage cleanup, API refresh, NOTIFY."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Union

from core.deps import get_db_context, get_internal_model_class_raw
from core.enums import FileStatus
from core.storage import StorageProvider
from services.api_reflection_client import refresh_api_server_schema
from services.file_registry_workflow import UploadContext, update_file_status
from services.pg_notify_events import publish_thi_event

logger = logging.getLogger(__name__)


def record_metadata_creation(table_name: str, uploaded_by: str) -> None:
    try:
        MetadataCreation = get_internal_model_class_raw("metadata_creation")
        with get_db_context() as db:
            db.add(MetadataCreation(table_name=table_name, created_by=uploaded_by))
            db.flush()
        logger.info("metadata_creation record saved for %s", table_name)
    except Exception as meta_err:
        logger.error(
            "Failed to create metadata_creation record for %s: %s",
            table_name,
            meta_err,
            exc_info=True,
        )


def cleanup_uploaded_object(
    storage_provider: StorageProvider, object_key: str, file_path: Union[str, Path]
) -> None:
    try:
        storage_provider.delete_file(object_key)
        path = Path(file_path)
        if "/tmp/thi-storage" in str(path) and path.exists():
            path.unlink()
            logger.info("Cleaned up local file: %s", path)
    except Exception as cleanup_error:
        logger.warning("Storage cleanup failed: %s", cleanup_error)


def finalize_successful_etl(
    file_id: str,
    ctx: UploadContext,
    file_path: Union[str, Path],
    storage_provider: StorageProvider,
    error_count: int,
) -> dict[str, Any]:
    update_file_status(file_id, FileStatus.SUCCESS)
    record_metadata_creation(ctx.target_table_name, ctx.uploaded_by)
    cleanup_uploaded_object(storage_provider, ctx.object_key, file_path)
    refresh_api_server_schema()
    publish_thi_event(
        {
            "type": "celery_success",
            "file_id": file_id,
            "message": "Success",
        }
    )
    return {
        "file_id": file_id,
        "status": FileStatus.SUCCESS,
        "error_count": error_count,
    }
