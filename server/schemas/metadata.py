from pydantic import BaseModel
import uuid
from datetime import date


class MetadataCreationRequest(BaseModel):
    """Schema for creating a metadata creation record."""
    created_by: str
    table_name: str


class MetadataUpdateRequest(BaseModel):
    """Schema for creating a metadata update record."""
    foreign_key: uuid.UUID
    updated_by: str


class FilterCreatedAtRequest(BaseModel):
    """Schema for filtering by date range."""
    start_date: date
    end_date: date
