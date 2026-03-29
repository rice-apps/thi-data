import boto3
from botocore.client import Config
from pathlib import Path
from typing import Optional
import os
from .storage import StorageProvider

class S3StorageProvider(StorageProvider):
    def __init__(
        self, 
        endpoint_url: str, 
        access_key: str, 
        secret_key: str, 
        bucket_name: str,
        region_name: str = "us-east-1"
    ):
        self.bucket_name = bucket_name
        self.s3 = boto3.client(
            's3',
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version='s3v4'),
            region_name=region_name
        )
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self):
        """Create the bucket if it doesn't already exist."""
        try:
            self.s3.head_bucket(Bucket=self.bucket_name)
        except Exception:
            try:
                self.s3.create_bucket(Bucket=self.bucket_name)
            except Exception:
                pass

    def generate_presigned_url(self, object_key: str) -> str:
        return self.s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': self.bucket_name, 'Key': object_key},
            ExpiresIn=3600
        )

    def upload_file(self, object_key: str, content: bytes) -> bool:
        try:
            self.s3.put_object(Bucket=self.bucket_name, Key=object_key, Body=content)
            return True
        except Exception:
            return False

    def get_file_path(self, object_key: str) -> Optional[Path]:
        """
        In a real cloud S3 scenario, this would download to a temp file.
        For on-prem (like SeaweedFS/Minio), if there's a shared volume, 
        this could return the mount path. 
        As a default, we download to a temporary location.
        """
        temp_dir = Path("/tmp/thi-storage")
        temp_dir.mkdir(parents=True, exist_ok=True)
        local_path = temp_dir / object_key
        local_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            self.s3.download_file(self.bucket_name, object_key, str(local_path))
            return local_path
        except Exception:
            return None

    def delete_file(self, object_key: str) -> bool:
        try:
            self.s3.delete_object(Bucket=self.bucket_name, Key=object_key)
            return True
        except Exception:
            return False

    def list_files(self, prefix: str = "") -> list[dict]:
        try:
            response = self.s3.list_objects_v2(Bucket=self.bucket_name, Prefix=prefix)
            results = []
            for obj in response.get('Contents', []):
                results.append({
                    "name": obj['Key'],
                    "id": obj['Key'],
                    "metadata": {"size": obj['Size']}
                })
            return results
        except Exception:
            return []
