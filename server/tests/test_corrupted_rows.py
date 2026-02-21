import requests
import os
import sys
import pytest

# Add the 'server' directory to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
server_dir = os.path.dirname(current_dir)
sys.path.insert(0, server_dir)

from core.deps import get_db
from core.database import Base, reflect_db
import crud

CORRUPTED_ROWS_TABLE = "corrupted_rows"
API_URL = "http://localhost:8000"

@pytest.fixture(scope="function")
def setup_corrupted_row():
    reflect_db()
    model_class = Base.classes.get(CORRUPTED_ROWS_TABLE)
    if not model_class:
        pytest.fail(f"Test setup failed: Could not find model for table '{CORRUPTED_ROWS_TABLE}'")

    db = next(get_db())
    new_item_data = {
        "target_table": "test_table",
        "row_id": "123",
        "error_reason": "Test corruption message"
    }

    created_item = None
    try:
        created_item = crud.create_item(db, model_class, new_item_data)
        db.commit()
        db.refresh(created_item)
        item_id = created_item.id
        yield item_id
    finally:
        if created_item:
            try:
                crud.delete_item(db, model_class, created_item.id)
                db.commit()
            except Exception as e:
                db.rollback()
                print(f"Error during teardown: {e}")
        db.close()

def test_create_corrupted_row():
    payload = {
        "target_table": "create_test_table",
        "row_id": "999",
        "error_reason": "Creation test message"
    }
    
    reflect_db()
    model_class = Base.classes.get(CORRUPTED_ROWS_TABLE)
    db = next(get_db())
    
    created_id = None
    try:
        r = requests.post(f"{API_URL}/api/corrupted_rows", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert data["target_table"] == payload["target_table"]
        assert data["error_reason"] == payload["error_reason"]
        created_id = data["id"]
    finally:
        if created_id:
            try:
                crud.delete_item(db, model_class, created_id)
                db.commit()
            except Exception as e:
                db.rollback()
        db.close()

def test_get_corrupted_rows(setup_corrupted_row):
    r = requests.get(f"{API_URL}/api/corrupted_rows")
    assert r.status_code == 200
    data = r.json()
    
    assert "data" in data
    assert "total" in data
    assert "page" in data
    assert "limit" in data
    assert isinstance(data["data"], list)
    assert data["total"] >= 1
    
    # Check if our setup item is in the list
    setup_id = setup_corrupted_row
    found = any(item["id"] == setup_id for item in data["data"])
    assert found

def test_delete_corrupted_row():
    # Setup
    reflect_db()
    model_class = Base.classes.get(CORRUPTED_ROWS_TABLE)
    db = next(get_db())
    new_item_data = {
        "target_table": "delete_test_table",
        "row_id": "456",
        "error_reason": "Delete test message"
    }
    created_item = crud.create_item(db, model_class, new_item_data)
    db.commit()
    db.refresh(created_item)
    item_id = created_item.id

    # Test
    r = requests.delete(f"{API_URL}/api/corrupted_rows/{item_id}")
    assert r.status_code == 200
    assert r.json()["message"] == "Corrupted row deleted successfully"

    # Verify deleted
    r_check = requests.get(f"{API_URL}/api/corrupted_rows")
    data = r_check.json()
    found = any(item["id"] == item_id for item in data["data"])
    assert not found
    db.close()
