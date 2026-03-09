from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import inspect as sa_inspect, Integer, Float, Numeric, Boolean, DateTime, Date, BigInteger, SmallInteger
from core.deps import get_db, get_internal_model_class
from crud.base import model_to_dict
from datetime import datetime
import logging

router = APIRouter()

logger = logging.getLogger(__name__)


class ResolutionRequest(BaseModel):
    """Schema for resolving a corrupted row."""
    corrections: Dict[str, Any]


def _validate_and_cast(column_name: str, value: Any, column_type) -> Any:
    """
    Validate that `value` is castable to the SQLAlchemy `column_type`.
    Returns the cast value or raises ValueError on failure.
    """
    logger.debug(f"Validating column '{column_name}' with value '{value}' for type {column_type}")
    if value is None:
        return None

    if isinstance(column_type, (Integer, BigInteger, SmallInteger)):
        try:
            return int(value)
        except (ValueError, TypeError):
            logger.warning(f"Type validation failed for column '{column_name}': expected integer, got '{value}'")
            raise ValueError(f"Column '{column_name}' expects an integer, got '{value}'")

    if isinstance(column_type, (Float, Numeric)):
        try:
            return float(value)
        except (ValueError, TypeError):
            logger.warning(f"Type validation failed for column '{column_name}': expected number, got '{value}'")
            raise ValueError(f"Column '{column_name}' expects a number, got '{value}'")

    if isinstance(column_type, Boolean):
        if isinstance(value, bool):
            return value
        if str(value).lower() in ('true', '1', 'yes'):
            return True
        if str(value).lower() in ('false', '0', 'no'):
            return False
        logger.warning(f"Type validation failed for column '{column_name}': expected boolean, got '{value}'")
        raise ValueError(f"Column '{column_name}' expects a boolean, got '{value}'")

    if isinstance(column_type, DateTime):
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value))
        except (ValueError, TypeError):
            logger.warning(f"Type validation failed for column '{column_name}': expected datetime (ISO format), got '{value}'")
            raise ValueError(f"Column '{column_name}' expects a datetime (ISO format), got '{value}'")

    if isinstance(column_type, Date):
        try:
            return datetime.fromisoformat(str(value)).date()
        except (ValueError, TypeError):
            logger.warning(f"Type validation failed for column '{column_name}': expected date (ISO format), got '{value}'")
            raise ValueError(f"Column '{column_name}' expects a date (ISO format), got '{value}'")

    # For String/Text and other types, return as-is
    return value


@router.patch("/api/{target_table}/{row_id}/resolve")
def resolve_corrupted_row(
    target_table: str,
    row_id: str,
    resolution: ResolutionRequest,
    db: Session = Depends(get_db)
):
    """
    Resolves a corrupted row by updating the primary record with corrected values.
    The sidecar JOIN in rows.py automatically unflags the column once the main
    table value is no longer NULL.
    """
    logger.info(f"Starting resolution for corrupted row - table: {target_table}, row_id: {row_id}")
    logger.debug(f"Resolution corrections: {resolution.corrections}")

    try:
        TargetModel = get_internal_model_class(target_table)
    except Exception:
        raise HTTPException(status_code=404, detail=f"Table '{target_table}' not found")

    record = db.query(TargetModel).filter(TargetModel.id == row_id).first()

    if not record:
        logger.warning(f"Record not found - table: {target_table}, row_id: {row_id}")
        raise HTTPException(status_code=404, detail=f"Record {row_id} not found in {target_table}")

    logger.debug(f"Record found in {target_table} for row_id: {row_id}")

    # Get column type metadata for validation
    mapper = sa_inspect(TargetModel)
    column_types = {c.key: c.columns[0].type for c in mapper.column_attrs if c.columns}
    logger.debug(f"Retrieved column types for validation: {list(column_types.keys())}")

    try:
        for column, value in resolution.corrections.items():
            logger.debug(f"Processing correction for column '{column}' with value '{value}'")
            if not hasattr(record, column):
                logger.warning(f"Column '{column}' does not exist in table {target_table}")
                raise ValueError(f"Column '{column}' does not exist in {target_table}")

            # Type-validate and cast the value before setting
            col_type = column_types.get(column)
            if col_type:
                value = _validate_and_cast(column, value, col_type)

            setattr(record, column, value)
            logger.debug(f"Successfully set column '{column}' to value '{value}'")

        logger.info(f"All corrections applied successfully for row_id: {row_id}")
    except ValueError as e:
        logger.error(f"Validation error during resolution: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Validation Error: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error during correction application: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Validation Error: {str(e)}")

    db.flush()
    db.refresh(record)
    logger.info(f"Corrupted row resolved successfully - table: {target_table}, row_id: {row_id}")

    return model_to_dict(record)
