import random
from pathlib import Path
from typing import Optional
from core.storage import StorageProvider


class FakeS3(StorageProvider):

    def __init__(self, test_files_dir="tests/test_validation_data"):
        self.validURLs = set()
        self.fakeStorage = {}
        self.urlToObjectKey = {}
        self.base_path = Path.cwd() / test_files_dir

    def generate_presigned_url(self):
        random_number = random.randint(1000, 9999)
        url = f"https://fake-s3-url.com/{random_number}"
        self.validURLs.add(url)
        return url

    def upload_file(self, url, file):
        if url in self.validURLs:
            self.fakeStorage[url] = file
            return True
        return False

    def get_file_path(self, object_key: str) -> Optional[Path]:
        file_path = self.base_path / object_key
        if file_path.exists():
            return file_path
        return None

    def delete_file(self, url):
        if url in self.fakeStorage:
            del self.fakeStorage[url]
            return True
        return False



