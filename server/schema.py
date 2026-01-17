from typing import Optional
from pydantic import BaseModel
import uuid
from datetime import date

class Item(BaseModel):
    first_name: str
    last_name: str
    age: int

class UpdateItem(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    age: Optional[int] = None

class MetadataCreationRequest(BaseModel):
    created_by: str
    table_name: str

class MetadataUpdateRequest(BaseModel):
    foreign_key: uuid.UUID
    updated_by: str

class SearchCreatedByResponse(BaseModel):
    name: str

class FilterCreatedAtRequest(BaseModel):
    start_date: date
    end_date: date

class CorruptedRowCreate(BaseModel):
    target_table: str
    row_id: str
    error_reason: str | None = None

