"""
Integration tests for the corrupted rows feature.

Tests the resolve endpoint and type validation.
The resolve endpoint updates the main table record; the sidecar JOIN
automatically unflags columns once the main value is no longer NULL.

Requires a running server at localhost:8000 with a reflected DB.
"""

import requests
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Add the 'server' directory to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
server_dir = os.path.dirname(current_dir)
sys.path.insert(0, server_dir)

from core.deps import get_db
from core.database import Base, reflect_db
from crud.base import BaseRepository, model_to_dict
from sqlalchemy import Integer, Float, Boolean, String
TARGET_TABLE = "test_database"  # Must have integer 'age' column for validation tests
API_URL = "http://localhost:8000"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def setup_target_row():
    """
    Create a row in test_database with a NULL age (simulating TRY_CAST failure).
    Yields the target_row_id. Cleans up on teardown.
    """
    reflect_db()
    target_model = Base.classes.get(TARGET_TABLE)

    if not target_model:
        pytest.fail(f"Test setup failed: Could not find model for '{TARGET_TABLE}'")

    db = next(get_db())
    target_item = None

    try:
        target_item = BaseRepository(target_model).create(db, {
            "first_name": "Corrupted",
            "last_name": "TestUser",
            "age": None
        })
        db.commit()
        db.refresh(target_item)
        yield target_item.id
    finally:
        try:
            if target_item:
                BaseRepository(target_model).delete(db, target_item.id)
                db.commit()
        except Exception as e:
            db.rollback()
            print(f"Error during teardown: {e}")
        db.close()


# ===========================================================================
# TEST GROUP 1: Resolve (Heal) Endpoint
# ===========================================================================

class TestResolveEndpoint:
    """Tests for PATCH /api/{table_name}/{row_id}/resolve."""

    def test_resolve_corrupted_row_success(self, setup_target_row):
        """
        Resolving with a valid integer value should:
        1. Update the primary record's age
        2. Return the updated record as a TableRow dict
        """
        target_id = setup_target_row

        r = requests.patch(
            f"{API_URL}/api/{TARGET_TABLE}/{target_id}/resolve",
            json={"corrections": {"age": "25"}}
        )
        assert r.status_code == 200
        data = r.json()
        # Response is a flat TableRow, not a status wrapper
        assert data["age"] == 25
        assert data["first_name"] == "Corrupted"
        assert "status" not in data
        assert "message" not in data

    def test_resolve_with_invalid_type_rejects(self, setup_target_row):
        """
        Resolving with 'abc' for an integer column should return 400
        due to type validation.
        """
        target_id = setup_target_row

        r = requests.patch(
            f"{API_URL}/api/{TARGET_TABLE}/{target_id}/resolve",
            json={"corrections": {"age": "not_a_number"}}
        )
        assert r.status_code == 400
        assert "Validation Error" in r.json()["detail"]
        assert "integer" in r.json()["detail"].lower()

    def test_resolve_nonexistent_table(self):
        """Resolving against a nonexistent table returns 404/500."""
        r = requests.patch(
            f"{API_URL}/api/nonexistent_table_xyz/1/resolve",
            json={"corrections": {"col": "val"}}
        )
        assert r.status_code in (404, 500)

    def test_resolve_nonexistent_row(self):
        """Resolving a nonexistent row returns 404."""
        r = requests.patch(
            f"{API_URL}/api/{TARGET_TABLE}/999999/resolve",
            json={"corrections": {"age": "25"}}
        )
        assert r.status_code == 404

    def test_resolve_nonexistent_column(self, setup_target_row):
        """Resolving with a column that doesn't exist returns 400."""
        target_id = setup_target_row

        r = requests.patch(
            f"{API_URL}/api/{TARGET_TABLE}/{target_id}/resolve",
            json={"corrections": {"nonexistent_column": "value"}}
        )
        assert r.status_code == 400
        assert "does not exist" in r.json()["detail"]

    def test_resolve_with_valid_integer_string(self, setup_target_row):
        """A string that represents a valid integer ('42') should be accepted and cast."""
        target_id = setup_target_row

        r = requests.patch(
            f"{API_URL}/api/{TARGET_TABLE}/{target_id}/resolve",
            json={"corrections": {"age": "42"}}
        )
        assert r.status_code == 200
        # Response is a flat TableRow
        assert r.json()["age"] == 42


# ===========================================================================
# TEST GROUP 2: Type Validation Unit Tests (no server required)
# ===========================================================================

class TestTypeValidation:
    """Unit tests for the _validate_and_cast helper function."""

    def setup_method(self):
        """Import the validation function."""
        from api.corrupted_rows import _validate_and_cast
        self.validate = _validate_and_cast

    def test_integer_valid(self):
        assert self.validate("age", "25", Integer()) == 25
        assert self.validate("age", 25, Integer()) == 25
        assert self.validate("age", "0", Integer()) == 0

    def test_integer_invalid(self):
        with pytest.raises(ValueError, match="integer"):
            self.validate("age", "abc", Integer())
        with pytest.raises(ValueError, match="integer"):
            self.validate("age", "12.5", Integer())

    def test_float_valid(self):
        assert self.validate("score", "3.14", Float()) == 3.14
        assert self.validate("score", "42", Float()) == 42.0

    def test_float_invalid(self):
        with pytest.raises(ValueError, match="number"):
            self.validate("score", "not_a_number", Float())

    def test_boolean_valid(self):
        assert self.validate("active", "true", Boolean()) is True
        assert self.validate("active", "false", Boolean()) is False
        assert self.validate("active", "1", Boolean()) is True
        assert self.validate("active", "0", Boolean()) is False
        assert self.validate("active", "yes", Boolean()) is True
        assert self.validate("active", "no", Boolean()) is False
        assert self.validate("active", True, Boolean()) is True

    def test_boolean_invalid(self):
        with pytest.raises(ValueError, match="boolean"):
            self.validate("active", "maybe", Boolean())

    def test_none_passthrough(self):
        assert self.validate("any_col", None, Integer()) is None

    def test_string_passthrough(self):
        assert self.validate("name", "hello", String()) == "hello"


# ===========================================================================
# TEST GROUP 3: ETL Sidecar — All rows in clean table
# ===========================================================================

class TestETLSidecarBehavior:
    """
    Verify that ALL rows land in the clean table
    (corrupted values as NULL via TRY_CAST) AND in corrupted_rows.
    Uses in-memory DuckDB — no Postgres or dlt required.
    """

    @pytest.fixture
    def duckdb_con(self):
        import duckdb
        con = duckdb.connect(database=":memory:")
        yield con
        con.close()

    @pytest.fixture(autouse=True)
    def stub_dlt(self):
        """Stub out dlt_pipeline to avoid importing dlt."""
        import types
        fake = types.ModuleType("services.dlt_pipeline")
        fake.CORRUPTED_ROWS_NAME = "corrupted_rows"
        fake.RAW_DATA_NAME = "raw_staging"
        fake.CLEAN_DATA_NAME = "clean_data"
        class MockDLTPipeline:
            def load_to_postgres(self, con): pass
        fake.DLTPipeline = MockDLTPipeline
        sys.modules["services.dlt_pipeline"] = fake

    def _seed_and_validate(self, con, columns, rows, schema_map):
        """Helper to seed raw_staging and run validation."""
        from services.etl_processor import _validate_and_split_data

        col_defs = ", ".join(f"{col} VARCHAR" for col in columns)
        con.execute(f"CREATE TABLE raw_staging ({col_defs})")
        placeholders = ", ".join(["?"] * len(columns))
        for row in rows:
            con.execute(f"INSERT INTO raw_staging VALUES ({placeholders})", list(row))

        return _validate_and_split_data(con, schema_map)

    def test_all_rows_in_clean_table_including_corrupted(self, duckdb_con):
        """
        Every row—including corrupted ones—should exist in clean_data.
        Corrupted values should be NULL (via TRY_CAST).
        """
        columns = ["name", "age"]
        rows = [
            ("Alice", "30"),    # clean
            ("Bob", "ABC"),     # corrupted — age should be NULL in clean
            ("Charlie", "25"),  # clean
        ]

        error_count = self._seed_and_validate(duckdb_con, columns, rows, {"name": "VARCHAR", "age": "INTEGER"})
        assert error_count == 1  # Only Bob

        # ALL 3 rows should be in clean_data
        clean_count = duckdb_con.execute("SELECT COUNT(*) FROM clean_data").fetchone()[0]
        assert clean_count == 3, f"Expected 3 rows in clean_data (all rows), got {clean_count}"

        # Bob's age should be NULL in clean_data
        bob_age = duckdb_con.execute(
            "SELECT age FROM clean_data WHERE name = 'Bob'"
        ).fetchone()[0]
        assert bob_age is None, f"Bob's age should be NULL via TRY_CAST, got {bob_age}"

        # Alice and Charlie should have correct ages
        alice_age = duckdb_con.execute(
            "SELECT age FROM clean_data WHERE name = 'Alice'"
        ).fetchone()[0]
        assert alice_age == 30

    def test_corrupted_rows_also_populated(self, duckdb_con):
        """Corrupted rows sidecar should still capture the bad rows."""
        columns = ["name", "score"]
        rows = [
            ("Alice", "100"),
            ("Bob", "HIGH"),   # corrupted
        ]

        error_count = self._seed_and_validate(duckdb_con, columns, rows, {"score": "INTEGER"})
        assert error_count == 1

        corrupted = duckdb_con.execute(
            "SELECT name, score FROM corrupted_rows"
        ).fetchall()
        assert len(corrupted) == 1
        assert corrupted[0][0] == "Bob"
        assert corrupted[0][1] == "HIGH"  # Raw value preserved

    def test_original_csv_row_id_in_both_tables(self, duckdb_con):
        """Both clean_data and corrupted_rows should have original_csv_row_id."""
        columns = ["val"]
        rows = [("10",), ("BAD",)]

        self._seed_and_validate(duckdb_con, columns, rows, {"val": "INTEGER"})

        clean_cols = [desc[0] for desc in duckdb_con.execute("SELECT * FROM clean_data LIMIT 0").description]
        corrupted_cols = [desc[0] for desc in duckdb_con.execute("SELECT * FROM corrupted_rows LIMIT 0").description]

        assert "original_csv_row_id" in clean_cols
        assert "original_csv_row_id" in corrupted_cols


# ===========================================================================
# TEST GROUP 4: Resolve request body shape (unit tests)
# ===========================================================================

class TestResolveRequestBody:
    """The PATCH resolve endpoint expects { corrections: {...} }."""

    def test_resolution_requires_corrections_key(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from api.corrupted_rows import router
        from core.deps import get_db

        app = FastAPI()
        app.include_router(router)

        mock_db = MagicMock()
        def override_get_db():
            yield mock_db
        app.dependency_overrides[get_db] = override_get_db

        client = TestClient(app)

        # Sending bare fixes without corrections wrapper should fail validation
        resp = client.patch("/api/test_table/1/resolve", json={"name": "Alice"})
        assert resp.status_code == 422  # Pydantic validation error

    def test_resolution_accepts_corrections_wrapper(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from api.corrupted_rows import router
        from core.deps import get_db
        from sqlalchemy import String

        app = FastAPI()
        app.include_router(router)

        mock_db = MagicMock()
        def override_get_db():
            yield mock_db
        app.dependency_overrides[get_db] = override_get_db

        mock_record = MagicMock()
        mock_record.id = 1
        mock_model = MagicMock()

        with patch("api.corrupted_rows.get_internal_model_class") as mock_get_model:
            mock_get_model.return_value = mock_model
            mock_db.query.return_value.filter.return_value.first.return_value = mock_record

            mock_mapper = MagicMock()
            mock_col_attr = MagicMock()
            mock_col_attr.key = "name"
            mock_col_inner = MagicMock()
            mock_col_inner.type = String()
            mock_col_attr.columns = [mock_col_inner]
            mock_mapper.column_attrs = [mock_col_attr]

            with patch("api.corrupted_rows.sa_inspect", return_value=mock_mapper):
                mock_record.name = "old_value"
                with patch("api.corrupted_rows.model_to_dict", return_value={"id": 1, "name": "Alice"}):
                    client = TestClient(app)
                    resp = client.patch("/api/test_table/1/resolve", json={
                        "corrections": {"name": "Alice"}
                    })

        assert resp.status_code == 200
        data = resp.json()
        # Response is now a flat TableRow dict
        assert data["id"] == 1
        assert data["name"] == "Alice"
        assert "status" not in data


class TestResolveNoDoubleCommit:
    """resolve_corrupted_row should use flush(), not commit()."""

    def test_no_explicit_commit_call(self):
        """Verify the function source uses db.flush() not db.commit()."""
        import inspect
        from api.corrupted_rows import resolve_corrupted_row
        source = inspect.getsource(resolve_corrupted_row)
        assert "db.commit()" not in source
        assert "db.flush()" in source
