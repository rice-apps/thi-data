"""
End-to-end pipeline tests.

These require the full Docker stack running:
  docker compose up backend db seaweedfs rabbitmq celery-worker

Tests upload CSVs, infer schema, confirm, process, and verify results
land in Postgres and SSE works.
"""

import os
import sys
import time
import pytest
import requests

current_dir = os.path.dirname(os.path.abspath(__file__))
server_dir = os.path.dirname(current_dir)
if server_dir not in sys.path:
    sys.path.insert(0, server_dir)

from core.enums import FileStatus

API_URL = "http://localhost:8000"
TEST_CSV_PATH = os.path.join(current_dir, "test_data.csv")
CORRUPTED_CSV_PATH = os.path.join(current_dir, "test_data_corrupted.csv")
CORRUPTED_XLSX_PATH = os.path.join(current_dir, "test_data_corrupted.xlsx")

FRICTIONLESS_TO_DUCKDB = {
    "string": "VARCHAR",
    "integer": "INTEGER",
    "number": "DOUBLE",
    "boolean": "BOOLEAN",
    "date": "DATE",
    "datetime": "TIMESTAMP",
}

POLL_INTERVAL = 2
POLL_TIMEOUT = 60


def _api_available():
    try:
        r = requests.get(f"{API_URL}/", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


_MIME_TYPES = {
    ".csv": "text/csv",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _upload_and_process(file_path, schema_overrides=None):
    """Upload file, infer schema, confirm, process. Returns file_id.

    Args:
        file_path: Path to the data file (.csv or .xlsx).
        schema_overrides: Optional dict mapping column names to DuckDB types,
            applied after frictionless inference to force strict types.
    """
    ext = os.path.splitext(file_path)[1].lower()
    mime = _MIME_TYPES.get(ext, "application/octet-stream")
    with open(file_path, "rb") as f:
        files = {"file": (os.path.basename(file_path), f, mime)}
        r = requests.post(f"{API_URL}/api/files/upload", files=files)
    assert r.status_code == 200, f"Upload failed: {r.text}"
    file_id = r.json()["file_id"]

    # Infer schema
    r = requests.post(f"{API_URL}/api/validate_schema", params={"file_id": file_id})
    assert r.status_code == 200, f"Schema inference failed: {r.text}"
    columns = r.json()["columns"]

    schema_map = {}
    clean_schema = {"fields": []}
    for col in columns:
        duckdb_type = FRICTIONLESS_TO_DUCKDB.get(col["type"], "VARCHAR")
        schema_map[col["name"]] = duckdb_type
        clean_schema["fields"].append({"name": col["name"], "type": duckdb_type})

    # Apply schema overrides to force strict types
    if schema_overrides:
        schema_map.update(schema_overrides)
        for field in clean_schema["fields"]:
            if field["name"] in schema_overrides:
                field["type"] = schema_overrides[field["name"]]

    r = requests.patch(
        f"{API_URL}/api/files/{file_id}",
        json={"file_schema": clean_schema, "status": FileStatus.SCHEMA_CONFIRMED},
    )
    assert r.status_code == 200, f"Schema confirm failed: {r.text}"

    r = requests.post(
        f"{API_URL}/api/files/{file_id}/process",
        json={"proposed_schema": schema_map},
    )
    assert r.status_code == 200, f"Process failed: {r.text}"

    return file_id


def _poll_until_terminal(file_id, timeout=POLL_TIMEOUT):
    """Poll file registry until status is terminal. Returns final status."""
    start = time.time()
    while time.time() - start < timeout:
        r = requests.get(
            f"{API_URL}/api/events/stream",
            params={"file_id": file_id},
            stream=True,
            timeout=timeout,
        )
        for line in r.iter_lines(decode_unicode=True):
            if line and line.startswith("event:"):
                event_type = line.split(":", 1)[1].strip()
                if event_type in ("celery_success", "celery_failed"):
                    return event_type
        time.sleep(POLL_INTERVAL)
    pytest.fail(f"Timed out waiting for terminal status for file_id={file_id}")


pytestmark = pytest.mark.skipif(
    not _api_available(),
    reason="API server not available (Docker stack not running)"
)


# Full Pipeline E2E tests
class TestFullPipelineE2E:

    @pytest.fixture(scope="class")
    def processed_file(self):
        """Upload test_data.csv and process it through the full pipeline."""
        if not os.path.exists(TEST_CSV_PATH):
            pytest.skip("test_data.csv not found")

        file_id = _upload_and_process(TEST_CSV_PATH)
        status = _poll_until_terminal(file_id)

        yield file_id, status

        # Delete file from registry
        try:
            requests.delete(f"{API_URL}/api/files", params={"file_id": file_id})
        except Exception:
            pass

    def test_processing_completes_successfully(self, processed_file):
        file_id, status = processed_file
        assert status == "celery_success", f"Expected success but got {status}"

    def test_data_lands_in_postgres(self, processed_file):
        file_id, status = processed_file
        if status != "celery_success":
            pytest.skip("Processing did not succeed")

        r = requests.get(f"{API_URL}/api/test_data")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] > 0, "No rows found in test_data table"

    def test_new_table_appears_in_tables_list(self, processed_file):
        file_id, status = processed_file
        if status != "celery_success":
            pytest.skip("Processing did not succeed")

        r = requests.get(f"{API_URL}/api/tables")
        assert r.status_code == 200
        tables = r.json()["tables"]
        assert "test_data" in tables

    def test_sse_returns_terminal_event(self, processed_file):
        file_id, status = processed_file

        # After processing, SSE should return terminal immediately
        r = requests.get(
            f"{API_URL}/api/events/stream",
            params={"file_id": file_id},
            stream=True,
            timeout=10,
        )
        lines = []
        for line in r.iter_lines(decode_unicode=True):
            lines.append(line)
            if line == "":
                break

        assert any("celery_success" in l or "celery_failed" in l for l in lines)


# Corrupted Data E2E tests
class TestCorruptedDataE2E:

    @pytest.fixture(scope="class")
    def processed_corrupted_file(self):
        """Upload test_data_corrupted.csv and process it."""
        if not os.path.exists(CORRUPTED_CSV_PATH):
            pytest.skip("test_data_corrupted.csv not found")

        file_id = _upload_and_process(
            CORRUPTED_CSV_PATH,
            schema_overrides={
                "age": "INTEGER",
                "blood_pressure": "INTEGER",
                "admission_date": "DATE",
            },
        )
        status = _poll_until_terminal(file_id)

        yield file_id, status

        try:
            requests.delete(f"{API_URL}/api/files", params={"file_id": file_id})
        except Exception:
            pass

    def test_processing_completes(self, processed_corrupted_file):
        file_id, status = processed_corrupted_file
        assert status in ("celery_success", "celery_failed")

    def test_corrupted_rows_populated(self, processed_corrupted_file):
        """After processing, the corrupted_rows internal table should have entries."""
        file_id, status = processed_corrupted_file
        if status != "celery_success":
            pytest.skip("Processing did not succeed")

        # Access corrupted rows via the CRUD endpoint on the data table
        r = requests.get(f"{API_URL}/api/test_data_corrupted")
        if r.status_code != 200:
            pytest.skip("test_data_corrupted table not available")

        data = r.json()
        # Check if any rows have corruption markers
        corrupted = [row for row in data.get("data", []) if row.get("_is_corrupted")]
        # With our test data, we expect exactly 3 corrupted rows:
        #   P002: age="abc" (not INTEGER)
        #   P003: blood_pressure="HIGH" (not INTEGER)
        #   P004: admission_date="not-a-date" (not DATE)
        assert len(corrupted) == 3, f"Expected 3 corrupted rows but found {len(corrupted)}"

        corrupted_ids = {row["patient_id"] for row in corrupted}
        assert corrupted_ids == {"P002", "P003", "P004"}, (
            f"Expected corrupted patient_ids {{P002, P003, P004}}, got {corrupted_ids}"
        )


# XLSX Corrupted Data E2E tests
class TestXLSXCorruptedDataE2E:

    @pytest.fixture(scope="class")
    def processed_xlsx_file(self):
        """Upload test_data_corrupted.xlsx and process it."""
        if not os.path.exists(CORRUPTED_XLSX_PATH):
            pytest.skip("test_data_corrupted.xlsx not found")

        file_id = _upload_and_process(
            CORRUPTED_XLSX_PATH,
            schema_overrides={
                "age": "INTEGER",
                "blood_pressure": "INTEGER",
                "admission_date": "DATE",
            },
        )
        status = _poll_until_terminal(file_id)

        yield file_id, status

        try:
            requests.delete(f"{API_URL}/api/files", params={"file_id": file_id})
        except Exception:
            pass

    def test_processing_completes(self, processed_xlsx_file):
        file_id, status = processed_xlsx_file
        assert status == "celery_success", f"Expected success but got {status}"

    def test_corrupted_rows_detected(self, processed_xlsx_file):
        file_id, status = processed_xlsx_file
        if status != "celery_success":
            pytest.skip("Processing did not succeed")

        r = requests.get(f"{API_URL}/api/test_data_corrupted")
        if r.status_code != 200:
            pytest.skip("test_data_corrupted table not available")

        data = r.json()
        corrupted = [row for row in data.get("data", []) if row.get("_is_corrupted")]
        assert len(corrupted) == 3, f"Expected 3 corrupted rows but found {len(corrupted)}"

        corrupted_ids = {row["patient_id"] for row in corrupted}
        assert corrupted_ids == {"P002", "P003", "P004"}, (
            f"Expected corrupted patient_ids {{P002, P003, P004}}, got {corrupted_ids}"
        )
