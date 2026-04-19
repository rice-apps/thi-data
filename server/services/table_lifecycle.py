"""Orchestration for destructive table operations (metadata, DLT tables, cache)."""

from __future__ import annotations

import logging
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.config import settings
from core.database import reflect_db
from core.deps import get_internal_model_class, get_file_registry_model, _repo_cache

logger = logging.getLogger(__name__)


def delete_user_table(db: Session, table_name: str) -> None:
    """
    Remove metadata rows, file_registry links, DLT clinical_data tables, then re-reflect.
    Caller must enforce visibility and existence checks.
    """
    dlt_schema = settings.DLT_DATASET
    MetadataCreation = get_internal_model_class("metadata_creation")
    MetadataUpdates = get_internal_model_class("metadata_updates")
    FileRegistry = get_file_registry_model()

    for record in (
        db.query(MetadataCreation).filter(MetadataCreation.table_name == table_name).all()
    ):
        db.query(MetadataUpdates).filter(MetadataUpdates.foreign_key == record.id).delete()
        db.delete(record)

    db.query(FileRegistry).filter(FileRegistry.target_table_name == table_name).delete()

    db.execute(text(f'DROP TABLE IF EXISTS {dlt_schema}."{table_name}"'))
    db.execute(text(f'DROP TABLE IF EXISTS {dlt_schema}."{table_name}__corrupted"'))

    db.commit()
    reflect_db()

    _repo_cache.pop(table_name, None)
    _repo_cache.pop(f"{table_name}__corrupted", None)
    logger.info("Deleted table %s and refreshed ORM reflection", table_name)
