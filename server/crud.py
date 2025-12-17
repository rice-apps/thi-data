from sqlalchemy.orm import Session
from sqlalchemy import select, inspect, cast, String, func
from typing import Any, List, Dict
from fastapi import HTTPException

def model_to_dict(model_instance):
    """Helper to convert SQLAlchemy model to dict"""
    return {c.key: getattr(model_instance, c.key) for c in inspect(model_instance).mapper.column_attrs}

# def get_all_items(db: Session, model_class: Any):
#     """
#     Returns a tuple: (list_of_items, total_count)
#     """
#     query = db.query(model_class)
#     total = query.count() # Get total before slicing
#     items = query.all()
#     return items, total

def get_all_items(db: Session, model_class: Any, skip: int = 0, limit: int = 100):
    """
    Returns a tuple: (list_of_items, total_count)
    """
    query = db.query(model_class)
    total = query.count() # Get total before slicing
    items = query.offset(skip).limit(limit).all()
    return items, total

def filter_text(db: Session, model_class: Any, column: str, text: str, skip: int = 0, limit: int = 100):
    """
    Searches column for text, handling numeric columns via CAST.
    Returns a tuple: (list_of_items, total_count)
    """
    col = getattr(model_class, column)
    
    # FIX: Cast column to String so ILIKE works on Integers (Age, ID, etc.)
    search_filter = cast(col, String).ilike(f"%{text}%")
    
    query = db.query(model_class).filter(search_filter)
    
    total = query.count() # Get total matches before slicing
    items = query.offset(skip).limit(limit).all()
    
    return items, total

def get_one_item(db: Session, model_class: Any, item_id: int):
    return db.get(model_class, item_id)

def create_item(db: Session, model_class: Any, item_data: Dict[str, Any]):
    try:
        new_item = model_class(**item_data)
        db.add(new_item)
        db.commit()
        db.refresh(new_item)
        return new_item
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error creating item: {e}")


def delete_item(db: Session, model_class: Any, item_id: int):

    item = db.get(model_class, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    db.delete(item)
    db.commit()

def update_item(db: Session, model_class: Any, item_id: int, item):
    try:
        db.add(item)
        db.commit()
        db.refresh(item)
        return item
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error updating item: {e}")
    
def get_database_size(name: str, db: Session) -> Any:
    """
    Get the size of the entire database in a human-readable format.
    """

    stmt = select(
        func.pg_size_pretty(
            func.pg_total_relation_size(name)
        )
    )

    try:
        size = db.execute(stmt).scalar()
        if size is None:
             raise HTTPException(status_code=404, detail="Table not found")

        return {"table": name, "size": size}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error getting database size: {e}")