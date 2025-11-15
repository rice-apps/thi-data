from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import select, inspect
from pydantic import BaseModel
import uuid
import crud

from typing import Any, List
from database import SessionLocal, Base, reflect_db

app = FastAPI()

class MetadataCreationRequest(BaseModel):
    created_by: str
    table_name: str

class MetadataUpdateRequest(BaseModel):
    foreign_key: uuid.UUID
    updated_by: str

origins = [
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Allows all methods
    allow_headers=["*"], # Allows all headers
)

@app.on_event("startup")
def on_startup():
    reflect_db()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_model_class(table_name: str):
    """
    FastAPI dependency to get the SQLAlchemy model class from a table name.
    """
    model_class = Base.classes.get(table_name)
    if not model_class:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found.")
    return model_class


# --- API Endpoints ---

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get("/api/tables")
def get_all_tables():
    """
    Get a list of all table names reflected from the database.
    """
    return {"tables": list(Base.classes.keys())}

@app.post("/api/metadata_creation")
def metadata_creation(request_data: MetadataCreationRequest, db: Session = Depends(get_db)):
    model_class = Base.classes.get("metadata_creation")
    if not model_class:
        raise HTTPException(
            status_code=500, 
            detail="Configuration error: 'metadata_creation' table not found."
        )
    item_data = request_data.dict()
    try:
        new_item = crud.create_item(db, model_class, item_data)
        return crud.model_to_dict(new_item)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error creating item: {e}")

@app.post("/api/metadata_update")
def metadata_update(request_data: MetadataUpdateRequest, db: Session = Depends(get_db)):
    model_class = Base.classes.get("metadata_updates")
    if not model_class:
        raise HTTPException(
            status_code=500, 
            detail="Configuration error: 'metadata_updates' table not found."
        )
    item_data = request_data.dict()
    try:
        new_item = crud.create_item(db, model_class, item_data)
        return crud.model_to_dict(new_item)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error creating item: {e}")
    

@app.get("/api/{table_name}")
def get_all_items(
    model_class: Any = Depends(get_model_class), 
    db: Session = Depends(get_db)
) -> List[dict]:
    """
    Get all items from a specified table.
    """
    items = crud.get_all_items(db, model_class)
    return [crud.model_to_dict(item) for item in items]

@app.post("/api/{table_name}")
def create_item(
    item_data: dict, 
    model_class: Any = Depends(get_model_class), 
    db: Session = Depends(get_db)
) -> dict:
    """
    Create a new item in a specified table.
    Validation is based on the table's columns, not a Pydantic schema.
    """
    mapper = inspect(model_class)
    valid_keys = {c.key for c in mapper.column_attrs}
    
    # --- Dynamic Validation ---
    for key in item_data:
        if key not in valid_keys:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid field: '{key}'. Valid fields are: {list(valid_keys)}"
            )
            
    try:
        new_item = crud.create_item(db, model_class, item_data)
        return crud.model_to_dict(new_item)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error creating item: {e}")


@app.get("/api/{table_name}/{item_id}")
def get_one_item(
    item_id: int, 
    model_class: Any = Depends(get_model_class), 
    db: Session = Depends(get_db)
) -> dict:
    """
    Get a single item by its ID from a specified table.
    (Note: Assumes an integer primary key)
    """
    item = crud.get_one_item(db, model_class, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return crud.model_to_dict(item)

@app.put("/api/{table_name}/{item_id}")
def update_item(
    item_id: int,
    item_data: dict, 
    model_class: Any = Depends(get_model_class), 
    db: Session = Depends(get_db)
) -> dict:
    """
    Update an item in a specified table.
    Validation is based on the table's columns.
    """
    item = crud.get_one_item(db, model_class, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    mapper = inspect(model_class)
    valid_keys = {c.key for c in mapper.column_attrs}
    pk_keys = {c.key for c in mapper.primary_key}

    for key, value in item_data.items():
        if key not in valid_keys:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid field: '{key}'. Valid fields are: {list(valid_keys)}"
            )
        if key in pk_keys:
            raise HTTPException(
                status_code=400, 
                detail=f"Cannot update primary key field: '{key}'"
            )
        setattr(item, key, value)
    
    try:
        new_item = crud.update_item(db, model_class, item_id, item)
        return crud.model_to_dict(new_item)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error updating item: {e}")


@app.delete("/api/{table_name}/{item_id}")
def delete_item(
    item_id: int, 
    model_class: Any = Depends(get_model_class), 
    db: Session = Depends(get_db)
):
    """
    Delete an item by its ID from a specified table.
    """
    crud.delete_item(db, model_class, item_id)
    return {"message": "Item deleted successfully"}