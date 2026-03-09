"""
Unit tests for server/api/tables.py — table listing, metadata, schema, size.

All tests use mocked dependencies (no live services).
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.deps import get_db, get_model_class, get_internal_model_class
from api.tables import router


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app():
    app = FastAPI()
    app.include_router(router)

    mock_db = MagicMock()

    def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    return app, mock_db


# ---------------------------------------------------------------------------
# GET /api/tables
# ---------------------------------------------------------------------------

class TestGetAllTables:

    def test_returns_visible_tables_only(self):
        app, _ = _make_app()

        with patch("api.tables.Base") as mock_base:
            mock_base.classes.keys.return_value = [
                "patients",
                "file_registry",
                "metadata_creation",
                "lab_results",
            ]

            client = TestClient(app)
            resp = client.get("/api/tables")

        assert resp.status_code == 200
        tables = resp.json()["tables"]
        assert "patients" in tables
        assert "lab_results" in tables
        # Hidden tables excluded
        assert "file_registry" not in tables
        assert "metadata_creation" not in tables


# ---------------------------------------------------------------------------
# GET /api/tables_with_metadata
# ---------------------------------------------------------------------------

class TestTablesWithMetadata:

    def test_calls_get_tables_metadata(self):
        app, mock_db = _make_app()

        mock_creation = MagicMock()
        mock_updates = MagicMock()

        app.dependency_overrides[get_internal_model_class] = (
            lambda table_name: mock_creation if "creation" in table_name else mock_updates
        )

        with patch("api.tables.Base") as mock_base, \
             patch("api.tables.get_tables_metadata") as mock_get_meta, \
             patch("api.tables.get_internal_model_class") as mock_get_internal:
            mock_base.classes.keys.return_value = ["patients", "file_registry"]
            mock_get_internal.side_effect = [mock_creation, mock_updates]
            mock_get_meta.return_value = [
                {"name": "patients", "uploadedBy": "admin", "size": "1 MB"}
            ]

            client = TestClient(app)
            resp = client.get("/api/tables_with_metadata")

        assert resp.status_code == 200
        data = resp.json()
        assert data["tables"][0]["name"] == "patients"
        mock_get_meta.assert_called_once()


# ---------------------------------------------------------------------------
# GET /api/schema/{table_name}
# ---------------------------------------------------------------------------

class TestGetTableSchema:

    def test_schema_excludes_id(self):
        app, _ = _make_app()

        mock_model = MagicMock()
        mapper = MagicMock()
        col_id = MagicMock()
        col_id.key = "id"
        col_name = MagicMock()
        col_name.key = "name"
        col_age = MagicMock()
        col_age.key = "age"
        mapper.column_attrs = [col_id, col_name, col_age]

        app.dependency_overrides[get_model_class] = lambda table_name: mock_model

        with patch("api.tables.inspect", return_value=mapper):
            client = TestClient(app)
            resp = client.get("/api/schema/patients")

        assert resp.status_code == 200
        columns = resp.json()["columns"]
        assert "id" not in columns
        assert "name" in columns
        assert "age" in columns


# ---------------------------------------------------------------------------
# GET /api/get_size/{table_name}
# ---------------------------------------------------------------------------

class TestGetSize:

    def test_success(self):
        app, mock_db = _make_app()

        with patch("api.tables.get_database_size") as mock_get_size:
            mock_get_size.return_value = {"table": "patients", "size": "2 MB"}

            client = TestClient(app)
            resp = client.get("/api/get_size/patients")

        assert resp.status_code == 200
        assert resp.json()["size"] == "2 MB"

    def test_not_found(self):
        app, mock_db = _make_app()

        with patch("api.tables.get_database_size") as mock_get_size:
            mock_get_size.return_value = None

            client = TestClient(app)
            resp = client.get("/api/get_size/nonexistent")

        assert resp.status_code == 404
