"""
Integration tests for tables API endpoints.

Requires the Docker stack to be running (docker compose up).
"""

import os
import sys
import pytest
import requests

current_dir = os.path.dirname(os.path.abspath(__file__))
server_dir = os.path.dirname(current_dir)
if server_dir not in sys.path:
    sys.path.insert(0, server_dir)

API_URL = "http://localhost:8000"


def _api_available():
    try:
        r = requests.get(f"{API_URL}/", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _api_available(),
    reason="API server not available (Docker stack not running)"
)


class TestTablesIntegration:

    def test_tables_with_metadata_returns_structure(self):
        r = requests.get(f"{API_URL}/api/tables_with_metadata")
        assert r.status_code == 200
        data = r.json()
        assert "tables" in data
        assert isinstance(data["tables"], list)
        # Each table should have expected metadata fields
        if data["tables"]:
            table = data["tables"][0]
            assert "name" in table
            assert "uploadedBy" in table
            assert "dateUploaded" in table
            assert "size" in table

    def test_table_schema_returns_columns(self):
        # First get a table name
        r = requests.get(f"{API_URL}/api/tables")
        if r.status_code != 200 or not r.json().get("tables"):
            pytest.skip("No tables available")

        table_name = r.json()["tables"][0]
        r = requests.get(f"{API_URL}/api/schema/{table_name}")
        assert r.status_code == 200
        data = r.json()
        assert "columns" in data
        assert isinstance(data["columns"], list)
        assert all(
            isinstance(c, dict) and "name" in c and "type" in c for c in data["columns"]
        )
        names = [c["name"] for c in data["columns"]]
        assert "id" not in names
        assert "original_csv_row_id" not in names

    def test_table_size(self):
        r = requests.get(f"{API_URL}/api/tables")
        if r.status_code != 200 or not r.json().get("tables"):
            pytest.skip("No tables available")

        table_name = r.json()["tables"][0]
        r = requests.get(f"{API_URL}/api/get_size/{table_name}")
        assert r.status_code == 200
        data = r.json()
        assert "table" in data
        assert "size" in data

    def test_table_size_nonexistent(self):
        r = requests.get(f"{API_URL}/api/get_size/nonexistent_table_xyz")
        assert r.status_code in (404, 400)
