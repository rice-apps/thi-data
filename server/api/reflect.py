from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import create_engine
from sqlalchemy_dlock.factory import create_sadlock 
from core.database import Base

router = APIRouter()

REFRESH_KEY = 'db_reflection_schema_refresh'

@router.post("/api/refresh")
def refresh_warehouse( warehouse_url: str = Query(..., description="Database URL of the warehouse to reflect")):
    try:
        engine = create_engine(warehouse_url)
        conn = engine.connect()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to connect to database: {e}")

    try:
        lock = create_sadlock(conn, REFRESH_KEY)
        lock.acquire()
        Base.prepare(autoload_with=engine, reflect=True)
        lock.release()
    except Exception as e:
        raise HTTPException(status_code=400,detail=f"Failed to reflect the DB: {e}")

    return {"message": "Database reflection successful.", "tables": list(Base.classes.keys())}