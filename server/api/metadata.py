from fastapi import APIRouter, HTTPException, Depends
import crud
from schema import MetadataCreationRequest, MetadataUpdateRequest
from sqlalchemy.orm import Session
from database import Base
from deps import get_db

router = APIRouter()
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