"""
Unit tests for server/api/rows.py — CRUD endpoints for dynamic table rows.

All tests use FastAPI TestClient with dependency overrides (no live services).
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.deps import get_db, get_model_class
from api.rows import router


# Test helpers

def _make_app():
    app = FastAPI()
    app.include_router(router)

    mock_db = MagicMock()

    def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    return app, mock_db


def _mock_mapper(columns, pk_columns=None):
    """Create a mock SQLAlchemy mapper with given column names."""
    mapper = MagicMock()
    cols = []
    for name in columns:
        c = MagicMock()
        c.key = name
        cols.append(c)
    mapper.column_attrs = cols

    pk_cols = []
    for name in (pk_columns or ["id"]):
        c = MagicMock()
        c.key = name
        pk_cols.append(c)
    mapper.primary_key = pk_cols
    return mapper


# Get all items tests

class TestGetAllItems:

    def test_simple_path_without_corrupted_rows(self):
        """When corrupted_rows table is not available, use simple repo path."""
        app, mock_db = _make_app()
        mock_model = MagicMock()

        app.dependency_overrides[get_model_class] = lambda table_name: mock_model

        with patch("api.rows.get_class_strict", return_value=None), \
             patch("api.rows.get_repository") as mock_get_repo:

            mock_repo = MagicMock()
            mock_item = MagicMock()
            mock_item.__table__ = MagicMock()
            mock_item.__table__.columns = []
            mock_repo.get_all.return_value = ([mock_item], 1)
            mock_get_repo.return_value = mock_repo

            with patch("api.rows.model_to_dict", return_value={"id": 1, "name": "Alice"}):
                client = TestClient(app)
                resp = client.get("/api/test_table")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["data"][0]["name"] == "Alice"

    def test_with_corrupted_rows_join(self):
        """When corrupted_rows exists, items should include _is_corrupted flag."""
        app, mock_db = _make_app()
        mock_model = MagicMock()
        mock_model.original_csv_row_id = MagicMock()

        app.dependency_overrides[get_model_class] = lambda table_name: mock_model

        mock_corrupted_model = MagicMock()
        mock_corrupted_model.original_csv_row_id = MagicMock()

        mapper = _mock_mapper(["id", "name", "original_csv_row_id"])

        # Build a mock select chain: select(...).outerjoin(...).offset(...).limit(...)
        mock_stmt = MagicMock()
        mock_stmt.outerjoin.return_value = mock_stmt
        mock_stmt.offset.return_value = mock_stmt
        mock_stmt.limit.return_value = mock_stmt

        with patch("api.rows.get_class_strict", return_value=mock_corrupted_model), \
             patch("api.rows.inspect", return_value=mapper), \
             patch("api.rows.select", return_value=mock_stmt), \
             patch("api.rows.model_to_dict") as mock_to_dict:

            # Mock the db.execute result
            mock_main_row = MagicMock()
            mock_corrupted_row = None  # No corruption
            mock_db.execute.return_value.all.return_value = [(mock_main_row, mock_corrupted_row)]
            mock_db.query.return_value.count.return_value = 1

            mock_to_dict.return_value = {"id": 1, "name": "Alice", "original_csv_row_id": 1}

            client = TestClient(app)
            resp = client.get("/api/test_table")

        assert resp.status_code == 200
        data = resp.json()
        assert data["data"][0]["_is_corrupted"] is False
        assert data["data"][0]["_error_context"] is None


# Get one item tests

class TestGetOneItem:

    def test_success(self):
        app, mock_db = _make_app()
        mock_model = MagicMock()
        app.dependency_overrides[get_model_class] = lambda table_name: mock_model

        with patch("api.rows.get_repository") as mock_get_repo, \
             patch("api.rows.model_to_dict", return_value={"id": 1, "name": "Alice"}):
            mock_repo = MagicMock()
            mock_repo.get_by_id.return_value = MagicMock()
            mock_get_repo.return_value = mock_repo

            client = TestClient(app)
            resp = client.get("/api/test_table/1")

        assert resp.status_code == 200
        assert resp.json()["name"] == "Alice"

    def test_not_found(self):
        app, mock_db = _make_app()
        mock_model = MagicMock()
        app.dependency_overrides[get_model_class] = lambda table_name: mock_model

        with patch("api.rows.get_repository") as mock_get_repo:
            mock_repo = MagicMock()
            mock_repo.get_by_id.return_value = None
            mock_get_repo.return_value = mock_repo

            client = TestClient(app)
            resp = client.get("/api/test_table/999")

        assert resp.status_code == 404


# Create item tests

class TestCreateItem:

    def test_success(self):
        app, mock_db = _make_app()
        mock_model = MagicMock()
        mock_model.__table__ = MagicMock(schema="public")
        mapper = _mock_mapper(["id", "name", "age"])
        app.dependency_overrides[get_model_class] = lambda table_name: mock_model

        with patch("api.rows.inspect", return_value=mapper), \
             patch("api.rows.get_repository") as mock_get_repo, \
             patch("api.rows.model_to_dict", return_value={"id": 1, "name": "Alice", "age": 30}), \
             patch("api.rows.log_metadata_update"):
            mock_repo = MagicMock()
            mock_item = MagicMock()
            mock_item.id = 1
            mock_repo.create.return_value = mock_item
            mock_get_repo.return_value = mock_repo

            client = TestClient(app)
            resp = client.post("/api/test_table", json={"name": "Alice", "age": 30})

        assert resp.status_code == 200
        assert resp.json()["name"] == "Alice"

    def test_invalid_field(self):
        app, mock_db = _make_app()
        mock_model = MagicMock()
        mock_model.__table__ = MagicMock(schema="public")
        mapper = _mock_mapper(["id", "name"])
        app.dependency_overrides[get_model_class] = lambda table_name: mock_model

        with patch("api.rows.inspect", return_value=mapper):
            client = TestClient(app)
            resp = client.post("/api/test_table", json={"nonexistent": "value"})

        assert resp.status_code == 400
        assert "Invalid field" in resp.json()["detail"]


# Update item tests

class TestUpdateItem:

    def test_success(self):
        app, mock_db = _make_app()
        mock_model = MagicMock()
        mock_model.__table__ = MagicMock(schema="public")
        mapper = _mock_mapper(["id", "name"])
        app.dependency_overrides[get_model_class] = lambda table_name: mock_model

        with patch("api.rows.inspect", return_value=mapper), \
             patch("api.rows.get_repository") as mock_get_repo, \
             patch("api.rows.model_to_dict", return_value={"id": 1, "name": "Updated"}), \
             patch("api.rows.log_metadata_update"):
            mock_repo = MagicMock()
            mock_repo.get_by_id.return_value = MagicMock()
            mock_repo.update.return_value = MagicMock()
            mock_get_repo.return_value = mock_repo

            client = TestClient(app)
            resp = client.put("/api/test_table/1", json={"name": "Updated"})

        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated"

    def test_not_found(self):
        app, mock_db = _make_app()
        mock_model = MagicMock()
        mock_model.__table__ = MagicMock(schema="public")
        app.dependency_overrides[get_model_class] = lambda table_name: mock_model

        with patch("api.rows.get_repository") as mock_get_repo:
            mock_repo = MagicMock()
            mock_repo.get_by_id.return_value = None
            mock_get_repo.return_value = mock_repo

            client = TestClient(app)
            resp = client.put("/api/test_table/999", json={"name": "X"})

        assert resp.status_code == 404

    def test_invalid_field(self):
        app, mock_db = _make_app()
        mock_model = MagicMock()
        mock_model.__table__ = MagicMock(schema="public")
        mapper = _mock_mapper(["id", "name"])
        app.dependency_overrides[get_model_class] = lambda table_name: mock_model

        with patch("api.rows.inspect", return_value=mapper), \
             patch("api.rows.get_repository") as mock_get_repo:
            mock_repo = MagicMock()
            mock_repo.get_by_id.return_value = MagicMock()
            mock_get_repo.return_value = mock_repo

            client = TestClient(app)
            resp = client.put("/api/test_table/1", json={"bad_field": "value"})

        assert resp.status_code == 400
        assert "Invalid field" in resp.json()["detail"]

    def test_pk_update_rejected(self):
        app, mock_db = _make_app()
        mock_model = MagicMock()
        mock_model.__table__ = MagicMock(schema="public")
        mapper = _mock_mapper(["id", "name"], pk_columns=["id"])
        app.dependency_overrides[get_model_class] = lambda table_name: mock_model

        with patch("api.rows.inspect", return_value=mapper), \
             patch("api.rows.get_repository") as mock_get_repo:
            mock_repo = MagicMock()
            mock_repo.get_by_id.return_value = MagicMock()
            mock_get_repo.return_value = mock_repo

            client = TestClient(app)
            resp = client.put("/api/test_table/1", json={"id": 999})

        assert resp.status_code == 400
        assert "primary key" in resp.json()["detail"].lower()

    def test_dlt_cleanup_corrupted_rows(self):
        """Updating a DLT table should clean up any matching corrupted_rows."""
        app, mock_db = _make_app()
        mock_model = MagicMock()
        mock_model.__table__ = MagicMock(schema="dlt_dataset")  # Simulates DLT table
        mapper = _mock_mapper(["id", "name", "original_csv_row_id"])
        app.dependency_overrides[get_model_class] = lambda table_name: mock_model
        
        mock_corrupted_model = MagicMock()
        mock_corrupted_model.original_csv_row_id = MagicMock()

        # is_dlt_table will return True because schema is dlt_dataset
        with patch("api.rows.is_dlt_table", return_value=True), \
             patch("api.rows.inspect", return_value=mapper), \
             patch("api.rows.get_repository") as mock_get_repo, \
             patch("api.rows.model_to_dict") as mock_to_dict, \
             patch("api.rows.log_metadata_update"), \
             patch("api.rows.get_class_strict", return_value=mock_corrupted_model):
             
            mock_repo = MagicMock()
            mock_item = MagicMock()
            mock_repo.get_by_id.return_value = mock_item
            
            # The returned item has original_csv_row_id
            updated_mock_item = MagicMock()
            updated_mock_item.original_csv_row_id = "row-123"
            mock_repo.update.return_value = updated_mock_item
            
            mock_get_repo.return_value = mock_repo
            mock_to_dict.return_value = {"id": 1, "name": "Updated", "original_csv_row_id": "row-123"}

            client = TestClient(app)
            resp = client.put("/api/test_table/1", json={"name": "Updated"})

        assert resp.status_code == 200
        # Check that the delete query was constructed for corrupted_rows
        mock_db.query.assert_any_call(mock_corrupted_model)
        mock_db.query.return_value.filter.assert_called()
        mock_db.query.return_value.filter.return_value.delete.assert_called_once()
        mock_db.commit.assert_called()


# Delete item tests

class TestDeleteItem:

    def test_success(self):
        app, mock_db = _make_app()
        mock_model = MagicMock()
        mock_model.__table__ = MagicMock(schema="public")
        app.dependency_overrides[get_model_class] = lambda table_name: mock_model

        with patch("api.rows.get_repository") as mock_get_repo, \
             patch("api.rows.log_metadata_update"):
            mock_repo = MagicMock()
            mock_repo.delete.return_value = True
            mock_get_repo.return_value = mock_repo

            client = TestClient(app)
            resp = client.delete("/api/test_table/1")

        assert resp.status_code == 200
        assert "deleted" in resp.json()["message"].lower()

    def test_not_found(self):
        app, mock_db = _make_app()
        mock_model = MagicMock()
        mock_model.__table__ = MagicMock(schema="public")
        app.dependency_overrides[get_model_class] = lambda table_name: mock_model

        with patch("api.rows.get_repository") as mock_get_repo:
            mock_repo = MagicMock()
            mock_repo.delete.return_value = False
            mock_get_repo.return_value = mock_repo

            client = TestClient(app)
            resp = client.delete("/api/test_table/999")

        assert resp.status_code == 404

    def test_dlt_cleanup_corrupted_rows_on_delete(self):
        """Deleting from a DLT table should clean up any matching corrupted_rows."""
        app, mock_db = _make_app()
        mock_model = MagicMock()
        mock_model.__table__ = MagicMock(schema="dlt_dataset")  # Simulates DLT table
        app.dependency_overrides[get_model_class] = lambda table_name: mock_model

        mock_corrupted_model = MagicMock()
        mock_corrupted_model.original_csv_row_id = MagicMock()

        with patch("api.rows.is_dlt_table", return_value=True), \
             patch("api.rows.get_repository") as mock_get_repo, \
             patch("api.rows.log_metadata_update"), \
             patch("api.rows.get_class_strict", return_value=mock_corrupted_model):
             
            mock_repo = MagicMock()
            mock_item = MagicMock()
            mock_item.original_csv_row_id = "row-999"
            mock_repo.get_by_id.return_value = mock_item
            mock_repo.delete.return_value = True
            mock_get_repo.return_value = mock_repo

            client = TestClient(app)
            resp = client.delete("/api/test_table/1")

        assert resp.status_code == 200
        # Check that the delete query was constructed for corrupted_rows
        mock_db.query.assert_any_call(mock_corrupted_model)
        mock_db.query.return_value.filter.assert_called()
        mock_db.query.return_value.filter.return_value.delete.assert_called_once()
        mock_db.commit.assert_called()


# Match items (search) tests

class TestMatchItems:

    def test_success(self):
        app, mock_db = _make_app()
        mock_model = MagicMock()
        app.dependency_overrides[get_model_class] = lambda table_name: mock_model

        with patch("api.rows.get_repository") as mock_get_repo, \
             patch("api.rows.model_to_dict", return_value={"id": 1, "name": "Alice"}):
            mock_repo = MagicMock()
            mock_repo.filter_text.return_value = ([MagicMock()], 1)
            mock_get_repo.return_value = mock_repo

            client = TestClient(app)
            resp = client.get("/api/test_table/search/name/Alice")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1

    def test_error(self):
        app, mock_db = _make_app()
        mock_model = MagicMock()
        app.dependency_overrides[get_model_class] = lambda table_name: mock_model

        with patch("api.rows.get_repository") as mock_get_repo:
            mock_repo = MagicMock()
            mock_repo.filter_text.side_effect = Exception("column not found")
            mock_get_repo.return_value = mock_repo

            client = TestClient(app)
            resp = client.get("/api/test_table/search/bad_col/foo")

        assert resp.status_code == 400


# log_metadata_update tests

class TestLogMetadataUpdate:

    def test_existing_record(self):
        from api.rows import log_metadata_update

        mock_db = MagicMock()
        mock_creation = MagicMock()
        mock_creation.file_id = 42

        # Build a mock select chain: select(...).where(...) -> mock_stmt
        mock_stmt = MagicMock()
        mock_stmt.where.return_value = mock_stmt

        with patch("api.rows.get_internal_model_class") as mock_get_model, \
             patch("api.rows.select", return_value=mock_stmt):
            mock_creation_model = MagicMock()
            mock_updates_model = MagicMock()
            mock_get_model.side_effect = [mock_creation_model, mock_updates_model]

            mock_db.execute.return_value.scalars.return_value.first.return_value = mock_creation

            log_metadata_update(mock_db, "patients", "admin")

            # Should have added an update record and flushed
            mock_db.add.assert_called()
            mock_db.flush.assert_called()

    def test_auto_create_record(self):
        from api.rows import log_metadata_update

        mock_db = MagicMock()

        # Build a mock select chain: select(...).where(...) -> mock_stmt
        mock_stmt = MagicMock()
        mock_stmt.where.return_value = mock_stmt

        with patch("api.rows.get_internal_model_class") as mock_get_model, \
             patch("api.rows.select", return_value=mock_stmt):
            mock_creation_model = MagicMock()
            mock_updates_model = MagicMock()
            mock_get_model.side_effect = [mock_creation_model, mock_updates_model]

            # No creation record found
            mock_db.execute.return_value.scalars.return_value.first.return_value = None

            log_metadata_update(mock_db, "patients")

            # Should have added both creation and update records
            assert mock_db.add.call_count >= 1

    def test_swallows_exceptions(self):
        from api.rows import log_metadata_update

        mock_db = MagicMock()

        with patch("api.rows.get_internal_model_class", side_effect=Exception("boom")):
            # Should not raise
            log_metadata_update(mock_db, "patients")
