"""File registry lookups and status transitions (API + Celery)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Union

from sqlalchemy import text
from sqlalchemy.orm import Session

from core.enums import FileStatus

if TYPE_CHECKING:
    from crud.base import BaseRepository


@dataclass(frozen=True)
class UploadContext:
    object_key: str
    target_table_name: str
    uploaded_by: str


def get_upload_context(
    db: Session, file_id: str, repo: Optional["BaseRepository"] = None
) -> UploadContext:
    from core.deps import get_file_registry_repo

    reg = repo or get_file_registry_repo()
    records = reg.get_by_field(db=db, field_name="file_id", value=file_id)
    if not records:
        raise LookupError("File not found in registry.")
    r = records[0]
    return UploadContext(
        object_key=r.object_key,
        target_table_name=r.target_table_name,
        uploaded_by=r.uploaded_by or "unknown",
    )


def update_file_status(
    file_id: str, status: Union[FileStatus, str], error_message: str = None
) -> None:
    from core.deps import get_db_context, get_file_registry_repo

    with get_db_context() as db:
        update_data: dict = {"status": status}
        if error_message:
            update_data["error_message"] = error_message

        get_file_registry_repo().update_by_field(
            db=db,
            search_field="file_id",
            search_value=file_id,
            update_data=update_data,
        )


def claim_file_for_processing(db: Session, file_id: str) -> int:
    """Set status to PROCESSING if file is SCHEMA_CONFIRMED or FAILED. Returns rowcount."""
    q = text(
        """
        UPDATE public.file_registry
        SET status = :processing, error_message = NULL
        WHERE file_id = CAST(:file_id AS uuid)
          AND (status = :s_confirmed OR status = :s_failed)
        """
    )
    return db.execute(
        q,
        {
            "processing": FileStatus.PROCESSING.value,
            "file_id": file_id,
            "s_confirmed": FileStatus.SCHEMA_CONFIRMED.value,
            "s_failed": FileStatus.FAILED.value,
        },
    ).rowcount
