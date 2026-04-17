"""Append-only audit trail for table data changes (metadata_updates)."""

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.deps import get_internal_model_class

logger = logging.getLogger(__name__)


def record_table_data_change(
    db: Session, table_name: str, user_name: str = "system"
) -> None:
    """
    Record that rows in `table_name` were modified (create/update/delete).
    Swallows errors so the primary request still succeeds.
    """
    logger.debug(f"Logging metadata update for table: {table_name}, user: {user_name}")
    try:
        MetadataCreation = get_internal_model_class("metadata_creation")
        MetadataUpdates = get_internal_model_class("metadata_updates")

        stmt = select(MetadataCreation).where(MetadataCreation.table_name == table_name)
        creation_record = db.execute(stmt).scalars().first()

        creation_id = None
        if not creation_record:
            logger.debug(f"No creation record found for table {table_name}, creating one")
            try:
                new_creation = MetadataCreation(
                    table_name=table_name,
                    created_by="system",
                    created_at=datetime.now(),
                )
                db.add(new_creation)
                db.flush()
                creation_id = new_creation.id
                logger.debug(f"Created metadata_creation record with id: {creation_id}")
            except Exception as e:
                logger.error(f"Failed to auto-create metadata_creation record: {e}")
                return
        else:
            creation_id = creation_record.file_id
            logger.debug(f"Found existing creation record with id: {creation_id}")

        new_update = MetadataUpdates(
            foreign_key=creation_id,
            updated_by=user_name,
            updated_at=datetime.now(),
        )
        db.add(new_update)
        db.flush()
        logger.debug(f"Metadata update logged successfully for table: {table_name}")

    except Exception as e:
        logger.error(f"Failed to log metadata update: {e}")


# Backward-compatible name for callers/tests
log_metadata_update = record_table_data_change
