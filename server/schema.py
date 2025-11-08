from typing import Optional
from pydantic import BaseModel



class Item(BaseModel):
    first_name: str
    last_name: str
    age: int

class UpdateItem(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    age: Optional[int] = None