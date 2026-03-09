"""
Tests for the schema validation API endpoints and DI patterns.

Unit tests use FastAPI TestClient with dependency overrides (no live services).
Integration tests hit the live API (requires docker compose up).

Test coverage:
  1. POST /api/validate_schema — schema inference from file
  2. POST /api/files/{file_id}/process — process with user-confirmed schema
  3. DI verification — deps are injected, not created internally
  4. End-to-end: upload → infer → save schema → process
"""

import os
import sys
import uuid
import pytest
import requests
from unittest.mock import patch, MagicMock
from contextlib import contextmanager

# Add the 'server' directory to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
server_dir = os.path.dirname(current_dir)
sys.path.insert(0, server_dir)

from core.enums import FileStatus

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_URL = "http://localhost:8000"
TEST_CSV_PATH = os.path.join(current_dir, "test_data.csv")


# ===========================================================================
# 1. Unit Tests: validate_and_split_data edge cases
# ===========================================================================

class TestValidateAndSplitEdgeCases:
    """Edge cases for the core DuckDB TRY_CAST validation logic."""

    @pytest.fixture(autouse=True)
    def setup_duckdb(self):
        """Stub dlt to avoid import errors, import validate function."""
        import types
        import duckdb

        _fake_dlt = types.ModuleType("services.dlt_pipeline")
        _fake_dlt.CORRUPTED_ROWS_NAME = "corrupted_rows"
        _fake_dlt.RAW_DATA_NAME = "raw_staging"
        _fake_dlt.CLEAN_DATA_NAME = "clean_data"
        class MockDLTPipeline:
            def load_to_postgres(self, con): pass
        _fake_dlt.DLTPipeline = MockDLTPipeline
        sys.modules["services.dlt_pipeline"] = _fake_dlt

        from services.etl_processor import _validate_and_split_data
        self.validate_and_split_data = _validate_and_split_data
        self.RAW = "raw_staging"
        self.CLEAN = "clean_data"
        self.CORRUPTED = "corrupted_rows"

        self.con = duckdb.connect(database=":memory:")
        yield
        self.con.close()

    def _seed(self, columns, rows):
        col_defs = ", ".join(f'"{col}" VARCHAR' for col in columns)
        self.con.execute(f"CREATE TABLE {self.RAW} ({col_defs})")
        for row in rows:
            placeholders = ", ".join(["?"] * len(columns))
            self.con.execute(f"INSERT INTO {self.RAW} VALUES ({placeholders})", list(row))

    def test_empty_dataset(self):
        """Empty CSV: 0 rows should produce 0 clean and 0 corrupted."""
        self._seed(["id", "value"], [])
        error_count = self.validate_and_split_data(self.con, {"id": "INTEGER", "value": "VARCHAR"})
        assert error_count == 0
        assert self.con.execute(f"SELECT COUNT(*) FROM {self.CLEAN}").fetchone()[0] == 0
        assert self.con.execute(f"SELECT COUNT(*) FROM {self.CORRUPTED}").fetchone()[0] == 0

    def test_single_column_schema(self):
        """Schema with only one column: validation still works."""
        self._seed(["name", "age"], [("Alice", "30"), ("Bob", "XY")])
        error_count = self.validate_and_split_data(self.con, {"age": "INTEGER"})
        assert error_count == 1
        
    def test_column_name_with_spaces(self):
        """Column names with spaces should be handled via quoting."""
        self._seed(["patient name", "blood pressure"], [
            ("P001", "120"),
            ("P002", "HIGH"),
        ])
        error_count = self.validate_and_split_data(self.con, {"blood pressure": "INTEGER"})
        assert error_count == 1

    def test_all_null_column(self):
        """A column with all NULLs: none should appear as corrupted (NULL IS NOT NULL = false)."""
        self._seed(["id", "value"], [("1", None), ("2", None)])
        error_count = self.validate_and_split_data(self.con, {"value": "INTEGER"})
        assert error_count == 0

    def test_date_cast_validation(self):
        """DATE type should validate date strings properly."""
        self._seed(["event_date"], [
            ("2025-01-15",),
            ("not-a-date",),
            ("2025-12-31",),
        ])
        error_count = self.validate_and_split_data(self.con, {"event_date": "DATE"})
        assert error_count == 1

    def test_boolean_cast_validation(self):
        """BOOLEAN type should validate boolean strings."""
        self._seed(["flag"], [
            ("true",),
            ("false",),
            ("maybe",),
        ])
        error_count = self.validate_and_split_data(self.con, {"flag": "BOOLEAN"})
        assert error_count == 1

    def test_original_csv_row_id_present(self):
        """Both clean and corrupted tables should contain original_csv_row_id."""
        self._seed(["val"], [("1",), ("bad",)])
        self.validate_and_split_data(self.con, {"val": "INTEGER"})
        
        clean_cols = [desc[0] for desc in self.con.execute(f"SELECT * FROM {self.CLEAN} LIMIT 0").description]
        corrupted_cols = [desc[0] for desc in self.con.execute(f"SELECT * FROM {self.CORRUPTED} LIMIT 0").description]
        assert "original_csv_row_id" in clean_cols
        assert "original_csv_row_id" in corrupted_cols


# ===========================================================================
# 2. Unit Tests: Process file endpoint (POST /api/files/{file_id}/process)
# ===========================================================================

class TestProcessFileEndpoint:
    """Test the process_file endpoint with mocked deps."""

    def test_process_file_dispatches_celery_task(self):
        """Should dispatch a Celery task and return immediately with PROCESSING status."""
        from fastapi.testclient import TestClient
        from api.files import router
        from fastapi import FastAPI
        from core.deps import get_db

        app = FastAPI()
        app.include_router(router)

        mock_db = MagicMock()

        def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db

        client = TestClient(app)

        from core.deps import get_file_registry_repo

        mock_repo = MagicMock()
        mock_record = MagicMock()
        mock_record.object_key = "uploads/test.csv"
        mock_repo.get_by_field.return_value = [mock_record]

        app.dependency_overrides[get_file_registry_repo] = lambda: mock_repo

        payload = {"proposed_schema": {"age": "INTEGER", "name": "VARCHAR"}}

        mock_task = MagicMock()
        mock_task.id = "celery-task-id-456"

        with patch("api.files.process_patient_file") as mock_celery:
            mock_celery.delay.return_value = mock_task
            response = client.post("/api/files/test-123/process", json=payload)

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "PROCESSING"
            assert data["task_id"] == "celery-task-id-456"
            assert data["file_id"] == "test-123"

            mock_celery.delay.assert_called_once_with(
                "test-123",
                {"age": "INTEGER", "name": "VARCHAR"}
            )

    def test_process_file_not_found(self):
        """Should return 404 when file not in registry."""
        from fastapi.testclient import TestClient
        from api.files import router
        from fastapi import FastAPI
        from core.deps import get_db

        app = FastAPI()
        app.include_router(router)

        mock_db = MagicMock()
        app.dependency_overrides[get_db] = lambda: (yield mock_db) or None

        client = TestClient(app)

        from core.deps import get_file_registry_repo

        mock_repo = MagicMock()
        mock_repo.get_by_field.return_value = []

        app.dependency_overrides[get_file_registry_repo] = lambda: mock_repo

        payload = {"proposed_schema": {"age": "INTEGER"}}
        response = client.post("/api/files/missing/process", json=payload)
        assert response.status_code == 404


# ===========================================================================
# 3. Unit Tests: Validate schema endpoint (POST /api/validate_schema)
# ===========================================================================

class TestValidateSchemaEndpoint:
    """Test the validate_schema endpoint with mocked deps."""

    def test_validate_schema_success(self):
        """Should infer schema via frictionless and return columns."""
        from fastapi.testclient import TestClient
        from api.validation import router
        from fastapi import FastAPI
        from core.deps import get_db, get_storage_provider
        from pathlib import Path

        app = FastAPI()
        app.include_router(router)

        mock_db = MagicMock()
        mock_storage = MagicMock()
        mock_storage.get_file_path.return_value = Path("/tmp/test.csv")

        def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_storage_provider] = lambda: mock_storage

        client = TestClient(app)

        from core.deps import get_file_registry_repo

        mock_repo = MagicMock()
        mock_record = MagicMock()
        mock_record.object_key = "uploads/test.csv"
        mock_repo.get_by_field.return_value = [mock_record]
        mock_repo.update_by_field.return_value = 1

        app.dependency_overrides[get_file_registry_repo] = lambda: mock_repo

        mock_infer_result = {
            "schema": {
                "fields": [
                    {"name": "patient_id", "type": "string"},
                    {"name": "age", "type": "integer"},
                    {"name": "weight", "type": "number"},
                ]
            },
            "sample": {}
        }

        with patch("api.validation.infer_from_file", return_value=mock_infer_result):
            response = client.post("/api/validate_schema", params={"file_id": "test-123"})

        assert response.status_code == 200
        data = response.json()
        assert data["file_id"] == "test-123"
        assert len(data["columns"]) == 3
        assert data["columns"][0] == {"name": "patient_id", "type": "string"}
        assert data["columns"][1] == {"name": "age", "type": "integer"}

    def test_validate_schema_file_not_found(self):
        """Should return 404 when file_id not in registry."""
        from fastapi.testclient import TestClient
        from api.validation import router
        from fastapi import FastAPI
        from core.deps import get_db, get_storage_provider

        app = FastAPI()
        app.include_router(router)

        mock_db = MagicMock()
        app.dependency_overrides[get_db] = lambda: (yield mock_db) or None
        app.dependency_overrides[get_storage_provider] = lambda: MagicMock()

        client = TestClient(app)

        from core.deps import get_file_registry_repo

        mock_repo = MagicMock()
        mock_repo.get_by_field.return_value = []

        app.dependency_overrides[get_file_registry_repo] = lambda: mock_repo

        response = client.post("/api/validate_schema", params={"file_id": "missing"})
        assert response.status_code == 404

    def test_validate_schema_storage_file_not_found(self):
        """Should return 404 when storage get_file_path returns None."""
        from fastapi.testclient import TestClient
        from api.validation import router
        from fastapi import FastAPI
        from core.deps import get_db, get_storage_provider, get_file_registry_repo

        app = FastAPI()
        app.include_router(router)

        mock_db = MagicMock()
        def override_get_db():
            yield mock_db
        app.dependency_overrides[get_db] = override_get_db

        mock_storage = MagicMock()
        mock_storage.get_file_path.return_value = None
        app.dependency_overrides[get_storage_provider] = lambda: mock_storage

        mock_repo = MagicMock()
        mock_record = MagicMock()
        mock_record.object_key = "uploads/test.csv"
        mock_repo.get_by_field.return_value = [mock_record]
        app.dependency_overrides[get_file_registry_repo] = lambda: mock_repo

        client = TestClient(app)
        response = client.post("/api/validate_schema", params={"file_id": "f1"})
        assert response.status_code == 404
        assert "not found in storage" in response.json()["detail"].lower()

    def test_validate_schema_frictionless_failure_updates_status(self):
        """Should update status to FRICTIONLESS_FAILED on inference exception and return 500."""
        from fastapi.testclient import TestClient
        from api.validation import router
        from fastapi import FastAPI
        from core.deps import get_db, get_storage_provider, get_file_registry_repo
        from pathlib import Path

        app = FastAPI()
        app.include_router(router)

        mock_db = MagicMock()
        def override_get_db():
            yield mock_db
        app.dependency_overrides[get_db] = override_get_db

        mock_storage = MagicMock()
        mock_storage.get_file_path.return_value = Path("/tmp/test.csv")
        app.dependency_overrides[get_storage_provider] = lambda: mock_storage

        mock_repo = MagicMock()
        mock_record = MagicMock()
        mock_record.object_key = "uploads/test.csv"
        mock_repo.get_by_field.return_value = [mock_record]
        mock_repo.update_by_field.return_value = 1
        app.dependency_overrides[get_file_registry_repo] = lambda: mock_repo

        with patch("api.validation.infer_from_file", side_effect=Exception("parse error")):
            client = TestClient(app)
            response = client.post("/api/validate_schema", params={"file_id": "f1"})

        assert response.status_code == 500
        # Verify status was updated to FRICTIONLESS_FAILED
        update_calls = mock_repo.update_by_field.call_args_list
        assert any(
            c.kwargs.get("update_data", {}).get("status") == FileStatus.FRICTIONLESS_FAILED
            or (c[1].get("update_data", {}).get("status") == FileStatus.FRICTIONLESS_FAILED if len(c) > 1 else False)
            for c in update_calls
        )


# ===========================================================================
# 4. Integration Tests: Full flow (requires docker compose up)
# ===========================================================================

class TestSchemaValidationIntegration:
    """Integration tests hitting the live API.
    
    These require the Docker stack to be running 
    (docker compose up backend db seaweedfs rabbitmq).
    """

    @pytest.fixture
    def uploaded_file(self):
        """Upload a test CSV and return (file_id, object_key). Cleans up after test."""
        test_csv = os.path.join(current_dir, "test_data.csv")
        if not os.path.exists(test_csv):
            pytest.skip("test_data.csv not found")

        with open(test_csv, "rb") as f:
            files = {"file": ("test_data.csv", f, "text/csv")}
            r = requests.post(f"{API_URL}/api/files/upload", files=files)

        if r.status_code != 200:
            pytest.skip(f"Upload failed: {r.status_code} {r.text}")

        data = r.json()
        file_id = data["file_id"]
        yield file_id

        # Cleanup
        try:
            requests.delete(f"{API_URL}/api/files", params={"file_id": file_id})
        except Exception:
            pass

    def test_upload_and_validate_schema(self, uploaded_file):
        """Upload a CSV, infer its schema, verify columns are returned."""
        file_id = uploaded_file

        r = requests.post(
            f"{API_URL}/api/validate_schema",
            params={"file_id": file_id}
        )

        assert r.status_code == 200, f"Schema validation failed: {r.text}"
        data = r.json()
        assert data["file_id"] == file_id
        assert isinstance(data["columns"], list)
        assert len(data["columns"]) > 0

        # Each column should have name and type
        for col in data["columns"]:
            assert "name" in col
            assert "type" in col

    def test_full_flow_upload_infer_confirm_process(self, uploaded_file):
        """
        Full integration test of the schema validation pipeline:
        1. Upload CSV (done by fixture)
        2. Infer schema via POST /api/validate_schema
        3. Save schema via PATCH /api/files/{file_id}
        4. Queue processing via POST /api/files/{file_id}/process
        """
        file_id = uploaded_file

        # 2. Infer schema
        infer_resp = requests.post(
            f"{API_URL}/api/validate_schema",
            params={"file_id": file_id}
        )
        assert infer_resp.status_code == 200, f"Inference failed: {infer_resp.text}"
        columns = infer_resp.json()["columns"]

        # Map Frictionless types to DuckDB types for confirmation
        FRICTIONLESS_TO_DUCKDB = {
            "string": "VARCHAR",
            "integer": "INTEGER",
            "number": "DOUBLE",
            "boolean": "BOOLEAN",
            "date": "DATE",
            "datetime": "TIMESTAMP",
        }
        schema_map = {}
        clean_schema = {"fields": []}
        for col in columns:
            duckdb_type = FRICTIONLESS_TO_DUCKDB.get(col["type"], "VARCHAR")
            schema_map[col["name"]] = duckdb_type
            clean_schema["fields"].append({"name": col["name"], "type": duckdb_type})

        # 3. Save schema via PATCH /api/files/{file_id}
        save_resp = requests.patch(
            f"{API_URL}/api/files/{file_id}",
            json={
                "file_schema": clean_schema,
                "status": FileStatus.SCHEMA_CONFIRMED,
            }
        )
        assert save_resp.status_code == 200, f"Schema save failed: {save_resp.text}"

        # 4. Queue processing via POST /api/files/{file_id}/process
        process_resp = requests.post(
            f"{API_URL}/api/files/{file_id}/process",
            json={"proposed_schema": schema_map}
        )
        assert process_resp.status_code == 200, f"Process failed: {process_resp.text}"
        process_data = process_resp.json()
        assert process_data["file_id"] == file_id
        assert process_data["status"] == "PROCESSING"



# ===========================================================================
# 5. Error message sanitization
# ===========================================================================

class TestErrorSanitization:
    """Verify error messages don't leak technical details."""

    def test_validate_schema_error_is_generic(self):
        from fastapi.testclient import TestClient
        from api.validation import router
        from fastapi import FastAPI
        from core.deps import get_db, get_storage_provider, get_file_registry_repo

        app = FastAPI()
        app.include_router(router)

        mock_db = MagicMock()
        def override_get_db():
            yield mock_db
        app.dependency_overrides[get_db] = override_get_db

        mock_storage = MagicMock()
        mock_storage.get_file_path.return_value = "/tmp/nonexistent.csv"
        app.dependency_overrides[get_storage_provider] = lambda: mock_storage

        mock_repo = MagicMock()
        mock_record = MagicMock()
        mock_record.object_key = "uploads/test.csv"
        mock_repo.get_by_field.return_value = [mock_record]
        mock_repo.update_by_field.return_value = 1
        app.dependency_overrides[get_file_registry_repo] = lambda: mock_repo

        with patch("api.validation.infer_from_file", side_effect=Exception("UnicodeDecodeError at byte 0xFF")):
            client = TestClient(app)
            resp = client.post("/api/validate_schema", params={"file_id": "f1"})

        assert resp.status_code == 500
        detail = resp.json()["detail"]
        assert "UnicodeDecodeError" not in detail
        assert "0xFF" not in detail
        assert "file format" in detail.lower()

    def test_files_upload_error_is_generic(self):
        from fastapi.testclient import TestClient
        from api.files import router
        from fastapi import FastAPI
        from core.deps import get_db, get_storage_provider, get_file_registry_repo

        app = FastAPI()
        app.include_router(router)

        mock_db = MagicMock()
        def override_get_db():
            yield mock_db
        app.dependency_overrides[get_db] = override_get_db

        mock_storage = MagicMock()
        mock_storage.upload_file.side_effect = RuntimeError("S3 connection refused on port 9000")
        app.dependency_overrides[get_storage_provider] = lambda: mock_storage
        app.dependency_overrides[get_file_registry_repo] = lambda: MagicMock()

        client = TestClient(app)
        resp = client.post("/api/files/upload", files={"file": ("test.csv", b"a,b\n1,2", "text/csv")})

        assert resp.status_code == 500
        detail = resp.json()["detail"]
        assert "S3" not in detail
        assert "9000" not in detail
        assert "connection refused" not in detail.lower()
        assert "try again" in detail.lower()

    def test_create_item_error_is_generic(self):
        from fastapi.testclient import TestClient
        from api.rows import router
        from fastapi import FastAPI
        from core.deps import get_db, get_model_class

        app = FastAPI()
        app.include_router(router)

        mock_db = MagicMock()
        def override_get_db():
            yield mock_db
        app.dependency_overrides[get_db] = override_get_db

        mock_model = MagicMock()
        mock_mapper = MagicMock()
        mock_col = MagicMock()
        mock_col.key = "name"
        mock_mapper.column_attrs = [mock_col]
        mock_mapper.primary_key = []

        with patch("api.rows.inspect", return_value=mock_mapper):
            with patch("api.rows.get_repository") as mock_get_repo:
                mock_repo = MagicMock()
                mock_repo.create.side_effect = Exception("UNIQUE constraint failed: patients.name")
                mock_get_repo.return_value = mock_repo

                app.dependency_overrides[get_model_class] = lambda table_name: mock_model
                client = TestClient(app)
                resp = client.post("/api/test_table", json={"name": "Alice"})

        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert "UNIQUE constraint" not in detail
        assert "input values" in detail.lower()

    def test_match_items_error_is_generic(self):
        from fastapi.testclient import TestClient
        from api.rows import router
        from fastapi import FastAPI
        from core.deps import get_db, get_model_class

        app = FastAPI()
        app.include_router(router)

        mock_db = MagicMock()
        def override_get_db():
            yield mock_db
        app.dependency_overrides[get_db] = override_get_db

        mock_model = MagicMock()

        with patch("api.rows.get_repository") as mock_get_repo:
            mock_repo = MagicMock()
            mock_repo.filter_text.side_effect = Exception("column 'xyz' does not exist")
            mock_get_repo.return_value = mock_repo

            app.dependency_overrides[get_model_class] = lambda table_name: mock_model
            client = TestClient(app)
            resp = client.get("/api/test_table/search/xyz/foo")

        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert "column" not in detail.lower()
        assert "does not exist" not in detail.lower()
        assert "query" in detail.lower()

    def test_update_item_error_is_generic(self):
        from fastapi.testclient import TestClient
        from api.rows import router
        from fastapi import FastAPI
        from core.deps import get_db, get_model_class

        app = FastAPI()
        app.include_router(router)

        mock_db = MagicMock()
        def override_get_db():
            yield mock_db
        app.dependency_overrides[get_db] = override_get_db

        mock_model = MagicMock()
        mock_mapper = MagicMock()
        mock_col = MagicMock()
        mock_col.key = "name"
        mock_mapper.column_attrs = [mock_col]
        mock_mapper.primary_key = []

        with patch("api.rows.inspect", return_value=mock_mapper):
            with patch("api.rows.get_repository") as mock_get_repo:
                mock_repo = MagicMock()
                mock_item = MagicMock()
                mock_repo.get_by_id.return_value = mock_item
                mock_repo.update.side_effect = Exception("psycopg2.IntegrityError: duplicate key")
                mock_get_repo.return_value = mock_repo

                app.dependency_overrides[get_model_class] = lambda table_name: mock_model
                client = TestClient(app)
                resp = client.put("/api/test_table/1", json={"name": "Bob"})

        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert "psycopg2" not in detail
        assert "IntegrityError" not in detail
        assert "input values" in detail.lower()

