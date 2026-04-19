"""
Unit tests for server/api/files.py — file upload, delete, update, list, process.

All tests use FastAPI TestClient with dependency overrides (no live services).
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.deps import get_db, get_storage_provider, get_file_registry_repo
from api.files import router, derive_table_name


# derive_table_name tests

class TestDeriveTableName:

    def test_simple_csv(self):
        assert derive_table_name("patients.csv") == "patients"

    def test_xlsx_extension(self):
        assert derive_table_name("patients.xlsx") == "patients"

    def test_special_characters(self):
        assert derive_table_name("OWLS Data (2025).xlsx") == "owls_data__2025"

    def test_numeric_prefix(self):
        assert derive_table_name("123data.csv") == "t_123data"

    def test_hyphen_and_spaces(self):
        assert derive_table_name("patient-data report.csv") == "patient_data_report"

    def test_no_extension(self):
        assert derive_table_name("myfile") == "myfile"

    def test_empty_stem(self):
        assert derive_table_name(".hidden") == "t_"


# Test helpers

def _make_app():
    """Create a FastAPI app with the files router and default overrides."""
    app = FastAPI()
    app.include_router(router)

    mock_db = MagicMock()

    def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    return app, mock_db


# Upload tests

class TestUploadFile:

    def test_upload_success(self):
        app, mock_db = _make_app()
        mock_storage = MagicMock()
        mock_storage.upload_file.return_value = True

        mock_repo = MagicMock()
        mock_repo.create.return_value = MagicMock()

        app.dependency_overrides[get_storage_provider] = lambda: mock_storage
        app.dependency_overrides[get_file_registry_repo] = lambda: mock_repo

        client = TestClient(app)
        resp = client.post(
            "/api/files/upload",
            files={"file": ("test.csv", b"a,b\n1,2", "text/csv")},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "file_id" in data
        assert "object_key" in data
        assert data["status"] == "UPLOADED"
        mock_storage.upload_file.assert_called_once()
        mock_repo.create.assert_called_once()

        # Verify target_table_name is derived from filename
        create_kwargs = mock_repo.create.call_args
        obj_in = create_kwargs[1]["obj_in"] if "obj_in" in create_kwargs[1] else create_kwargs[0][1]
        assert obj_in["target_table_name"] == "test"

    def test_upload_derives_table_name_from_xlsx(self):
        app, mock_db = _make_app()
        mock_storage = MagicMock()
        mock_storage.upload_file.return_value = True
        mock_repo = MagicMock()
        mock_repo.create.return_value = MagicMock()

        app.dependency_overrides[get_storage_provider] = lambda: mock_storage
        app.dependency_overrides[get_file_registry_repo] = lambda: mock_repo

        client = TestClient(app)
        resp = client.post(
            "/api/files/upload",
            files={"file": ("OWLS Data (2025).xlsx", b"fake", "application/octet-stream")},
        )
        assert resp.status_code == 200
        create_kwargs = mock_repo.create.call_args
        obj_in = create_kwargs[1]["obj_in"] if "obj_in" in create_kwargs[1] else create_kwargs[0][1]
        assert obj_in["target_table_name"] == "owls_data__2025"

    def test_upload_derives_table_name_numeric_prefix(self):
        app, mock_db = _make_app()
        mock_storage = MagicMock()
        mock_storage.upload_file.return_value = True
        mock_repo = MagicMock()
        mock_repo.create.return_value = MagicMock()

        app.dependency_overrides[get_storage_provider] = lambda: mock_storage
        app.dependency_overrides[get_file_registry_repo] = lambda: mock_repo

        client = TestClient(app)
        resp = client.post(
            "/api/files/upload",
            files={"file": ("123data.csv", b"a,b\n1,2", "text/csv")},
        )
        assert resp.status_code == 200
        create_kwargs = mock_repo.create.call_args
        obj_in = create_kwargs[1]["obj_in"] if "obj_in" in create_kwargs[1] else create_kwargs[0][1]
        assert obj_in["target_table_name"] == "t_123data"

    def test_upload_storage_returns_false(self):
        app, mock_db = _make_app()
        mock_storage = MagicMock()
        mock_storage.upload_file.return_value = False

        app.dependency_overrides[get_storage_provider] = lambda: mock_storage
        app.dependency_overrides[get_file_registry_repo] = lambda: MagicMock()

        client = TestClient(app)
        resp = client.post(
            "/api/files/upload",
            files={"file": ("test.csv", b"a,b\n1,2", "text/csv")},
        )
        assert resp.status_code == 500
        assert "try again" in resp.json()["detail"].lower()

    def test_upload_with_custom_table_name(self):
        app, mock_db = _make_app()
        mock_storage = MagicMock()
        mock_storage.upload_file.return_value = True
        mock_repo = MagicMock()
        mock_repo.create.return_value = MagicMock()

        app.dependency_overrides[get_storage_provider] = lambda: mock_storage
        app.dependency_overrides[get_file_registry_repo] = lambda: mock_repo

        client = TestClient(app)
        resp = client.post(
            "/api/files/upload?table_name=custom_name",
            files={"file": ("test.csv", b"a,b\n1,2", "text/csv")},
        )
        assert resp.status_code == 200
        create_kwargs = mock_repo.create.call_args
        obj_in = create_kwargs[1]["obj_in"] if "obj_in" in create_kwargs[1] else create_kwargs[0][1]
        assert obj_in["target_table_name"] == "custom_name"

    def test_upload_storage_raises(self):
        app, mock_db = _make_app()
        mock_storage = MagicMock()
        mock_storage.upload_file.side_effect = RuntimeError("S3 connection refused")

        app.dependency_overrides[get_storage_provider] = lambda: mock_storage
        app.dependency_overrides[get_file_registry_repo] = lambda: MagicMock()

        client = TestClient(app)
        resp = client.post(
            "/api/files/upload",
            files={"file": ("test.csv", b"a,b\n1,2", "text/csv")},
        )
        assert resp.status_code == 500
        detail = resp.json()["detail"]
        assert "S3" not in detail
        assert "try again" in detail.lower()


# Delete tests

class TestDeleteFile:

    def test_delete_success(self):
        app, mock_db = _make_app()
        mock_storage = MagicMock()
        mock_repo = MagicMock()
        mock_record = MagicMock()
        mock_record.object_key = "uploads/test.csv"
        mock_repo.get_by_field.return_value = [mock_record]

        app.dependency_overrides[get_storage_provider] = lambda: mock_storage
        app.dependency_overrides[get_file_registry_repo] = lambda: mock_repo

        client = TestClient(app)
        resp = client.delete("/api/files", params={"file_id": "abc-123"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["file_id"] == "abc-123"
        mock_storage.delete_file.assert_called_once_with("uploads/test.csv")
        mock_repo.delete_by_field.assert_called_once()

    def test_delete_file_not_found(self):
        app, mock_db = _make_app()
        mock_storage = MagicMock()
        mock_repo = MagicMock()
        mock_repo.get_by_field.return_value = []

        app.dependency_overrides[get_storage_provider] = lambda: mock_storage
        app.dependency_overrides[get_file_registry_repo] = lambda: mock_repo

        client = TestClient(app)
        resp = client.delete("/api/files", params={"file_id": "missing"})
        assert resp.status_code == 404


# Update file registry tests

class TestUpdateFileRegistry:

    def test_update_success(self):
        app, mock_db = _make_app()
        mock_repo = MagicMock()
        mock_repo.update_by_field.return_value = 1

        app.dependency_overrides[get_file_registry_repo] = lambda: mock_repo

        client = TestClient(app)
        resp = client.patch(
            "/api/files/file-1",
            json={"status": "SCHEMA_CONFIRMED"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["file_id"] == "file-1"
        assert data["updated_fields"]["status"] == "SCHEMA_CONFIRMED"

    def test_update_empty_body(self):
        app, mock_db = _make_app()
        app.dependency_overrides[get_file_registry_repo] = lambda: MagicMock()

        client = TestClient(app)
        resp = client.patch("/api/files/file-1", json={})
        assert resp.status_code == 400
        assert "no fields" in resp.json()["detail"].lower()

    def test_update_file_not_found(self):
        app, mock_db = _make_app()
        mock_repo = MagicMock()
        mock_repo.update_by_field.return_value = 0

        app.dependency_overrides[get_file_registry_repo] = lambda: mock_repo

        client = TestClient(app)
        resp = client.patch(
            "/api/files/missing",
            json={"status": "PROCESSING"},
        )
        assert resp.status_code == 404


# List files tests

class TestListFiles:

    def test_returns_storage_listing(self):
        app, _ = _make_app()
        mock_storage = MagicMock()
        mock_storage.list_files.return_value = [
            {"key": "uploads/a.csv", "size": 100},
            {"key": "uploads/b.csv", "size": 200},
        ]
        app.dependency_overrides[get_storage_provider] = lambda: mock_storage

        client = TestClient(app)
        resp = client.get("/api/files")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        mock_storage.list_files.assert_called_once_with(prefix="uploads/")


# Process file tests

class TestProcessFile:

    def test_success_dispatches_celery(self):
        app, mock_db = _make_app()
        mock_db.execute.return_value = MagicMock(rowcount=1)
        mock_repo = MagicMock()
        mock_record = MagicMock()
        mock_record.object_key = "uploads/test.csv"
        mock_repo.get_by_field.return_value = [mock_record]

        app.dependency_overrides[get_file_registry_repo] = lambda: mock_repo

        mock_task = MagicMock()
        mock_task.id = "celery-task-123"

        client = TestClient(app)
        with patch("api.files.process_patient_file") as mock_celery:
            mock_celery.delay.return_value = mock_task
            resp = client.post(
                "/api/files/file-1/process",
                json={"proposed_schema": {"age": "INTEGER"}},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "PROCESSING"
        assert data["task_id"] == "celery-task-123"
        mock_celery.delay.assert_called_once_with("file-1", {"age": "INTEGER"})

    def test_not_found(self):
        app, mock_db = _make_app()
        mock_db.execute.return_value = MagicMock(rowcount=0)
        mock_repo = MagicMock()
        mock_repo.get_by_field.return_value = []

        app.dependency_overrides[get_file_registry_repo] = lambda: mock_repo

        client = TestClient(app)
        resp = client.post(
            "/api/files/missing/process",
            json={"proposed_schema": {"age": "INTEGER"}},
        )
        assert resp.status_code == 404

    def test_conflict_when_not_eligible(self):
        app, mock_db = _make_app()
        mock_db.execute.return_value = MagicMock(rowcount=0)
        mock_repo = MagicMock()
        mock_record = MagicMock()
        mock_record.status = "PROCESSING"
        mock_repo.get_by_field.return_value = [mock_record]
        app.dependency_overrides[get_file_registry_repo] = lambda: mock_repo

        client = TestClient(app)
        resp = client.post(
            "/api/files/f-1/process",
            json={"proposed_schema": {"age": "INTEGER"}},
        )
        assert resp.status_code == 409
        assert "PROCESSING" in resp.json()["detail"]


# Check duplicate tests

class TestCheckDuplicate:

    def test_no_duplicate(self):
        app, mock_db = _make_app()
        mock_repo = MagicMock()
        mock_repo.get_by_field.return_value = []

        app.dependency_overrides[get_file_registry_repo] = lambda: mock_repo

        client = TestClient(app)
        resp = client.get("/api/files/check-duplicate", params={"table_name": "patients"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["exists"] is False
        assert data["table_name"] == "patients"

    def test_active_duplicate_exists(self):
        app, mock_db = _make_app()
        mock_repo = MagicMock()
        mock_record = MagicMock()
        mock_record.status = "SUCCESS"
        mock_repo.get_by_field.return_value = [mock_record]

        app.dependency_overrides[get_file_registry_repo] = lambda: mock_repo

        client = TestClient(app)
        resp = client.get("/api/files/check-duplicate", params={"table_name": "patients"})
        assert resp.status_code == 200
        assert resp.json()["exists"] is True

    def test_deleted_records_ignored(self):
        app, mock_db = _make_app()
        mock_repo = MagicMock()
        mock_record = MagicMock()
        mock_record.status = "DELETED"
        mock_repo.get_by_field.return_value = [mock_record]

        app.dependency_overrides[get_file_registry_repo] = lambda: mock_repo

        client = TestClient(app)
        resp = client.get("/api/files/check-duplicate", params={"table_name": "patients"})
        assert resp.status_code == 200
        assert resp.json()["exists"] is False

    def test_failed_records_ignored(self):
        app, mock_db = _make_app()
        mock_repo = MagicMock()
        mock_record = MagicMock()
        mock_record.status = "FAILED"
        mock_repo.get_by_field.return_value = [mock_record]

        app.dependency_overrides[get_file_registry_repo] = lambda: mock_repo

        client = TestClient(app)
        resp = client.get("/api/files/check-duplicate", params={"table_name": "patients"})
        assert resp.status_code == 200
        assert resp.json()["exists"] is False
