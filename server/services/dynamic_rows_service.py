"""Orchestration for CRUD on reflected dynamic tables (DLT + public)."""

import logging
from typing import Any, Dict

from fastapi import HTTPException
from sqlalchemy.orm import Session

from core.database import is_dlt_table
from core.deps import get_repository
from crud.base import model_to_dict
from services.dynamic_row_validation import (
    validate_create_payload,
    validate_update_payload,
)
from services.metadata_audit import record_table_data_change
from services.pagination import paginated_dict
from services.row_corruption import (
    RowCorruptionFacade,
    fetch_merged_page_or_none,
    serialize_main_rows,
)

logger = logging.getLogger(__name__)


class DynamicRowsService:
    """Per-request service: one instance per (db, model_class, table_name)."""

    def __init__(self, db: Session, model_class: Any, table_name: str):
        self.db = db
        self.model_class = model_class
        self.table_name = table_name

    def list_page(self, skip: int, limit: int) -> Dict[str, Any]:
        merged = fetch_merged_page_or_none(
            self.db, self.model_class, self.table_name, skip, limit
        )
        if merged is not None:
            data, total = merged
            logger.info(
                f"Retrieved {len(data)} items from {self.table_name}, total: {total}"
            )
            return paginated_dict(data, total, skip, limit)

        repo = get_repository(self.model_class)
        items, total = repo.get_all(self.db, skip=skip, limit=limit)
        logger.info(
            f"Retrieved {len(items)} items from {self.table_name}, total: {total}"
        )
        data = [model_to_dict(item) for item in items]
        return paginated_dict(data, total, skip, limit)

    def search(self, column: str, match: str, skip: int, limit: int) -> Dict[str, Any]:
        try:
            repo = get_repository(self.model_class)
            results, total = repo.filter_text(
                self.db, column, match, skip=skip, limit=limit
            )
            logger.info(
                f"Found {total} matching items, returning {len(results)} results"
            )
            data = serialize_main_rows(
                self.db, self.model_class, self.table_name, results
            )
            return paginated_dict(data, total, skip, limit)
        except Exception as e:
            logger.error(
                f"Error matching items in column {column}: {str(e)}", exc_info=True
            )
            raise HTTPException(
                status_code=400, detail="Search failed. Please try a different query."
            )

    def get_one(self, item_id: str) -> dict:
        repo = get_repository(self.model_class)
        item = repo.get_by_id(self.db, item_id)
        if not item:
            logger.warning(f"Item {item_id} not found")
            raise HTTPException(status_code=404, detail="Item not found")
        logger.info(f"Item {item_id} retrieved successfully")
        merged = serialize_main_rows(self.db, self.model_class, self.table_name, [item])
        return merged[0]

    def create(self, item_data: dict, user_name: str) -> dict:
        item_data = dict(item_data)
        item_data.pop("id", None)
        validate_create_payload(item_data, self.model_class, self.table_name)
        try:
            repo = get_repository(self.model_class)
            new_item = repo.create(self.db, item_data)
            record_table_data_change(self.db, self.table_name, user_name=user_name)
            logger.info(
                f"Item created successfully in table {self.table_name} with id: {new_item.id}"
            )
            return model_to_dict(new_item)
        except Exception as e:
            logger.error(
                f"Error creating item in table {self.table_name}: {str(e)}",
                exc_info=True,
            )
            raise HTTPException(
                status_code=400,
                detail="Could not create the row. Please check your input values.",
            )

    def update(self, item_id: str, item_data: dict, user_name: str) -> dict:
        repo = get_repository(self.model_class)
        item = repo.get_by_id(self.db, item_id)
        if not item:
            logger.warning(f"Item {item_id} not found in table {self.table_name}")
            raise HTTPException(status_code=404, detail="Item not found")

        validate_update_payload(item_data, self.model_class, self.table_name)

        try:
            new_item = repo.update(db=self.db, db_obj=item, obj_in=item_data)
            record_table_data_change(self.db, self.table_name, user_name=user_name)

            if is_dlt_table(self.model_class) and hasattr(
                new_item, "original_csv_row_id"
            ):
                RowCorruptionFacade(
                    self.db, self.model_class, self.table_name
                ).delete_sidecar_for_original_id(
                    new_item.original_csv_row_id,
                    log_context=f"update {item_id}:",
                )

            logger.info(
                f"Item {item_id} updated successfully in table {self.table_name}"
            )
            return serialize_main_rows(
                self.db, self.model_class, self.table_name, [new_item]
            )[0]
        except Exception as e:
            logger.error(
                f"Error updating item {item_id} in table {self.table_name}: {str(e)}",
                exc_info=True,
            )
            raise HTTPException(
                status_code=400,
                detail="Could not update the row. Please check your input values.",
            )

    def delete(self, item_id: str, user_name: str) -> Dict[str, str]:
        repo = get_repository(self.model_class)
        item = repo.get_by_id(self.db, item_id)
        if not item:
            logger.warning(f"Item {item_id} not found in table {self.table_name}")
            raise HTTPException(status_code=404, detail="Item not found")

        row_id_to_cleanup = getattr(item, "original_csv_row_id", None)
        is_dlt = is_dlt_table(self.model_class)

        success = repo.delete(self.db, item_id)
        if not success:
            logger.warning(f"Item {item_id} not found in table {self.table_name}")
            raise HTTPException(status_code=404, detail="Item not found")

        if is_dlt and row_id_to_cleanup is not None:
            RowCorruptionFacade(
                self.db, self.model_class, self.table_name
            ).delete_sidecar_for_original_id(
                row_id_to_cleanup,
                log_context=f"delete {item_id}:",
            )

        record_table_data_change(self.db, self.table_name, user_name=user_name)
        logger.info(f"Item {item_id} deleted successfully from table {self.table_name}")
        return {"message": "Item deleted successfully"}
