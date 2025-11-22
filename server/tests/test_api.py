import requests
import os
import sys
import pytest

# --- Imports for setup/teardown ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir) 

from deps import get_db, get_model_class
import crud
from database import Base, reflect_db

TABLE = "test_database" 
EXAMPLE_FIRST_NAME = "Jeff"
EXAMPLE_LAST_NAME = "Bezos"
EXAMPLE_AGE = 800
METADATA_CREATION_TABLE = "metadata_creation"
METADATA_UPDATE_TABLE = "metadata_updates"

@pytest.fixture(scope="function")
def setup_item():
    # --- 0. Load database models ---
    # Base.classes is populated
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
        item_id = created_item.id
        
        yield item_id
    
    finally:
        # --- 2. TEARDOWN: Clean up the database ---
        if created_item:
            try:
                crud.delete_item(db, model_class, created_item.id)
            except Exception as e:
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
        item_id = created_item.id
        
        yield item_id
    
    finally:
        # --- 2. TEARDOWN: Clean up the database ---
        if created_item:
            try:
                crud.delete_item(db, model_class, created_item.id)
            except Exception as e:
                print(f"Error during metadata_creation fixture teardown: {e}")
        db.close()

def test_get_tables():
    r = requests.get("http://localhost:8000/api/tables")
    assert r.status_code == 200
    try:
        data = r.json()
    except requests.JSONDecodeError:
        assert False, "Response is not valid JSON"
    assert "tables" in data, "JSON response must contain a 'tables' key."

    assert isinstance(data["tables"], list), "The 'tables' key should contain a list."

def test_get_all_items():
    r = requests.get(f"http://localhost:8000/api/{TABLE}")
    assert r.status_code == 200
    try:
        data = r.json()
    except requests.JSONDecodeError:
        assert False, "Response is not valid JSON"
    assert isinstance(data, list), "Response should be a list of items."
    for item in data:
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
        r = requests.post(f"http://localhost:8000/api/{TABLE}", json=new_item)
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
            except Exception as e:
                print(f"Error during test_create_item teardown: {e}")


def test_get_one_item(setup_item):
    item_id = setup_item
    r = requests.get(f"http://localhost:8000/api/{TABLE}/{item_id}")

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
    r = requests.put(f"http://localhost:8000/api/{TABLE}/{item_id}",
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
        item_id = created_item.id
    except Exception as e:
        db.close()
        pytest.fail(f"Test setup for test_delete_item failed: {e}")
    
    # --- 2. Run the test ---
    r = requests.delete(f"http://localhost:8000/api/{TABLE}/{item_id}")

    assert r.status_code == 200
    db.expire_all()

    item = crud.get_one_item(db, model_class, item_id)
    assert item is None
    db.close()

def test_metadata_creation():
    new_metadata = {
        "created_by": "tester",
        "table_name": "test_table"
    }
    r = requests.post("http://localhost:8000/api/metadata_creation", json=new_metadata)
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
        r = requests.post("http://localhost:8000/api/metadata_update", json=new_metadata_update_data)
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
            except Exception as e:
                print(f"Error during test_metadata_update teardown: {e}")
        db.close()