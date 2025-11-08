import requests
import os
import sys
import pytest

# --- Imports for setup/teardown ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir) 

from main import get_db, get_model_class
import crud
from database import Base, reflect_db

TABLE = "test_database" 
EXAMPLE_FIRST_NAME = "Jeff"
EXAMPLE_LAST_NAME = "Bezos"
EXAMPLE_AGE = 800

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
        # --- 1. SETUP: Use the correct crud function ---
        created_item = crud.create_item(db, model_class, new_item_data)
        item_id = created_item.id
        
        yield item_id
    
    finally:
        # --- 2. TEARDOWN: Clean up the database ---
        if created_item:
            try:
                # We can re-use the 'db' session from the 'try' block
                crud.delete_item(db, model_class, created_item.id)
            except Exception as e:
                print(f"Error during test teardown: {e}")
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

    return item_id

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


def test_delete_item(setup_item):
    item_id = setup_item
    r = requests.delete(f"http://localhost:8000/api/{TABLE}/{item_id}")

    assert r.status_code == 200

    model_class = Base.classes.get(TABLE)
    
    if not model_class:
        pytest.fail(f"Test setup failed: Could not find model for table '{TABLE}'")

    db = next(get_db())
    item = crud.get_one_item(db, model_class, item_id)
    assert item == None
    db.close()