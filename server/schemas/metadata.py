from pydantic import BaseModel
import uuid
from datetime import date

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
