import random
from pathlib import Path
from typing import Optional
from core.storage import StorageProvider


class FakeS3(StorageProvider):

    def __init__(self, test_files_dir="tests/test_validation_data"):
        self.fakeStorage = {} # Maps object_key to content
        self.base_path = Path.cwd() / test_files_dir

    def generate_presigned_url(self, object_key: str):
        return f"https://fake-s3-url.com/{object_key}"

    def upload_file(self, object_key, content):
        self.fakeStorage[object_key] = content
        return True

    def get_file_path(self, object_key: str) -> Optional[Path]:
        # 1) Uploaded files written by the API (e.g. "uploads/<uuid>-file.csv")
        file_path = Path.cwd() / object_key
        if file_path.exists():
            return file_path

        # 2) Fixture files used by tests
        file_path = self.base_path / object_key
        if file_path.exists():
            return file_path
        return None

    def delete_file(self, object_key):
        if object_key in self.fakeStorage:
            del self.fakeStorage[object_key]
            return True
        return False

    def list_files(self, prefix: str = "") -> list[dict]:
        results = []
        for key in self.fakeStorage.keys():
            if key.startswith(prefix):
                results.append({
                    "name": key,
                    "id": key,
                    "metadata": {"size": len(self.fakeStorage[key])}
                })
        return results



