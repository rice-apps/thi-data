# server/services/storage_interface.py
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

class StorageService(ABC):
    """Abstract interface for file storage."""
    
    @abstractmethod
    def get_file_path(self, object_key: str) -> Optional[Path]:
        pass