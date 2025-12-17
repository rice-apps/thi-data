from typing import Any
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import inspect
from sqlalchemy.orm import Session
from database import reflect_db, Base
from api import metadata, tables, metadata_filters
from deps import get_db, get_model_class
import crud

origins = [
    "http://localhost:3000",
]

@asynccontextmanager
async def lifespan(app: FastAPI):
    reflect_db()
    yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Allows all methods
    allow_headers=["*"], # Allows all headers
)


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

app.include_router(metadata_filters.router)
app.include_router(metadata.router)
app.include_router(tables.router)

@app.get("/api/{table_name}")
def get_all_items(
    skip: int = 0,
    limit: int = 100,
    model_class: Any = Depends(get_model_class), 
    db: Session = Depends(get_db)
) -> dict[str, Any]:
    
    items, total = crud.get_all_items(db, model_class, skip=skip, limit=limit)
    
    return {
        "data": [crud.model_to_dict(item) for item in items],
        "total": total,
        "page": (skip // limit) + 1,
        "limit": limit
    }

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


@app.get("/api/{table_name}/search/{column}/{match}")
def match_items(
    column: str,
    match: str,
    skip: int = 0,
    limit: int = 100,
    model_class: Any = Depends(get_model_class), 
    db: Session = Depends(get_db)
) -> dict[str, Any]:
    try:
        results, total = crud.filter_text(db, model_class, column, match, skip=skip, limit=limit)
        
        return {
            "data": [crud.model_to_dict(item) for item in results],
            "total": total,
            "page": (skip // limit) + 1,
            "limit": limit
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error matching items: {e}")    

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



    