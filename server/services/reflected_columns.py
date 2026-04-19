"""SQLAlchemy reflection helpers: API display labels and value coercion."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, List

from sqlalchemy import types as satypes
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapper

logger = logging.getLogger(__name__)

_HIDDEN_KEYS = frozenset({"original_csv_row_id", "id"})


def unwrap_sqlalchemy_type(sqlatype: Any) -> Any:
    impl = getattr(sqlatype, "impl", None)
    if impl is not None and impl is not sqlatype:
        return unwrap_sqlalchemy_type(impl)
    return sqlatype


def sqlalchemy_type_display(sqlatype: Any) -> str:
    """Map reflected SQLAlchemy types to short labels aligned with the schema editor."""
    if sqlatype is None:
        return "Other"
    sqlatype = unwrap_sqlalchemy_type(sqlatype)
    if isinstance(sqlatype, satypes.Boolean):
        return "Boolean"
    if isinstance(sqlatype, (satypes.Integer, satypes.SmallInteger, satypes.BigInteger)):
        return "Integer"
    if isinstance(
        sqlatype,
        (satypes.String, satypes.Text, satypes.CHAR, satypes.Unicode, satypes.UnicodeText),
    ):
        return "String"
    if isinstance(sqlatype, (satypes.Float, satypes.Double, satypes.REAL)):
        return "Decimal"
    if isinstance(sqlatype, satypes.Numeric):
        return "Decimal"
    if isinstance(sqlatype, satypes.Date):
        return "Date"
    if isinstance(sqlatype, satypes.DateTime):
        return "Timestamp"
    if isinstance(sqlatype, satypes.LargeBinary):
        return "Binary"
    if isinstance(sqlatype, satypes.Interval):
        return "Interval"
    if isinstance(sqlatype, (postgresql.JSON, postgresql.JSONB)):
        return "JSON"
    if isinstance(sqlatype, postgresql.UUID):
        return "UUID"
    if isinstance(sqlatype, satypes.ARRAY):
        return "Array"
    name = type(sqlatype).__name__
    return name if name else "Other"


def schema_columns_for_table(mapper: Mapper) -> List[dict]:
    """Visible columns for GET /api/schema: name + display type."""
    out: List[dict] = []
    for c in mapper.column_attrs:
        if c.key in _HIDDEN_KEYS:
            continue
        if not c.columns:
            continue
        sqlatype = c.columns[0].type
        out.append({"name": c.key, "type": sqlalchemy_type_display(sqlatype)})
    return out


def column_types_by_key(mapper: Mapper) -> dict[str, Any]:
    return {c.key: c.columns[0].type for c in mapper.column_attrs if c.columns}


def coerce_value_for_column(column_name: str, value: Any, column_type: Any) -> Any:
    """
    Cast API/input values to values suitable for SQLAlchemy column assignment.
    Raises ValueError on failure.
    """
    logger.debug(
        "Coercing column %r value %r for type %s",
        column_name,
        value,
        column_type,
    )
    if value is None:
        return None

    col = unwrap_sqlalchemy_type(column_type)

    if isinstance(col, (satypes.Integer, satypes.SmallInteger, satypes.BigInteger)):
        try:
            return int(value)
        except (ValueError, TypeError):
            logger.warning(
                "Integer coercion failed for column %r: got %r", column_name, value
            )
            raise ValueError(
                f"Column '{column_name}' expects an integer, got '{value}'"
            ) from None

    if isinstance(col, (satypes.Float, satypes.Numeric, satypes.REAL)):
        try:
            return float(value)
        except (ValueError, TypeError):
            logger.warning(
                "Numeric coercion failed for column %r: got %r", column_name, value
            )
            raise ValueError(
                f"Column '{column_name}' expects a number, got '{value}'"
            ) from None

    if isinstance(col, satypes.Boolean):
        if isinstance(value, bool):
            return value
        if str(value).lower() in ("true", "1", "yes"):
            return True
        if str(value).lower() in ("false", "0", "no"):
            return False
        logger.warning(
            "Boolean coercion failed for column %r: got %r", column_name, value
        )
        raise ValueError(
            f"Column '{column_name}' expects a boolean, got '{value}'"
        ) from None

    if isinstance(col, satypes.DateTime):
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value))
        except (ValueError, TypeError):
            logger.warning(
                "DateTime coercion failed for column %r: got %r", column_name, value
            )
            raise ValueError(
                f"Column '{column_name}' expects a datetime (ISO format), got '{value}'"
            ) from None

    if isinstance(col, satypes.Date):
        try:
            return datetime.fromisoformat(str(value)).date()
        except (ValueError, TypeError):
            logger.warning(
                "Date coercion failed for column %r: got %r", column_name, value
            )
            raise ValueError(
                f"Column '{column_name}' expects a date (ISO format), got '{value}'"
            ) from None

    return value
