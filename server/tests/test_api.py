import requests
import os
import sys
import pytest

# --- Imports for setup/teardown ---
# Add the 'server' directory to sys.path so we can import modules
current_dir = os.path.dirname(os.path.abspath(__file__))
server_dir = os.path.dirname(current_dir)
sys.path.insert(0, server_dir)

from core.deps import get_db, get_model_class
from core.database import Base, reflect_db
import crud

TABLE = "test_database" 
EXAMPLE_FIRST_NAME = "Jeff"
EXAMPLE_LAST_NAME = "Bezos"
EXAMPLE_AGE = 800
METADATA_CREATION_TABLE = "metadata_creation"
METADATA_UPDATE_TABLE = "metadata_updates"
API_URL = "http://localhost:8000"

@pytest.fixture(scope="function")
def setup_item():
    # --- 0. Load database models ---
    reflect_db() 
    model_class = Base.classes.get(TABLE)
    
    if not model_class:
        pytest.fail(f"Test setup failed: Could not find model for table '{TABLE}'")

    db = next(get_db())
    new_item_data = {
        "first_name": EXAMPLE_FIRST_NAME,
        "last_name": EXAMPLE_LAST_NAME,
        "age": EXAMPLE_AGE
    }

    created_item = None
    try:
        # --- 1. SETUP ---
        created_item = crud.create_item(db, model_class, new_item_data)
        db.commit()
        db.refresh(created_item)
        item_id = created_item.id
        
        yield item_id
    
    finally:
        # --- 2. TEARDOWN: Clean up the database ---
        if created_item:
            try:
                crud.delete_item(db, model_class, created_item.id)
                db.commit()
            except Exception as e:
                db.rollback()
                print(f"Error during test teardown: {e}")
        db.close()

@pytest.fixture(scope="function")
def setup_metadata_creation():
    # --- 0. Load database models ---
    reflect_db()
    model_class = Base.classes.get(METADATA_CREATION_TABLE)
    if not model_class:
        pytest.fail(f"Test setup failed: Could not find model for table '{METADATA_CREATION_TABLE}'")

    db = next(get_db())
    new_item_data = {
            "created_by": "fixture_tester",
            "table_name": "fixture_test_table"
        }
    created_item = None
    try:
        # --- 1. SETUP ---
        created_item = crud.create_item(db, model_class, new_item_data)
        db.commit()
        db.refresh(created_item)
        item_id = created_item.id
        
        yield item_id
    
    finally:
        # --- 2. TEARDOWN: Clean up the database ---
        if created_item:
            try:
                crud.delete_item(db, model_class, created_item.id)
                db.commit()
            except Exception as e:
                db.rollback()
                print(f"Error during metadata_creation fixture teardown: {e}")
        db.close()

def test_get_tables():
    r = requests.get(f"{API_URL}/api/tables")
    assert r.status_code == 200
    try:
        data = r.json()
    except requests.JSONDecodeError:
        assert False, "Response is not valid JSON"
    assert "tables" in data, "JSON response must contain a 'tables' key."
    assert isinstance(data["tables"], list), "The 'tables' key should contain a list."

def test_get_all_items():
    r = requests.get(f"{API_URL}/api/{TABLE}")
    assert r.status_code == 200
    try:
        data = r.json()
    except requests.JSONDecodeError:
        assert False, "Response is not valid JSON"
    # data format is now {"data": [...], "total": N, ...}
    assert isinstance(data, dict), "Response should be a dictionary (paginated)."
    assert "data" in data, "Response should contain 'data' key."
    items = data["data"]
    assert isinstance(items, list), "'data' should be a list."
    
    if items:
        item = items[0]
        assert isinstance(item, dict), "Each item should be a dictionary."
        for key in ["id", "first_name", "last_name", "age"]:
            assert key in item, f"Each item should contain the key '{key}'."

def test_create_item():
    new_item = {
        "first_name": EXAMPLE_FIRST_NAME,
        "last_name": EXAMPLE_LAST_NAME,
        "age": EXAMPLE_AGE
    }
    
    item_id = None
    
    reflect_db()
    model_class = get_model_class(TABLE)
    if not model_class:
        pytest.fail(f"Test setup failed: Could not find model for table '{TABLE}'")
    db = next(get_db())
    
    try:
        r = requests.post(f"{API_URL}/api/{TABLE}", json=new_item)
        assert r.status_code == 200
        try:
            data = r.json()
        except requests.JSONDecodeError:
            assert False, "Response is not valid JSON"
        
        item_id = data.get("id")

        assert isinstance(data, dict), "Response should be a dictionary."
        for key in ["id", "first_name", "last_name", "age"]:
            assert key in data, f"Response should contain the key '{key}'."
    finally:
        # Teardown: Clean up the item this test created
        if item_id:
            try:
                crud.delete_item(db, model_class, item_id)
                db.commit()
            except Exception as e:
                db.rollback()
                print(f"Error during test_create_item teardown: {e}")


def test_get_one_item(setup_item):
    item_id = setup_item
    r = requests.get(f"{API_URL}/api/{TABLE}/{item_id}")

    assert r.status_code == 200
    try:
        data = r.json()
    except requests.JSONDecodeError:
        assert False, "Response is not valid JSON"
    assert isinstance(data, dict), "Response should be a dictionary."
    for key in ["id", "first_name", "last_name", "age"]:
        assert key in data, f"Response should contain the key '{key}'."
    assert data["first_name"] == EXAMPLE_FIRST_NAME

def test_update_item(setup_item):
    item_id = setup_item
    updated_item_data = {
        "first_name": "Jeff",
        "last_name": "Bezos-Updated",
        "age": 900
    }
    r = requests.put(f"{API_URL}/api/{TABLE}/{item_id}",
                        json=updated_item_data)
    assert r.status_code == 200
    try:
        data = r.json()
    except requests.JSONDecodeError:
        assert False, "Response is not valid JSON"
    assert isinstance(data, dict), "Response should be a dictionary."
    for key in ["id", "first_name", "last_name", "age"]:
        assert key in data, f"Response should contain the key '{key}'."
    assert data["last_name"] == "Bezos-Updated"
    assert data["age"] == 900


def test_delete_item():
    # --- 1. Setup: Manually create an item to delete ---
    reflect_db()
    model_class = Base.classes.get(TABLE)

    if not model_class:
        pytest.fail(f"Test setup failed: Could not find model for table '{TABLE}'")
    db = next(get_db())
    new_item_data = {
        "first_name": "Item",
        "last_name": "To-Be-Deleted",
        "age": 123
    }
    created_item = None
    item_id = None

    try:
        created_item = crud.create_item(db, model_class, new_item_data)
        db.commit()
        db.refresh(created_item)
        item_id = created_item.id
    except Exception as e:
        db.rollback()
        db.close()
        pytest.fail(f"Test setup for test_delete_item failed: {e}")
    
    # --- 2. Run the test ---
    r = requests.delete(f"{API_URL}/api/{TABLE}/{item_id}")

    assert r.status_code == 200
    
    # Close setup session and open a fresh one to avoid isolation/caching issues
    db.close()
    db = next(get_db())

    item = crud.get_one_item(db, model_class, item_id)
    assert item is None
    db.close()

def test_metadata_creation():
    new_metadata = {
        "created_by": "tester",
        "table_name": "test_table"
    }
    r = requests.post(f"{API_URL}/api/metadata_creation", json=new_metadata)
    assert r.status_code == 200
    try:
        data = r.json()
    except requests.JSONDecodeError:
        assert False, "Response is not valid JSON"
    assert isinstance(data, dict), "Response should be a dictionary."
    for key in ["id", "created_by", "table_name"]:
        assert key in data, f"Response should contain the key '{key}'."

def test_metadata_update(setup_metadata_creation):
    creation_id = setup_metadata_creation
    
    new_metadata_update_data = {
        "updated_by": "tester",
        "foreign_key": str(creation_id)
    }
    
    update_item_id = None
    reflect_db()
    update_model_class = Base.classes.get(METADATA_UPDATE_TABLE)
    db = next(get_db())
    
    if not update_model_class:
        pytest.fail(f"Test setup failed: Could not find model for '{METADATA_UPDATE_TABLE}'")

    try:
        r = requests.post(f"{API_URL}/api/metadata_update", json=new_metadata_update_data)
        assert r.status_code == 200
        try:
            data = r.json()
        except requests.JSONDecodeError:
            assert False, "Response is not valid JSON"
        
        update_item_id = data.get("id")

        assert isinstance(data, dict), "Response should be a dictionary."
        for key in ["id", "updated_by", "foreign_key"]:
            assert key in data, f"Response should contain the key '{key}'."
        
        assert data["foreign_key"] == str(creation_id)
        assert data["updated_by"] == "tester"

    finally:
        if update_item_id:
            try:
                crud.delete_item(db, update_model_class, update_item_id)
                db.commit()
            except Exception as e:
                db.rollback()
                print(f"Error during test_metadata_update teardown: {e}")
        db.close()