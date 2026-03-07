from fastapi import APIRouter, HTTPException, Query 
from core.database import reflect_db
import logging

router = APIRouter()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

REFRESH_KEY = 'db_reflection_schema_refresh'

@router.post("/api/refresh")
def refresh_warehouse():
    logging.info("Initiating database reflection refresh...")
    try:
        reflect_db()
        logging.info("Database reflection completed successfully.")
    
        return {"status": "success", "message": "Database refreshed successfully."}
    except Exception as e:
        logging.error(f"Error during database reflection: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Failed to connect to database: {e}")