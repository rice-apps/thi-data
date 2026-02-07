import os
import sys
import pytest
import uuid

current_dir = os.path.dirname(os.path.abspath(__file__))
server_dir = os.path.dirname(current_dir)
sys.path.insert(0, server_dir)

from core.deps import get_db, init_storage_provider
from core.database import Base, reflect_db
import crud
from main import app
from api import validation
from fastapi.testclient import TestClient
from FakeS3.fakeS3 import FakeS3

app.include_router(validation.router) 
client = TestClient(app)

TABLE = "file_registry"
OBJECT_KEY = "patient_data.csv"

def test_validate_schema_flow():
    reflect_db()
    init_storage_provider(FakeS3(test_files_dir="server/tests/test_validation_data"))
    model_class = Base.classes.get(TABLE)
    
    if not model_class:
        pytest.fail(f"Test setup failed: Could not find model for table '{TABLE}'")

    db = next(get_db())
    test_file_id = str(uuid.uuid4())
    
    new_record = crud.create_item(db, model_class, {
        "file_id": test_file_id, 
        "object_key": OBJECT_KEY, 
        "status": "PENDING"
    })
    db.commit()

    response = client.post(f"/api/validate_schema?file_id={test_file_id}")
    
    assert response.status_code == 200, f"API failed: {response.text}"
    data = response.json()
    assert "schema" in data
    assert "fields" in data["schema"]
    print(f"Inferred Schema: {data['schema']['fields']}")

    db.expire_all() # Refresh
    fields = data["schema"]["fields"]
    field_map = {f["name"]: f["type"] for f in fields}
    assert field_map["PatientID"] == "string"
    assert field_map["FirstName"] == "string"
    assert field_map["LastName"] == "string"
    assert field_map["Age"] == "integer"
    assert field_map["Gender"] == "string"
    assert field_map["BloodType"] == "string"
    assert field_map["LastCheckup"] == "date"
    assert field_map["Condition"] == "string"

    # Cleanup test data
    # crud.delete_item(db, model_class, new_record.id)
    db.close()

if __name__ == "__main__":
    try:
        test_validate_schema_flow()
        print("test_validate_schema_flow PASSED!")
    except Exception as e:
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()