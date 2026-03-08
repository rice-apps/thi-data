"""
Tests for the schema validation API endpoints and DI patterns.

Unit tests use FastAPI TestClient with dependency overrides (no live services).
Integration tests hit the live API (requires docker compose up).

Test coverage:
  1. POST /api/validate_schema — schema inference from file
  2. PATCH /api/schema/{file_id} — confirm schema + trigger ETL
  3. POST /api/files/{file_id}/process — process with user-confirmed schema
  4. DI verification — deps are injected, not created internally
  5. End-to-end: upload → infer → confirm → process
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
        _fake_dlt.load_to_postgres = lambda _con: None
        sys.modules["services.dlt_pipeline"] = _fake_dlt

        from services.etl_processor import validate_and_split_data
        self.validate_and_split_data = validate_and_split_data
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
# 2. Unit Tests: Schema API endpoint (PATCH /api/schema/{file_id})
# ===========================================================================

class TestSchemaConfirmEndpoint:
    """Test the confirm_schema endpoint with mocked deps."""

    def test_confirm_schema_calls_etl_with_injected_deps(self):
        """confirm_schema should pass db and storage to run_pipeline_with_schema."""
        from fastapi.testclient import TestClient
        from api.schema import router, confirm_schema
        from fastapi import FastAPI
        from core.deps import get_db, get_storage_provider

        app = FastAPI()
        app.include_router(router)

        mock_db = MagicMock()
        mock_storage = MagicMock()

        def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_storage_provider] = lambda: mock_storage

        client = TestClient(app)

        # Mock crud to return a file record and accept updates
        with patch("api.schema.crud") as mock_crud, \
             patch("api.schema.get_file_registry_model") as mock_get_model, \
             patch("api.schema.etl_processor") as mock_etl:

            mock_get_model.return_value = MagicMock()
            mock_crud.get_items_by_field.return_value = [MagicMock()]
            mock_crud.update_item_by_field.return_value = 1

            payload = {
                "columns": [
                    {"name": "age", "type": "INTEGER"},
                    {"name": "name", "type": "VARCHAR"},
                ]
            }

            response = client.patch("/api/schema/test-file-123", json=payload)

            assert response.status_code == 200
            data = response.json()
            assert data["file_id"] == "test-file-123"
            assert data["status"] == FileStatus.SCHEMA_CONFIRMED

            # Verify ETL was called with injected deps
            mock_etl.run_pipeline_with_schema.assert_called_once_with(
                "test-file-123",
                {"age": "INTEGER", "name": "VARCHAR"},
                db=mock_db,
                storage=mock_storage,
            )

    def test_confirm_schema_returns_404_for_missing_file(self):
        """Should return 404 if file_id not found in registry."""
        from fastapi.testclient import TestClient
        from api.schema import router
        from fastapi import FastAPI
        from core.deps import get_db, get_storage_provider

        app = FastAPI()
        app.include_router(router)

        mock_db = MagicMock()
        app.dependency_overrides[get_db] = lambda: (yield mock_db) or None
        app.dependency_overrides[get_storage_provider] = lambda: MagicMock()

        client = TestClient(app)

        with patch("api.schema.crud") as mock_crud, \
             patch("api.schema.get_file_registry_model") as mock_get_model:
            mock_get_model.return_value = MagicMock()
            mock_crud.get_items_by_field.return_value = []  # No file found

            payload = {"columns": [{"name": "age", "type": "INTEGER"}]}
            response = client.patch("/api/schema/nonexistent-file", json=payload)

            assert response.status_code == 404


# ===========================================================================
# 3. Unit Tests: Process file endpoint (POST /api/files/{file_id}/process)
# ===========================================================================

class TestProcessFileEndpoint:
    """Test the process_file endpoint with mocked deps."""

    def test_process_file_success(self):
        """Should call process_file_task and update status to SUCCESS."""
        from fastapi.testclient import TestClient
        from api.files import router
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

        with patch("api.files.crud") as mock_crud, \
             patch("api.files.get_file_registry_model") as mock_get_model, \
             patch("api.files.process_file_task") as mock_process:

            mock_model = MagicMock()
            mock_get_model.return_value = mock_model
            mock_record = MagicMock()
            mock_record.object_key = "uploads/test.csv"
            mock_crud.get_items_by_field.return_value = [mock_record]
            mock_crud.update_item_by_field.return_value = 1
            mock_process.return_value = 0

            payload = {"proposed_schema": {"age": "INTEGER", "name": "VARCHAR"}}
            response = client.post("/api/files/test-123/process", json=payload)

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == FileStatus.SUCCESS

            mock_process.assert_called_once_with(
                str(Path("/tmp/test.csv")),
                {"age": "INTEGER", "name": "VARCHAR"}
            )

    def test_process_file_not_found(self):
        """Should return 404 when file not in registry."""
        from fastapi.testclient import TestClient
        from api.files import router
        from fastapi import FastAPI
        from core.deps import get_db, get_storage_provider

        app = FastAPI()
        app.include_router(router)

        mock_db = MagicMock()
        app.dependency_overrides[get_db] = lambda: (yield mock_db) or None
        app.dependency_overrides[get_storage_provider] = lambda: MagicMock()

        client = TestClient(app)

        with patch("api.files.crud") as mock_crud, \
             patch("api.files.get_file_registry_model") as mock_get_model:
            mock_get_model.return_value = MagicMock()
            mock_crud.get_items_by_field.return_value = []

            payload = {"proposed_schema": {"age": "INTEGER"}}
            response = client.post("/api/files/missing/process", json=payload)
            assert response.status_code == 404

    def test_process_file_etl_failure_sets_failed_status(self):
        """If ETL raises, status should be set to FAILED and 500 returned."""
        from fastapi.testclient import TestClient
        from api.files import router
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

        with patch("api.files.crud") as mock_crud, \
             patch("api.files.get_file_registry_model") as mock_get_model, \
             patch("api.files.process_file_task") as mock_process:

            mock_get_model.return_value = MagicMock()
            mock_record = MagicMock()
            mock_record.object_key = "uploads/test.csv"
            mock_crud.get_items_by_field.return_value = [mock_record]
            mock_crud.update_item_by_field.return_value = 1
            mock_process.side_effect = RuntimeError("DuckDB crashed")

            payload = {"proposed_schema": {"age": "INTEGER"}}
            response = client.post("/api/files/test-fail/process", json=payload)

            assert response.status_code == 500
            assert "DuckDB crashed" in response.json()["detail"]

            # Verify status was updated to FAILED
            failed_calls = [
                c for c in mock_crud.update_item_by_field.call_args_list
                if c[1].get("update_data", {}).get("status") == FileStatus.FAILED
            ]
            assert len(failed_calls) >= 1


# ===========================================================================
# 4. Unit Tests: Validate schema endpoint (POST /api/validate_schema)
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

        with patch("api.validation.crud") as mock_crud, \
             patch("api.validation.get_file_registry_model") as mock_get_model:

            mock_get_model.return_value = MagicMock()
            mock_record = MagicMock()
            mock_record.object_key = "uploads/test.csv"
            mock_crud.get_items_by_field.return_value = [mock_record]
            mock_crud.update_item_by_field.return_value = 1

            # Mock frictionless inference result
            mock_crud.infer_from_file.return_value = {
                "schema": {
                    "fields": [
                        {"name": "patient_id", "type": "string"},
                        {"name": "age", "type": "integer"},
                        {"name": "weight", "type": "number"},
                    ]
                },
                "sample": {}
            }

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

        with patch("api.validation.crud") as mock_crud, \
             patch("api.validation.get_file_registry_model") as mock_get_model:
            mock_get_model.return_value = MagicMock()
            mock_crud.get_items_by_field.return_value = []

            response = client.post("/api/validate_schema", params={"file_id": "missing"})
            assert response.status_code == 404


# ===========================================================================
# 5. DI Pattern Verification
# ===========================================================================

class TestDependencyInjection:
    """Verify proper DI patterns throughout the schema validation pipeline."""

    def test_get_db_context_is_proper_context_manager(self):
        """get_db_context should be a proper contextmanager that
        supports 'with' statement and triggers commit/rollback."""
        from core.deps import get_db_context

        # It should work as a context manager (not blow up)
        with patch("core.deps.SessionLocal") as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session

            with get_db_context() as db:
                assert db is mock_session

            # Should commit on success
            mock_session.commit.assert_called_once()
            mock_session.close.assert_called_once()

    def test_get_db_context_rollback_on_error(self):
        """get_db_context should rollback on exception."""
        from core.deps import get_db_context

        with patch("core.deps.SessionLocal") as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session

            with pytest.raises(ValueError):
                with get_db_context() as db:
                    raise ValueError("test error")

            mock_session.rollback.assert_called_once()
            mock_session.close.assert_called_once()

    def test_run_pipeline_with_schema_accepts_injected_deps(self):
        """run_pipeline_with_schema should accept db and storage as params."""
        import inspect
        from services.etl_processor import run_pipeline_with_schema

        sig = inspect.signature(run_pipeline_with_schema)
        params = list(sig.parameters.keys())
        assert "db" in params, "run_pipeline_with_schema must accept 'db' parameter"
        assert "storage" in params, "run_pipeline_with_schema must accept 'storage' parameter"

    def test_storage_provider_not_imported_from_supabase(self):
        """No server module should import from core.supabase."""
        import importlib
        import inspect as insp
        api_modules = ["api.files", "api.schema", "api.validation", "api.metadata"]
        for module_name in api_modules:
            mod = importlib.import_module(module_name)
            source_file = insp.getfile(mod)
            with open(source_file, "r") as f:
                content = f.read()
            assert "from core.supabase" not in content, \
                f"{module_name} still imports from core.supabase"
            assert "get_supabase_client" not in content, \
                f"{module_name} still references get_supabase_client"


# ===========================================================================
# 6. Integration Tests: Full flow (requires docker compose up)
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
        3. Confirm schema via PATCH /api/schema/{file_id}
        4. Verify status transitions
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
        confirmed_columns = []
        for col in columns:
            duckdb_type = FRICTIONLESS_TO_DUCKDB.get(col["type"], "VARCHAR")
            confirmed_columns.append({"name": col["name"], "type": duckdb_type})

        # 3. Confirm schema
        confirm_resp = requests.patch(
            f"{API_URL}/api/schema/{file_id}",
            json={"columns": confirmed_columns}
        )
        assert confirm_resp.status_code == 200, f"Schema confirm failed: {confirm_resp.text}"
        confirm_data = confirm_resp.json()
        assert confirm_data["file_id"] == file_id
        assert confirm_data["status"] == FileStatus.SCHEMA_CONFIRMED
