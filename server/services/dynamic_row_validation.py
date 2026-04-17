"""Validate dynamic table write payloads against reflected SQLAlchemy models."""

import logging
from typing import Any, Set

from fastapi import HTTPException
from sqlalchemy import inspect

logger = logging.getLogger(__name__)


def column_keys(model_class: Any) -> Set[str]:
    return {c.key for c in inspect(model_class).column_attrs}


def primary_key_keys(model_class: Any) -> Set[str]:
    return {c.key for c in inspect(model_class).primary_key}


def validate_create_payload(item_data: dict, model_class: Any, table_name: str) -> None:
    valid_keys = column_keys(model_class)
    for key in item_data:
        if key not in valid_keys:
            logger.warning(f"Invalid field '{key}' provided for table {table_name}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid field: '{key}'. Valid fields are: {list(valid_keys)}",
            )


def validate_update_payload(item_data: dict, model_class: Any, table_name: str) -> None:
    valid_keys = column_keys(model_class)
    pk_keys = primary_key_keys(model_class)
    for key, value in item_data.items():
        if key not in valid_keys:
            logger.warning(
                f"Invalid field '{key}' provided for update in table {table_name}"
            )
            raise HTTPException(status_code=400, detail=f"Invalid field: '{key}'")
        if key in pk_keys:
            logger.warning(
                f"Attempt to update primary key field '{key}' in table {table_name}"
            )
            raise HTTPException(
                status_code=400, detail=f"Cannot update primary key field: '{key}'"
            )
