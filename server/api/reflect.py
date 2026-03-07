from fastapi import APIRouter, HTTPException, Query 
from core.database import reflect_db

router = APIRouter()

REFRESH_KEY = 'db_reflection_schema_refresh'


@router.post("/api/refresh")
def refresh_warehouse( warehouse_url: str = Query(..., description="Database URL of the warehouse to reflect")):
    try:
        reflect_db()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to connect to database: {e}")
    
    
