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
import crud 

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

    created_record = crud.create_item(
        db = db,
        model_class = FileRegistry,
        data = {
            "file_id": file_id,
            "object_key": object_key,
            "status": "UPLOADED"
        },
    )
    
    yield file_id, object_key

    try:
        crud.delete_item_by_field(
            db=db,
            model_class=FileRegistry,
            field="file_id",
            value=file_id,
        )
    except Exception as e:
        print(f"Error cleaning up file record: {e}")
    db.close()

def test_update_file_registry():
    file_id, _ = setup_file_registry
    payload = {"status": "PROCESSED"}
    r = requests.patch(f"{API_URL}/{file_id}", json=payload)

    assert r.status_code == 200
    data = r.json()
    assert data["file_id"] == file_id
    assert data["updated_fields"]["status"] == "PROCESSED"

def test_delete_file_registry():
    file_id, _ = setup_file_registry
    r = requests.delete(f"{API_URL}/", params={"file_id": file_id})

    assert r.status_code == 200
    data = r.json()
    assert data["file_id"] == file_id
    assert data["status"] == "deleted"

    reflect_db()
    FileRegistry = Base.classes.get("file_registry")
    db = next(get_db())
    records = crud.get_items_by_field(db, FileRegistry, "file_id", file_id)
    db.close()
    assert len(records) == 0

def test_upload_file():
    test_file_path = os.path.join(current_dir, "test_file.txt")
    with open(test_file_path, "w") as f:
        f.write("This is a test file.")

    with open(test_file_path, "rb") as f:
        files = {"file": f}

    os.remove(test_file_path)

    assert r.status_code == 200
    data = r.json()
    assert "file_id" in data
    assert "object_key" in data
    assert data["status"] == "UPLOADED"
