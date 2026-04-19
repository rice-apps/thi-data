from typing import Any, Dict
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from schemas.metadata import MetadataCreationRequest, MetadataUpdateRequest
from core.deps import get_db, get_internal_model_class, get_repository
from datetime import date, datetime, time
from crud.base import model_to_dict
from services.metadata_api_helpers import paginated_model_rows
import logging

router = APIRouter()

logger = logging.getLogger(__name__)

METADATA_CREATION_TABLE = "metadata_creation"
METADATA_UPDATES_TABLE = "metadata_updates"


def get_metadata_creation_model():
    return get_internal_model_class(METADATA_CREATION_TABLE)


def get_metadata_updates_model():
    return get_internal_model_class(METADATA_UPDATES_TABLE)


@router.post("/api/metadata_creation", response_model=Dict[str, Any])
def metadata_creation(
    request_data: MetadataCreationRequest,
    model_class: Any = Depends(get_metadata_creation_model),
    db: Session = Depends(get_db),
):
    logger.info("Creating metadata creation record for table: %s", request_data.table_name)
    item_data = request_data.model_dump()
    repo = get_repository(model_class)
    new_item = repo.create(db, item_data)
    logger.info("Metadata creation record created successfully with id: %s", new_item.id)
    return model_to_dict(new_item)


@router.post("/api/metadata_update", response_model=Dict[str, Any])
def metadata_update(
    request_data: MetadataUpdateRequest,
    model_class: Any = Depends(get_metadata_updates_model),
    db: Session = Depends(get_db),
):
    logger.info("Creating metadata update record for foreign_key: %s", request_data.foreign_key)
    item_data = request_data.model_dump()
    repo = get_repository(model_class)
    new_item = repo.create(db, item_data)
    logger.info("Metadata update record created successfully with id: %s", new_item.id)
    return model_to_dict(new_item)


@router.get("/api/metadata_filters")
def metadata_filters_endpoint():
    logger.info("Metadata filters endpoint accessed")
    return {"message": "Metadata Filters Endpoint"}


@router.get("/api/search_created_by", response_model=Dict[str, Any])
def search_created_by(
    name: str = Query(...),
    skip: int = 0,
    limit: int = 100,
    model_class: Any = Depends(get_metadata_creation_model),
    db: Session = Depends(get_db),
):
    logger.info(
        "Searching metadata creation records by created_by: %s (skip=%s, limit=%s)",
        name,
        skip,
        limit,
    )
    repo = get_repository(model_class)
    results = repo.get_by_field(db, field_name="created_by", value=name)
    logger.info(
        "Found %s metadata creation records for created_by: %s",
        len(results),
        name,
    )
    return paginated_model_rows(results, skip, limit)


@router.get("/api/search_updated_by", response_model=Dict[str, Any])
def search_updated_by(
    name: str = Query(...),
    skip: int = 0,
    limit: int = 100,
    model_class: Any = Depends(get_metadata_updates_model),
    db: Session = Depends(get_db),
):
    logger.info(
        "Searching metadata update records by updated_by: %s (skip=%s, limit=%s)",
        name,
        skip,
        limit,
    )
    repo = get_repository(model_class)
    results = repo.get_by_field(db, field_name="updated_by", value=name)
    logger.info(
        "Found %s metadata update records for updated_by: %s",
        len(results),
        name,
    )
    return paginated_model_rows(results, skip, limit)


@router.get("/api/filter_created_at", response_model=Dict[str, Any])
def filter_created_at(
    start_date: date = Query(...),
    end_date: date = Query(...),
    skip: int = 0,
    limit: int = 100,
    model_class: Any = Depends(get_metadata_creation_model),
    db: Session = Depends(get_db),
):
    logger.info(
        "Filtering metadata creation records by created_at: %s to %s",
        start_date,
        end_date,
    )
    start_datetime = datetime.combine(start_date, time.min)
    end_datetime = datetime.combine(end_date, time.max)

    repo = get_repository(model_class)
    results, _total = repo.get_by_date_range(
        db, date_column="created_at", start_date=start_datetime, end_date=end_datetime
    )

    logger.info(
        "Found %s metadata creation records in date range",
        len(results),
    )
    return paginated_model_rows(results, skip, limit)


@router.get("/api/filter_updated_at", response_model=Dict[str, Any])
def filter_updated_at(
    start_date: date = Query(...),
    end_date: date = Query(...),
    skip: int = 0,
    limit: int = 100,
    model_class: Any = Depends(get_metadata_updates_model),
    db: Session = Depends(get_db),
):
    logger.info(
        "Filtering metadata update records by updated_at: %s to %s",
        start_date,
        end_date,
    )
    start_datetime = datetime.combine(start_date, time.min)
    end_datetime = datetime.combine(end_date, time.max)

    repo = get_repository(model_class)
    results, _total = repo.get_by_date_range(
        db, date_column="updated_at", start_date=start_datetime, end_date=end_datetime
    )

    logger.info(
        "Found %s metadata update records in date range",
        len(results),
    )
    return paginated_model_rows(results, skip, limit)
