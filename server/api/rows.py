import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from core.deps import get_db, get_model_class
from services.dynamic_rows_service import DynamicRowsService

router = APIRouter()

logger = logging.getLogger(__name__)


@router.get("/api/{table_name}")
def get_all_items(
    table_name: str,
    skip: int = 0,
    limit: int = 100,
    model_class: Any = Depends(get_model_class),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    logger.info(f"Getting all items from table: {table_name} (skip={skip}, limit={limit})")
    svc = DynamicRowsService(db, model_class, table_name)
    return svc.list_page(skip, limit)


@router.post("/api/{table_name}")
def create_item(
    item_data: dict,
    table_name: str,
    x_user_name: Optional[str] = Header(None, alias="X-User-Name"),
    model_class: Any = Depends(get_model_class),
    db: Session = Depends(get_db),
) -> dict:
    logger.info(f"Creating item in table: {table_name}, user: {x_user_name or 'system'}")
    svc = DynamicRowsService(db, model_class, table_name)
    return svc.create(item_data, x_user_name or "system")


@router.get("/api/{table_name}/search/{column}/{match}")
def match_items(
    table_name: str,
    column: str,
    match: str,
    skip: int = 0,
    limit: int = 100,
    model_class: Any = Depends(get_model_class),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    logger.info(
        f"Searching table {table_name} for column '{column}' matching '{match}' "
        f"(skip={skip}, limit={limit})"
    )
    svc = DynamicRowsService(db, model_class, table_name)
    return svc.search(column, match, skip, limit)


@router.get("/api/{table_name}/{item_id}")
def get_one_item(
    table_name: str,
    item_id: str,
    model_class: Any = Depends(get_model_class),
    db: Session = Depends(get_db),
) -> dict:
    logger.info(f"Getting item {item_id} from table")
    svc = DynamicRowsService(db, model_class, table_name)
    return svc.get_one(item_id)


@router.put("/api/{table_name}/{item_id}")
def update_item(
    table_name: str,
    item_id: str,
    item_data: dict,
    x_user_name: Optional[str] = Header(None, alias="X-User-Name"),
    model_class: Any = Depends(get_model_class),
    db: Session = Depends(get_db),
) -> dict:
    logger.info(
        f"Updating item {item_id} in table: {table_name}, user: {x_user_name or 'system'}"
    )
    svc = DynamicRowsService(db, model_class, table_name)
    return svc.update(item_id, item_data, x_user_name or "system")


@router.delete("/api/{table_name}/{item_id}")
def delete_item(
    table_name: str,
    item_id: str,
    x_user_name: Optional[str] = Header(None, alias="X-User-Name"),
    model_class: Any = Depends(get_model_class),
    db: Session = Depends(get_db),
):
    logger.info(
        f"Deleting item {item_id} from table: {table_name}, user: {x_user_name or 'system'}"
    )
    svc = DynamicRowsService(db, model_class, table_name)
    return svc.delete(item_id, x_user_name or "system")
