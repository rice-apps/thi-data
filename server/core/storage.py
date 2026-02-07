from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class StorageProvider(ABC):

    @abstractmethod
    def generate_presigned_url(self) -> str:
        pass

    @abstractmethod
    def upload_file(self, url: str, file: bytes) -> bool:
        pass

    @abstractmethod
    def get_file_path(self, object_key: str) -> Optional[Path]:
        """Resolve an object key to a local file path."""
        pass

    @abstractmethod
    def delete_file(self, url: str) -> bool:
        pass
