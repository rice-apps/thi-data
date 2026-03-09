import os
import sys
import uuid
import pytest
import requests

current_dir = os.path.dirname(os.path.abspath(__file__))
server_dir = os.path.dirname(current_dir)
sys.path.insert(0, server_dir)

from core.deps import get_db
from core.database import Base, reflect_db
from core.enums import FileStatus
from crud.base import BaseRepository, model_to_dict

API_URL = "http://localhost:8000"
@pytest.fixture(scope="function")
def setup_file_registry():
    reflect_db()
    FileRegistry = Base.classes.get("file_registry")
    if not FileRegistry:
       pytest.fail("File registry not found in database.")

    db = next(get_db())
    file_id = str(uuid.uuid4())
    object_key = f"uploads/{file_id}-testfile.csv"

    created_record = BaseRepository(FileRegistry).create(db = db, obj_in = {
            "file_id": file_id,
            "object_key": object_key,
            "status": FileStatus.UPLOADED
        },
    )
    db.commit()
    
    yield file_id, object_key

    try:
        BaseRepository(FileRegistry).delete_by_field(
            db=db,
            field_name="file_id",
            value=file_id,
        )
        db.commit()
    except Exception as e:
        print(f"Error cleaning up file record: {e}")
    db.close()

def test_update_file_registry(setup_file_registry):
    file_id, _ = setup_file_registry
    payload = {"status": "PROCESSED"}
    r = requests.patch(f"{API_URL}/api/files/{file_id}", json=payload)

    assert r.status_code == 200
    data = r.json()
    assert data["file_id"] == file_id
    assert data["updated_fields"]["status"] == "PROCESSED"

def test_delete_file_registry(setup_file_registry):
    file_id, _ = setup_file_registry
    r = requests.delete(f"{API_URL}/api/files", params={"file_id": file_id})

    assert r.status_code == 200
    data = r.json()
    assert data["file_id"] == file_id
    assert data["status"] == FileStatus.DELETED

    reflect_db()
    FileRegistry = Base.classes.get("file_registry")
    db = next(get_db())
    records = BaseRepository(FileRegistry).get_by_field(db, field_name="file_id", value=file_id)
    db.close()
    assert len(records) == 0

def test_delete_file_verifies_storage_cleanup():
    """Upload a file, delete it, verify it's gone from storage listing."""
    test_file_path = os.path.join(current_dir, "test_cleanup.txt")
    with open(test_file_path, "w") as f:
        f.write("cleanup test file")

    try:
        # Upload
        with open(test_file_path, "rb") as f:
            files = {"file": ("test_cleanup.txt", f, "text/plain")}
            r = requests.post(f"{API_URL}/api/files/upload", files=files)

        if r.status_code != 200:
            pytest.skip(f"Upload failed: {r.status_code} {r.text}")

        file_id = r.json()["file_id"]
        object_key = r.json()["object_key"]

        # Delete
        r = requests.delete(f"{API_URL}/api/files", params={"file_id": file_id})
        assert r.status_code == 200

        # Verify gone from storage listing
        r = requests.get(f"{API_URL}/api/files")
        assert r.status_code == 200
        file_keys = [f.get("key", f.get("Key", "")) for f in r.json()]
        assert object_key not in file_keys
    finally:
        if os.path.exists(test_file_path):
            os.remove(test_file_path)


def test_upload_file():
    test_file_path = os.path.join(current_dir, "test_file.txt")
    with open(test_file_path, "w") as f:
        f.write("This is a test file.")

    try:
        with open(test_file_path, "rb") as f:
            files = {"file": ( "test_file.txt", f, "text/plain")}
            r = requests.post(f"{API_URL}/api/files/upload", files=files)

        if r.status_code != 200:
            print(f"DEBUG: upload failed with {r.status_code}: {r.text}")
        assert r.status_code == 200
        data = r.json()
        assert "file_id" in data
        assert "object_key" in data
        assert data["status"] == FileStatus.UPLOADED
    finally:
        if os.path.exists(test_file_path):
            os.remove(test_file_path)
