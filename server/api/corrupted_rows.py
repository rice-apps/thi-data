from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import Session
from database import Base
from deps import get_db
import crud

router = APIRouter()

async def create_corrupted_row(row: CorruptedRowCreate, db: Session = Depends(get_db)):
    model_class = Base.classes.get("corrupted_rows")
    if not model_class:
        raise HTTPException(
            status_code=500, 
            detail="Configuration error: 'corrupted_rows' table not found"
        )
    try: 
        data = row.dict()
        new_item = crud.create_item(db, model_class, data)
        return crud.model_to_dict(new_item)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
async def get_corrupted_rows(db: Session = Depends(get_db)):
    model_class = Base.classes.get("corrupted_rows")
    if not model_class:
        raise HTTPException(
            status_code=500, 
            detail="Configuration error: 'corrupted_rows' table not found"
        )
    try: 
        items = crud.get_all_items(db, model_class)
        return [crud.model_to_dict(item) for item in items]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def delete_corrupted_rows(row_id: str, db: Session = Depends(get_db)):
    model_class = Base.classes.get("corrupted_rows")
    if not model_class:
        raise HTTPException(
            status_code=500, 
            detail="Configuration error: 'corrupted_rows' table not found"
        )
    try:
        deleted = crud.delete_item(db, model_class, row_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Row not found")
        return {"message": "Row deleted", "deleted": crud.model_to_dict(deleted)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))