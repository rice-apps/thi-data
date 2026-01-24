from frictionless import describe 
from fastapi import APIRouter, HTTPException, Depends
from pathlib import Path
import crud
from core.deps import get_db
from sqlalchemy.orm import Session

router = APIRouter()

@router.post("/api/validate_schema")
def validate_schema(file_id: str, db: Session = Depends(get_db)):
    try:
        file_record = crud.get_items_by_field(db = db,
                                              model_class=db.Base.classes.get("file_registry"),
                                              field="file_id",
                                              value=file_id) 
        if not file_record:
            raise HTTPException(status_code = 404, detail="File ID not found in registry")
        
        record = file_record[0]
        object_key = record.object_key

        return crud.infer_from_file(object_key)

        # csv_path = Path(object_key)
        # if not csv_path.exists():
        #     raise HTTPException(status_code = 404, detail="File ID not found in storage")

    except HTTPException:
         crud.update_item_by_field(
             db = db,
             model_class=db.Base.classes.get("file_registry"),
             field="file_id",
             value=file_id,
             update_data={"status": "FRICTIONLESS_FAILED"})
         
    except Exception as e:
        raise HTTPException(status_code = 500, detail=f"Schema inference failed: {e}")