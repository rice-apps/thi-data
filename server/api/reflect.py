from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import create_engine
from sqlalchemy_dlock.factory import create_sadlock 
from core.database import Base
import logging

router = APIRouter()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(module)s:%(lineno)d -%(levelname)s - %(message)s"
)

REFRESH_KEY = 'db_reflection_schema_refresh'

@router.post("/api/refresh")
def refresh_warehouse( warehouse_url: str = Query(..., description="Database URL of the warehouse to reflect")):
    logging.info(f"Starting database reflection for warehouse: {warehouse_url}")
    try:
        logging.debug("Creating database engine")
        engine = create_engine(warehouse_url)
        conn = engine.connect()
        logging.info("Successfully connected to database")
    except Exception as e:
        logging.error(f"Failed to connect to database: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Failed to connect to database: {e}")

    lock = create_sadlock(conn, REFRESH_KEY)
    logging.debug(f"Created database lock for key: {REFRESH_KEY}")
    try:
        logging.info("Acquiring lock and starting database reflection")
        with lock:
            Base.prepare(autoload_with=engine, reflect=True)
        logging.info("Database reflection completed successfully")
    except Exception as e:
        logging.error(f"Failed to reflect the database: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Failed to reflect the DB: {e}")
    finally:
        conn.close()
        logging.debug("Database connection closed")

    return {"message": "Database reflection successful.", "tables": list(Base.classes.keys())}