import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.deps import get_db, get_internal_model_class
from services.corrupted_row_resolution import CorruptedRowResolutionService

router = APIRouter()
logger = logging.getLogger(__name__)


class ResolutionRequest(BaseModel):
    corrections: Dict[str, Any]


@router.patch("/api/{target_table}/{row_id}/resolve")
def resolve_corrupted_row(
    target_table: str,
    row_id: str,
    resolution: ResolutionRequest,
    db: Session = Depends(get_db),
):
    """
    Resolves a corrupted row by updating the primary record with corrected values.
    The sidecar JOIN in rows.py automatically unflags the column once the main
    table value is no longer NULL.
    """
    try:
        target_model = get_internal_model_class(target_table)
    except Exception:
        raise HTTPException(status_code=404, detail=f"Table '{target_table}' not found")

    try:
        svc = CorruptedRowResolutionService(db, target_model)
        return svc.resolve(
            row_id, resolution.corrections, table_name=target_table
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Validation Error: {str(e)}")
    except Exception as e:
        logger.error("Unexpected error during resolution: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=f"Validation Error: {str(e)}")
