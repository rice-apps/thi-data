"""File registry transitions used by the HTTP API and Celery handoff."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from core.enums import FileStatus


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
