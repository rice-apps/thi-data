from sqlalchemy.orm import Session
from sqlalchemy import select, inspect, func
from typing import Any, List, Dict
from fastapi import HTTPException


def model_to_dict(model_instance: Any) -> dict:
    """
    Helper function to convert a SQLAlchemy model instance to a dictionary.
    """
    mapper = inspect(model_instance.__class__)
    return {c.key: getattr(model_instance, c.key) for c in mapper.column_attrs}

def get_one_item(db: Session, model_class: Any, item_id: int):
    return db.get(model_class, item_id)

def get_all_items(db: Session, model_class: Any):
    return db.scalars(select(model_class)).all()

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