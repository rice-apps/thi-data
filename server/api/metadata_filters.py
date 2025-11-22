from fastapi import APIRouter, HTTPException, Depends
import crud
from schema import SearchCreatedByResponse, FilterCreatedAtRequest
from sqlalchemy.orm import Session
from database import Base
from deps import get_db
from sqlalchemy import select
from datetime import datetime, time

router = APIRouter()


 #--- Filter Database Metadata ---
@router.get("/api/metadata_filters")
def metadata_filters():
    return {"message": "Metadata Filters Endpoint"}

@router.get("/api/search_created_by")
def search_created_by(request: SearchCreatedByResponse, db: Session = Depends(get_db)):
    model_class = Base.classes.get("metadata_creation")
    if not model_class:
        raise HTTPException(
            status_code=500, 
            detail="Configuration error: 'metadata_creation' table not found."
        )
    stmt = select(model_class).where(model_class.created_by == request.name)
    results = db.execute(stmt).scalars().all()
    return [crud.model_to_dict(item) for item in results]

@router.get("/api/search_updated_by")
def search_updated_by(request: SearchCreatedByResponse, db: Session = Depends(get_db)):
    model_class = Base.classes.get("metadata_updates")
    if not model_class:
        raise HTTPException(
            status_code=500, 
            detail="Configuration error: 'metadata_updates' table not found."
        )
    stmt = select(model_class).where(model_class.updated_by == request.name)
    results = db.execute(stmt).scalars().all()
    return [crud.model_to_dict(item) for item in results]


@router.get("/api/filter_created_at")
def filter_created_at(request: FilterCreatedAtRequest, db: Session = Depends(get_db)):
    model_class = Base.classes.get("metadata_creation")
    if not model_class:
        raise HTTPException(
            status_code=500, 
            detail="Configuration error: 'metadata_creation' table not found."
        )
    
    start_datetime = datetime.combine(request.start_date, time.min)
    end_datetime = datetime.combine(request.end_date, time.max)
    stmt = select(model_class).where(
        model_class.created_at.between(start_datetime, end_datetime)
    )
    results = db.execute(stmt).scalars().all()
    return [crud.model_to_dict(item) for item in results]

@router.get("/api/filter_updated_at")
def filter_updated_at(request: FilterCreatedAtRequest, db: Session = Depends(get_db)):
    model_class = Base.classes.get("metadata_updates")
    if not model_class:
        raise HTTPException(
            status_code=500, 
            detail="Configuration error: 'metadata_updates' table not found."
        )
    
    start_datetime = datetime.combine(request.start_date, time.min)
    end_datetime = datetime.combine(request.end_date, time.max)
    stmt = select(model_class).where(
        model_class.updated_at.between(start_datetime, end_datetime)
    )
    results = db.execute(stmt).scalars().all()
    return [crud.model_to_dict(item) for item in results]
