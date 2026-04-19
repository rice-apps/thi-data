"""Apply user corrections to main-table rows (corruption resolution)."""

from __future__ import annotations

import logging
from typing import Any, Dict

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session

from crud.base import model_to_dict
from services.reflected_columns import column_types_by_key, coerce_value_for_column

logger = logging.getLogger(__name__)


class CorruptedRowResolutionService:
    def __init__(self, db: Session, target_model: Any):
        self._db = db
        self._model = target_model

    def resolve(
        self, row_id: str, corrections: Dict[str, Any], *, table_name: str
    ) -> dict:
        """
        Validate and apply corrections. Raises LookupError if row missing.
        Raises ValueError for invalid columns or coercion failures.
        """
        mapper = sa_inspect(self._model)
        pk_col = mapper.primary_key[0]
        pk_attr = getattr(self._model, pk_col.key)
        record = self._db.query(self._model).filter(pk_attr == row_id).first()

        if not record:
            logger.warning("Record not found for row_id=%s", row_id)
            raise LookupError(f"Record {row_id} not found in {table_name}")

        column_types = column_types_by_key(mapper)
        logger.debug("Column keys for coercion: %s", list(column_types.keys()))

        for column, value in corrections.items():
            logger.debug("Correction column=%r value=%r", column, value)
            if not hasattr(record, column):
                logger.warning("Column %r does not exist on model", column)
                raise ValueError(f"Column '{column}' does not exist in {table_name}")

            col_type = column_types.get(column)
            if col_type:
                value = coerce_value_for_column(column, value, col_type)

            setattr(record, column, value)
            logger.debug("Set column %r OK", column)

        self._db.flush()
        self._db.refresh(record)
        logger.info("Resolved corrupted row row_id=%s", row_id)
        return model_to_dict(record)
