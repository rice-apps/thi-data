from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from schemas.metadata import MetadataCreationRequest, MetadataUpdateRequest
from core.deps import get_db, get_internal_model_class
from datetime import date, datetime, time
import crud
from frictionless import describe
import tempfile
import os
from core.supabase import supabase

router = APIRouter()

# Constants
METADATA_CREATION_TABLE = "metadata_creation"
METADATA_UPDATES_TABLE = "metadata_updates"


def get_metadata_creation_model():
    """Dependency to get the metadata_creation model class."""
    return get_internal_model_class(METADATA_CREATION_TABLE)


def get_metadata_updates_model():
    """Dependency to get the metadata_updates model class."""
    return get_internal_model_class(METADATA_UPDATES_TABLE)


# --- Writes ---

@router.post("/api/metadata_creation", response_model=Dict[str, Any])
def metadata_creation(
    request_data: MetadataCreationRequest,
    model_class: Any = Depends(get_metadata_creation_model),
    db: Session = Depends(get_db)
):
    """Create a new metadata creation record."""
    item_data = request_data.model_dump()
    try:
        new_item = crud.create_item(db, model_class, item_data)
        return crud.model_to_dict(new_item)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error creating item: {e}")


@router.post("/api/metadata_update", response_model=Dict[str, Any])
def metadata_update(
    request_data: MetadataUpdateRequest,
    model_class: Any = Depends(get_metadata_updates_model),
    db: Session = Depends(get_db)
):
    """Create a new metadata update record."""
    item_data = request_data.model_dump()
    try:
        new_item = crud.create_item(db, model_class, item_data)
        return crud.model_to_dict(new_item)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error creating item: {e}")


# --- Reads / Filters ---

@router.get("/api/metadata_filters")
def metadata_filters_endpoint():
    """Placeholder for metadata filters endpoint."""
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
    results = crud.get_items_by_field(db, model_class, "created_by", name)
    total = len(results)
    paginated = results[skip:skip + limit]

    return {
        "data": [crud.model_to_dict(item) for item in paginated],
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
    results = crud.get_items_by_field(db, model_class, "updated_by", name)
    total = len(results)
    paginated = results[skip:skip + limit]

    return {
        "data": [crud.model_to_dict(item) for item in paginated],
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
    start_datetime = datetime.combine(start_date, time.min)
    end_datetime = datetime.combine(end_date, time.max)

    results = crud.get_items_by_date_range(
        db, model_class, "created_at", start_datetime, end_datetime
    )

    total = len(results)
    paginated = results[skip:skip + limit]

    return {
        "data": [crud.model_to_dict(item) for item in paginated],
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
    start_datetime = datetime.combine(start_date, time.min)
    end_datetime = datetime.combine(end_date, time.max)

    results = crud.get_items_by_date_range(
        db, model_class, "updated_at", start_datetime, end_datetime
    )

    total = len(results)
    paginated = results[skip:skip + limit]

    return {
        "data": [crud.model_to_dict(item) for item in paginated],
        "total": total,
        "page": (skip // limit) + 1 if limit > 0 else 1,
        "limit": limit
    }

@router.post("/api/validate_schema")
def validate_schema(file_id: str = Query(...)):
    """
    Infer schema for an uploaded file using Frictionless.
    """

    res = (
        supabase
        .table("file_registry")
        .select("*")
        .eq("id", file_id)
        .single()
        .execute()
    )

    if not res.data:
        raise HTTPException(status_code=404, detail="File not found")

    file_record = res.data
    object_key = file_record["object_key"]

    file_bytes = supabase.storage.from_("files").download(object_key)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        resource = describe(tmp_path)
        schema = resource.get("schema", {})
    finally:
        os.remove(tmp_path)

    return {
        "schema": schema
    }