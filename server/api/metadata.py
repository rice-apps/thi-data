from fastapi import APIRouter, HTTPException, Depends, Query
import crud
from schemas.metadata import MetadataCreationRequest, MetadataUpdateRequest
from sqlalchemy.orm import Session
from core.database import Base
from core.deps import get_db
from datetime import date, datetime, time

router = APIRouter()

# --- Writes ---

@router.post("/api/metadata_creation")
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

@router.post("/api/metadata_update")
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

# --- Reads / Filters ---

@router.get("/api/metadata_filters")
def metadata_filters_endpoint():
    return {"message": "Metadata Filters Endpoint"}

@router.get("/api/search_created_by")
def search_created_by(name: str = Query(...), db: Session = Depends(get_db)):
    model_class = Base.classes.get("metadata_creation")
    if not model_class:
        raise HTTPException(status_code=500, detail="Configuration error: 'metadata_creation' table not found.")
    
    results = crud.get_items_by_field(db, model_class, "created_by", name)
    return [crud.model_to_dict(item) for item in results]

@router.get("/api/search_updated_by")
def search_updated_by(name: str = Query(...), db: Session = Depends(get_db)):
    model_class = Base.classes.get("metadata_updates")
    if not model_class:
        raise HTTPException(status_code=500, detail="Configuration error: 'metadata_updates' table not found.")
        
    results = crud.get_items_by_field(db, model_class, "updated_by", name)
    return [crud.model_to_dict(item) for item in results]

@router.get("/api/filter_created_at")
def filter_created_at(
    start_date: date = Query(...), 
    end_date: date = Query(...), 
    db: Session = Depends(get_db)
):
    model_class = Base.classes.get("metadata_creation")
    if not model_class:
        raise HTTPException(status_code=500, detail="Configuration error: 'metadata_creation' table not found.")
    
    start_datetime = datetime.combine(start_date, time.min)
    end_datetime = datetime.combine(end_date, time.max)
    
    results = crud.get_items_by_date_range(db, model_class, "created_at", start_datetime, end_datetime)
    return [crud.model_to_dict(item) for item in results]

@router.get("/api/filter_updated_at")
def filter_updated_at(
    start_date: date = Query(...), 
    end_date: date = Query(...), 
    db: Session = Depends(get_db)
):
    model_class = Base.classes.get("metadata_updates")
    if not model_class:
        raise HTTPException(status_code=500, detail="Configuration error: 'metadata_updates' table not found.")
    
    start_datetime = datetime.combine(start_date, time.min)
    end_datetime = datetime.combine(end_date, time.max)
    
    results = crud.get_items_by_date_range(db, model_class, "updated_at", start_datetime, end_datetime)
    return [crud.model_to_dict(item) for item in results]