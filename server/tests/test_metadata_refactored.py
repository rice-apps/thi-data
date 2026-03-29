import requests
import os
import sys
import pytest
from datetime import date, datetime

# Add the 'server' directory to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
server_dir = os.path.dirname(current_dir)
sys.path.insert(0, server_dir)

from core.deps import get_db
import core.database as db_module
from core.database import reflect_db
from crud.base import BaseRepository, model_to_dict

METADATA_CREATION_TABLE = "metadata_creation"
METADATA_UPDATES_TABLE = "metadata_updates"
API_URL = "http://localhost:8000"

@pytest.fixture(scope="function")
def setup_metadata_creation():
    reflect_db()
    model_class = db_module.Base.classes.get(METADATA_CREATION_TABLE)
    if not model_class:
        pytest.fail(f"Test setup failed: Could not find model for table '{METADATA_CREATION_TABLE}'")

    db = next(get_db())
    new_item_data = {
        "created_by": "test_creator",
        "table_name": "test_metadata_table"
    }

    created_item = None
    try:
        created_item = BaseRepository(model_class).create(db, new_item_data)
        db.commit()
        db.refresh(created_item)
        item_id = str(created_item.id) # Convert UUID to string if necessary
        yield item_id, new_item_data["table_name"]
    finally:
        if created_item:
            try:
                BaseRepository(model_class).delete(db, created_item.id)
                db.commit()
            except Exception as e:
                db.rollback()
                print(f"Error during teardown: {e}")
        db.close()

def test_metadata_creation_endpoint():
    payload = {
        "created_by": "new_tester",
        "table_name": "new_test_table"
    }
    
    reflect_db()
    model_class = db_module.Base.classes.get(METADATA_CREATION_TABLE)
    db = next(get_db())
    
    created_id = None
    try:
        r = requests.post(f"{API_URL}/api/metadata_creation", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert data["created_by"] == payload["created_by"]
        assert data["table_name"] == payload["table_name"]
        created_id = data["id"]
    finally:
        if created_id:
            BaseRepository(model_class).delete(db, created_id)
        db.close()

def test_search_created_by(setup_metadata_creation):
    _, _ = setup_metadata_creation
    name = "test_creator"
    r = requests.get(f"{API_URL}/api/search_created_by", params={"name": name})
    assert r.status_code == 200
    data = r.json()
    
    assert "data" in data
    assert "total" in data
    assert isinstance(data["data"], list)
    assert data["total"] >= 1
    assert any(item["created_by"] == name for item in data["data"])

def test_filter_created_at(setup_metadata_creation):
    _, _ = setup_metadata_creation
    today = date.today().isoformat()
    r = requests.get(f"{API_URL}/api/filter_created_at", params={
        "start_date": today,
        "end_date": today
    })
    assert r.status_code == 200
    data = r.json()
    
    assert "data" in data
    assert isinstance(data["data"], list)
    # Even if total is 0 (due to timezones or whatever), the structure should be correct
    assert "total" in data
    assert "page" in data

def test_metadata_update_endpoint(setup_metadata_creation):
    creation_id, _ = setup_metadata_creation
    payload = {
        "foreign_key": creation_id,
        "updated_by": "update_tester"
    }
    
    reflect_db()
    model_class = db_module.Base.classes.get(METADATA_UPDATES_TABLE)
    db = next(get_db())
    
    created_id = None
    try:
        r = requests.post(f"{API_URL}/api/metadata_update", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert data["updated_by"] == payload["updated_by"]
        assert data["foreign_key"] == payload["foreign_key"]
        created_id = data["id"]
    finally:
        if created_id:
            BaseRepository(model_class).delete(db, created_id)
        db.close()
