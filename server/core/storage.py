from abc import ABC, abstractmethod
from typing import Optional


class StorageProvider(ABC):

    @abstractmethod
    def generatePresignedURL(self) -> str:
        pass

    @abstractmethod
    def storeFile(self, url: str, file: bytes) -> bool:
        pass

    @abstractmethod
    def retrieveFile(self, url: str) -> Optional[bytes]:
        pass

    @abstractmethod
    def deleteFile(self, url: str) -> bool:
        pass
