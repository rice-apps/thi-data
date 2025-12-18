from sqlalchemy.orm import Session
from sqlalchemy import select, inspect, cast, String, func
from typing import Any, List, Dict, Tuple, Optional
from datetime import datetime

def model_to_dict(model_instance: Any) -> Dict[str, Any]:
    """Helper to convert SQLAlchemy model to dict"""
    return {c.key: getattr(model_instance, c.key) for c in inspect(model_instance).mapper.column_attrs}

def get_all_items(db: Session, model_class: Any, skip: int = 0, limit: int = 100) -> Tuple[List[Any], int]:
    """
    Returns a tuple: (list_of_items, total_count)
    """
    query = db.query(model_class)
    total = query.count()
    items = query.offset(skip).limit(limit).all()
    return items, total

def filter_text(db: Session, model_class: Any, column: str, text: str, skip: int = 0, limit: int = 100) -> Tuple[List[Any], int]:
    """
    Searches column for text, handling numeric columns via CAST.
    Returns a tuple: (list_of_items, total_count)
    """
    col = getattr(model_class, column)
    # Cast column to String so ILIKE works on Integers (Age, ID, etc.)
    search_filter = cast(col, String).ilike(f"%{text}%")
    
    query = db.query(model_class).filter(search_filter)
    total = query.count()
    items = query.offset(skip).limit(limit).all()
    
    return items, total

def get_one_item(db: Session, model_class: Any, item_id: int) -> Optional[Any]:
    return db.get(model_class, item_id)

def create_item(db: Session, model_class: Any, item_data: Dict[str, Any]) -> Any:
    try:
        new_item = model_class(**item_data)
        db.add(new_item)
        db.commit()
        db.refresh(new_item)
        return new_item
    except Exception as e:
        db.rollback()
        raise e

def delete_item(db: Session, model_class: Any, item_id: int) -> bool:
    item = db.get(model_class, item_id)
    if not item:
        return False
    
    db.delete(item)
    db.commit()
    return True

def update_item(db: Session, model_class: Any, item_id: int, item: Any) -> Any:
    try:
        db.add(item)
        db.commit()
        db.refresh(item)
        return item
    except Exception as e:
        db.rollback()
        raise e
    
def get_items_by_field(db: Session, model_class: Any, field_name: str, value: Any) -> List[Any]:
    """
    Generic filter by a single field (exact match).
    """
    column = getattr(model_class, field_name, None)
    if column is None:
        return []
    
    stmt = select(model_class).where(column == value)
    return db.execute(stmt).scalars().all()

def get_items_by_date_range(db: Session, model_class: Any, date_field: str, start: datetime, end: datetime) -> List[Any]:
    """
    Generic filter by date range.
    """
    column = getattr(model_class, date_field, None)
    if column is None:
        return []

    stmt = select(model_class).where(column.between(start, end))
    return db.execute(stmt).scalars().all()
