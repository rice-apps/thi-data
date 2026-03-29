from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from schemas.metadata import MetadataCreationRequest, MetadataUpdateRequest
from core.deps import get_db, get_internal_model_class, get_repository
from datetime import date, datetime, time
from crud.base import model_to_dict
from frictionless import describe
import tempfile
import os
import logging

router = APIRouter()

logger = logging.getLogger(__name__)

# Constants
METADATA_CREATION_TABLE = "metadata_creation"
METADATA_UPDATES_TABLE = "metadata_updates"


def get_metadata_creation_model():
    """Dependency to get the metadata_creation model class."""
    return get_internal_model_class(METADATA_CREATION_TABLE)


def get_metadata_updates_model():
    """Dependency to get the metadata_updates model class."""
    return get_internal_model_class(METADATA_UPDATES_TABLE)



@router.post("/api/metadata_creation", response_model=Dict[str, Any])
def metadata_creation(
    request_data: MetadataCreationRequest,
    model_class: Any = Depends(get_metadata_creation_model),
    db: Session = Depends(get_db)
):
    """Create a new metadata creation record."""
    logger.info(f"Creating metadata creation record for table: {request_data.table_name}")
    item_data = request_data.model_dump()
    repo = get_repository(model_class)
    new_item = repo.create(db, item_data)
    logger.info(f"Metadata creation record created successfully with id: {new_item.id}")
    return model_to_dict(new_item)


@router.post("/api/metadata_update", response_model=Dict[str, Any])
def metadata_update(
    request_data: MetadataUpdateRequest,
    model_class: Any = Depends(get_metadata_updates_model),
    db: Session = Depends(get_db)
):
    """Create a new metadata update record."""
    logger.info(f"Creating metadata update record for foreign_key: {request_data.foreign_key}")
    item_data = request_data.model_dump()
    repo = get_repository(model_class)
    new_item = repo.create(db, item_data)
    logger.info(f"Metadata update record created successfully with id: {new_item.id}")
    return model_to_dict(new_item)



@router.get("/api/metadata_filters")
def metadata_filters_endpoint():
    """Placeholder for metadata filters endpoint."""
    logger.info("Metadata filters endpoint accessed")
    return {"message": "Metadata Filters Endpoint"}


@router.get("/api/search_created_by", response_model=Dict[str, Any])
def search_created_by(
    name: str = Query(...),
    skip: int = 0,
    limit: int = 100,
    model_class: Any = Depends(get_metadata_creation_model),
    db: Session = Depends(get_db)
):
    """Search metadata creation records by creator name."""
    logger.info(f"Searching metadata creation records by created_by: {name} (skip={skip}, limit={limit})")
    repo = get_repository(model_class)
    results = repo.get_by_field(db, field_name="created_by", value=name)
    total = len(results)
    paginated = results[skip:skip + limit]
    logger.info(f"Found {total} metadata creation records for created_by: {name}, returning {len(paginated)} results")

    return {
        "data": [model_to_dict(item) for item in paginated],
        "total": total,
        "page": (skip // limit) + 1 if limit > 0 else 1,
        "limit": limit
    }


@router.get("/api/search_updated_by", response_model=Dict[str, Any])
def search_updated_by(
    name: str = Query(...),
    skip: int = 0,
    limit: int = 100,
    model_class: Any = Depends(get_metadata_updates_model),
    db: Session = Depends(get_db)
):
    """Search metadata update records by updater name."""
    logger.info(f"Searching metadata update records by updated_by: {name} (skip={skip}, limit={limit})")
    repo = get_repository(model_class)
    results = repo.get_by_field(db, field_name="updated_by", value=name)
    total = len(results)
    paginated = results[skip:skip + limit]

    logger.info(f"Found {total} metadata update records for updated_by: {name}, returning {len(paginated)} results")
    return {
        "data": [model_to_dict(item) for item in paginated],
        "total": total,
        "page": (skip // limit) + 1 if limit > 0 else 1,
        "limit": limit
    }


@router.get("/api/filter_created_at", response_model=Dict[str, Any])
def filter_created_at(
    start_date: date = Query(...),
    end_date: date = Query(...),
    skip: int = 0,
    limit: int = 100,
    model_class: Any = Depends(get_metadata_creation_model),
    db: Session = Depends(get_db)
):
    """Filter metadata creation records by date range."""
    logger.info(f"Filtering metadata creation records by created_at: {start_date} to {end_date} (skip={skip}, limit={limit})")
    start_datetime = datetime.combine(start_date, time.min)
    end_datetime = datetime.combine(end_date, time.max)

    repo = get_repository(model_class)
    results, _total = repo.get_by_date_range(
        db, date_column="created_at", start_date=start_datetime, end_date=end_datetime
    )

    total = len(results)
    paginated = results[skip:skip + limit]
    logger.info(f"Found {total} metadata creation records in date range, returning {len(paginated)} results")

    return {
        "data": [model_to_dict(item) for item in paginated],
        "total": total,
        "page": (skip // limit) + 1 if limit > 0 else 1,
        "limit": limit
    }


@router.get("/api/filter_updated_at", response_model=Dict[str, Any])
def filter_updated_at(
    start_date: date = Query(...),
    end_date: date = Query(...),
    skip: int = 0,
    limit: int = 100,
    model_class: Any = Depends(get_metadata_updates_model),
    db: Session = Depends(get_db)
):
    """Filter metadata update records by date range."""
    logger.info(f"Filtering metadata update records by updated_at: {start_date} to {end_date} (skip={skip}, limit={limit})")
    start_datetime = datetime.combine(start_date, time.min)
    end_datetime = datetime.combine(end_date, time.max)

    repo = get_repository(model_class)
    results, _total = repo.get_by_date_range(
        db, date_column="updated_at", start_date=start_datetime, end_date=end_datetime
    )

    total = len(results)
    paginated = results[skip:skip + limit]

    logger.info(f"Found {total} metadata update records in date range, returning {len(paginated)} results")
    return {
        "data": [model_to_dict(item) for item in paginated],
        "total": total,
        "page": (skip // limit) + 1 if limit > 0 else 1,
        "limit": limit
    }