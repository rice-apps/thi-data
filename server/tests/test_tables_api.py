"""
Unit tests for server/api/tables.py — table listing, metadata, schema, size, delete.

All tests use mocked dependencies (no live services).
"""

import pytest
from unittest.mock import patch, MagicMock, call
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

        with patch("api.tables.db_module") as mock_db_mod:
            mock_db_mod.Base.classes.keys.return_value = [
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

    def test_hides_test_databases(self):
        app, _ = _make_app()

        with patch("api.tables.db_module") as mock_db_mod:
            mock_db_mod.Base.classes.keys.return_value = [
                "owls",
                "test_database",
                "thi_database",
            ]

            client = TestClient(app)
            resp = client.get("/api/tables")

        assert resp.status_code == 200
        tables = resp.json()["tables"]
        assert "owls" in tables
        assert "test_database" not in tables
        assert "thi_database" not in tables

    def test_hides_corrupted_suffix_tables(self):
        app, _ = _make_app()

        with patch("api.tables.db_module") as mock_db_mod:
            mock_db_mod.Base.classes.keys.return_value = [
                "owls",
                "owls__corrupted",
                "corrupted_rows",
                "lab_results",
            ]

            client = TestClient(app)
            resp = client.get("/api/tables")

        assert resp.status_code == 200
        tables = resp.json()["tables"]
        assert "owls" in tables
        assert "lab_results" in tables
        # Internal tables hidden
        assert "owls__corrupted" not in tables
        assert "corrupted_rows" not in tables


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

        with patch("api.tables.db_module") as mock_db_mod, \
             patch("api.tables.get_tables_metadata") as mock_get_meta, \
             patch("api.tables.get_internal_model_class") as mock_get_internal:
            mock_db_mod.Base.classes.keys.return_value = ["patients", "file_registry"]
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

    def test_schema_excludes_internal_columns(self):
        app, _ = _make_app()

        mock_model = MagicMock()
        mapper = MagicMock()
        col_id = MagicMock()
        col_id.key = "id"
        col_rowid = MagicMock()
        col_rowid.key = "original_csv_row_id"
        col_name = MagicMock()
        col_name.key = "name"
        col_age = MagicMock()
        col_age.key = "age"
        mapper.column_attrs = [col_id, col_rowid, col_name, col_age]

        app.dependency_overrides[get_model_class] = lambda table_name: mock_model

        with patch("api.tables.inspect", return_value=mapper):
            client = TestClient(app)
            resp = client.get("/api/schema/patients")

        assert resp.status_code == 200
        columns = resp.json()["columns"]
        assert "id" not in columns
        assert "original_csv_row_id" not in columns
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


# ---------------------------------------------------------------------------
# DELETE /api/tables/{table_name}
# ---------------------------------------------------------------------------

class TestDeleteTable:

    def _make_meta_mocks(self, db):
        """Return (MetadataCreation mock, MetadataUpdates mock, FileRegistry mock)
        wired so db.query(...).filter(...).all() and .delete() behave correctly."""
        creation_record = MagicMock()
        creation_record.id = "uuid-1"

        mock_creation_cls = MagicMock()
        mock_updates_cls = MagicMock()
        mock_registry_cls = MagicMock()

        creation_query = MagicMock()
        creation_query.filter.return_value.all.return_value = [creation_record]
        updates_query = MagicMock()
        updates_query.filter.return_value.delete.return_value = 1
        registry_query = MagicMock()
        registry_query.filter.return_value.delete.return_value = 1

        def db_query_side_effect(cls):
            if cls is mock_creation_cls:
                return creation_query
            if cls is mock_updates_cls:
                return updates_query
            return registry_query

        db.query.side_effect = db_query_side_effect
        return mock_creation_cls, mock_updates_cls, mock_registry_cls, creation_record

    def test_deletes_table_and_metadata(self):
        app, mock_db = _make_app()
        mock_creation, mock_updates, mock_registry, creation_record = (
            self._make_meta_mocks(mock_db)
        )

        with patch("api.tables.get_class", return_value=MagicMock()) as mock_get_class, \
             patch("api.tables.get_internal_model_class") as mock_get_internal, \
             patch("api.tables.get_file_registry_model", return_value=mock_registry), \
             patch("api.tables.reflect_db") as mock_reflect, \
             patch("api.tables.settings") as mock_settings:

            mock_settings.DLT_DATASET = "clinical_data"
            mock_get_internal.side_effect = lambda name: (
                mock_creation if "creation" in name else mock_updates
            )

            client = TestClient(app)
            resp = client.delete("/api/tables/patients")

        assert resp.status_code == 200
        assert resp.json() == {"deleted": "patients"}
        mock_db.delete.assert_called_once_with(creation_record)
        mock_db.commit.assert_called_once()
        mock_reflect.assert_called_once()

        executed_sqls = [str(call_args[0][0]) for call_args in mock_db.execute.call_args_list]
        assert any("patients" in s for s in executed_sqls)
        assert any("patients__corrupted" in s for s in executed_sqls)

    def test_rejects_hidden_table(self):
        app, mock_db = _make_app()

        client = TestClient(app)
        resp = client.delete("/api/tables/metadata_creation")

        assert resp.status_code == 403

    def test_rejects_corrupted_suffix_table(self):
        app, mock_db = _make_app()

        client = TestClient(app)
        resp = client.delete("/api/tables/patients__corrupted")

        assert resp.status_code == 403

    def test_404_when_table_not_in_orm(self):
        app, mock_db = _make_app()

        with patch("api.tables.get_class", return_value=None):
            client = TestClient(app)
            resp = client.delete("/api/tables/nonexistent")

        assert resp.status_code == 404

    def test_delete_clears_repo_cache(self):
        """After deletion, _repo_cache entries for the table and its corrupted
        companion are removed so stale BaseRepository singletons don't persist."""
        app, mock_db = _make_app()
        mock_creation, mock_updates, mock_registry, creation_record = (
            self._make_meta_mocks(mock_db)
        )

        with patch("api.tables.get_class", return_value=MagicMock()), \
             patch("api.tables.get_internal_model_class") as mock_get_internal, \
             patch("api.tables.get_file_registry_model", return_value=mock_registry), \
             patch("api.tables.reflect_db"), \
             patch("api.tables._repo_cache", {"patients": "repo1", "patients__corrupted": "repo2", "other": "repo3"}) as mock_cache, \
             patch("api.tables.settings") as mock_settings:

            mock_settings.DLT_DATASET = "clinical_data"
            mock_get_internal.side_effect = lambda name: (
                mock_creation if "creation" in name else mock_updates
            )

            client = TestClient(app)
            resp = client.delete("/api/tables/patients")

        assert resp.status_code == 200
        assert "patients" not in mock_cache
        assert "patients__corrupted" not in mock_cache
        assert "other" in mock_cache

    def test_drops_corrupted_companion_even_when_no_metadata(self):
        """Tables without metadata_creation records are still fully dropped."""
        app, mock_db = _make_app()

        mock_creation_cls = MagicMock()
        mock_updates_cls = MagicMock()
        mock_registry_cls = MagicMock()

        creation_query = MagicMock()
        creation_query.filter.return_value.all.return_value = []
        registry_query = MagicMock()
        registry_query.filter.return_value.delete.return_value = 0

        def db_query_side_effect(cls):
            if cls is mock_creation_cls:
                return creation_query
            return registry_query

        mock_db.query.side_effect = db_query_side_effect

        with patch("api.tables.get_class", return_value=MagicMock()), \
             patch("api.tables.get_internal_model_class") as mock_get_internal, \
             patch("api.tables.get_file_registry_model", return_value=mock_registry_cls), \
             patch("api.tables.reflect_db"), \
             patch("api.tables.settings") as mock_settings:

            mock_settings.DLT_DATASET = "clinical_data"
            mock_get_internal.side_effect = lambda name: (
                mock_creation_cls if "creation" in name else mock_updates_cls
            )

            client = TestClient(app)
            resp = client.delete("/api/tables/orphan_table")

        assert resp.status_code == 200
        executed_sqls = [str(c[0][0]) for c in mock_db.execute.call_args_list]
        assert any("orphan_table" in s for s in executed_sqls)
        assert any("orphan_table__corrupted" in s for s in executed_sqls)
