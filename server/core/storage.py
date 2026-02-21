from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class StorageProvider(ABC):

    @abstractmethod
    def generate_presigned_url(self, object_key: str) -> str:
        pass

    @abstractmethod
    def upload_file(self, object_key: str, content: bytes) -> bool:
        pass

    @abstractmethod
    def get_file_path(self, object_key: str) -> Optional[Path]:
        """Resolve an object key to a local file path."""
        pass

    @abstractmethod
    def delete_file(self, object_key: str) -> bool:
        pass

    @abstractmethod
    def list_files(self, prefix: str = "") -> list[dict]:
        """List files in the storage provider."""
        pass
