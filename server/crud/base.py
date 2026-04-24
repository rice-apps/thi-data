from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import cast, String, inspect as sa_inspect
from core.database import Base

ModelType = TypeVar("ModelType", bound=Base)

def model_to_dict(obj: Any) -> Dict[str, Any]:
    """
    Convert a SQLAlchemy model instance to a dictionary.
    Handles nested objects and basic types.
    """
    if obj is None:
        return None
    
    # If it's a row object from a join
    if hasattr(obj, "_mapping"):
        return dict(obj._mapping)
        
    d = {}
    for column in obj.__table__.columns:
        value = getattr(obj, column.name)
        d[column.name] = value
    return d

class BaseRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType]):
        """
        Base class for repositories with default methods to Create, Read, Update, Delete (CRUD).
        """
        self.model = model
        mapper = sa_inspect(model)
        pk_cols = mapper.primary_key
        self._pk_attr = pk_cols[0].key if len(pk_cols) == 1 else None

    def _order_by_primary_key(self, query):
        mapper = sa_inspect(self.model)
        if not mapper.primary_key:
            return query
        for pk in mapper.primary_key:
            query = query.order_by(pk.asc())
        return query

    def get_by_id(self, db: Session, id: Any) -> Optional[ModelType]:
        pk_column = getattr(self.model, self._pk_attr)
        return db.query(self.model).filter(pk_column == id).first()

    def get_all(
        self, db: Session, *, skip: int = 0, limit: int = 100
    ) -> Tuple[List[ModelType], int]:
        total = db.query(self.model).count()
        q = self._order_by_primary_key(db.query(self.model))
        items = q.offset(skip).limit(limit).all()
        return items, total

    def get_by_field(self, db: Session, field_name: str, value: Any) -> List[ModelType]:
        return db.query(self.model).filter(getattr(self.model, field_name) == value).all()

    def create(self, db: Session, obj_in: Dict[str, Any]) -> ModelType:
        db_obj = self.model(**obj_in)
        db.add(db_obj)
        db.flush()
        db.refresh(db_obj)
        return db_obj

    def update(
        self,
        db: Session,
        *,
        db_obj: ModelType,
        obj_in: Union[Dict[str, Any], Any]
    ) -> ModelType:
        obj_data = model_to_dict(db_obj)
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = (
                obj_in.model_dump(exclude_unset=True)
                if hasattr(obj_in, "model_dump")
                else obj_in.dict(exclude_unset=True)
            )

        for field in obj_data:
            if field in update_data:
                setattr(db_obj, field, update_data[field])

        db.add(db_obj)
        db.flush()
        db.refresh(db_obj)
        return db_obj

    def delete(self, db: Session, id: Any) -> bool:
        obj = self.get_by_id(db, id)
        if obj:
            db.delete(obj)
            db.flush()
            return True
        return False

    def update_by_field(self, db: Session, search_field: str, search_value: Any, update_data: Dict[str, Any]) -> int:
        """
        Update multiple records matching a field value.
        """
        items = self.get_by_field(db, search_field, search_value)
        updated_count = 0
        for item in items:
            for key, value in update_data.items():
                if hasattr(item, key):
                    setattr(item, key, value)
            db.add(item)
            updated_count += 1

        if updated_count > 0:
            db.flush()
        return updated_count

    def delete_by_field(self, db: Session, field_name: str, value: Any) -> int:
        """
        Delete multiple records matching a field value.
        """
        items = self.get_by_field(db, field_name, value)
        deleted_count = 0
        for item in items:
            db.delete(item)
            deleted_count += 1

        if deleted_count > 0:
            db.flush()
        return deleted_count

    def get_by_date_range(
        self, db: Session, date_column: str, start_date: Any, end_date: Any
    ) -> Tuple[List[ModelType], int]:
        query = db.query(self.model).filter(
            getattr(self.model, date_column) >= start_date,
            getattr(self.model, date_column) <= end_date
        )
        total = query.count()
        return query.all(), total

    def filter_text(
        self, db: Session, column_name: str, match: str, skip: int = 0, limit: int = 100
    ) -> Tuple[List[ModelType], int]:
        column_attr = getattr(self.model, column_name)
        query = db.query(self.model).filter(
            cast(column_attr, String).ilike(f"%{match}%")
        )
        total = query.count()
        query = self._order_by_primary_key(query)
        items = query.offset(skip).limit(limit).all()
        return items, total
