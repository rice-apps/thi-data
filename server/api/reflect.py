from fastapi import APIRouter, HTTPException, Query 
from core.database import reflect_db
import logging

router = APIRouter()

logger = logging.getLogger(__name__)

REFRESH_KEY = 'db_reflection_schema_refresh'

@router.post("/api/refresh")
def refresh_warehouse():
    logger.info("Initiating database reflection refresh...")
    try:
        reflect_db()
        logger.info("Database reflection completed successfully.")
    
        return {"status": "success", "message": "Database refreshed successfully."}
    except Exception as e:
        logger.error(f"Error during database reflection: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Failed to connect to database: {e}")