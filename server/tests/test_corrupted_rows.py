"""
Integration tests for the corrupted rows feature.

Tests the complete lifecycle: create, read, delete, and resolve corrupted rows.
Also tests type validation in the resolve endpoint.

Requires a running server at localhost:8000 with a reflected DB.
"""

import requests
import os
import sys
import pytest

# Add the 'server' directory to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
server_dir = os.path.dirname(current_dir)
sys.path.insert(0, server_dir)

from core.deps import get_db
from core.database import Base, reflect_db
from crud.base import BaseRepository, model_to_dict
from sqlalchemy import Integer, Float, Boolean, String
CORRUPTED_ROWS_TABLE = "corrupted_rows"
TARGET_TABLE = "test_database"  # Must have integer 'age' column for validation tests
API_URL = "http://localhost:8000"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def setup_corrupted_row():
    """Create a corrupted row entry and yield its ID, then clean up."""
    reflect_db()
    model_class = Base.classes.get(CORRUPTED_ROWS_TABLE)
    if not model_class:
        pytest.fail(f"Test setup failed: Could not find model for table '{CORRUPTED_ROWS_TABLE}'")

    db = next(get_db())
    new_item_data = {
        "target_table": "test_table",
        "row_id": "123",
        "error_reason": "Test corruption message"
    }

    created_item = None
    try:
        created_item = BaseRepository(model_class).create(db, new_item_data)
        db.commit()
        db.refresh(created_item)
        item_id = created_item.id
        yield item_id
    finally:
        if created_item:
            try:
                BaseRepository(model_class).delete(db, created_item.id)
                db.commit()
            except Exception as e:
                db.rollback()
                print(f"Error during teardown: {e}")
        db.close()


@pytest.fixture(scope="function")
def setup_target_row_with_corruption():
    """
    Create a row in test_database with a NULL age (simulating TRY_CAST failure),
    and a matching corrupted_rows entry. Yields (target_row_id, corrupted_entry_id).
    Cleans up both on teardown.
    """
    reflect_db()
    target_model = Base.classes.get(TARGET_TABLE)
    corrupted_model = Base.classes.get(CORRUPTED_ROWS_TABLE)

    if not target_model:
        pytest.fail(f"Test setup failed: Could not find model for '{TARGET_TABLE}'")
    if not corrupted_model:
        pytest.fail(f"Test setup failed: Could not find model for '{CORRUPTED_ROWS_TABLE}'")

    db = next(get_db())
    target_item = None
    corrupted_item = None

    try:
        # Create a row with NULL age (simulating a corrupted cast)
        target_item = BaseRepository(target_model).create(db, {
            "first_name": "Corrupted",
            "last_name": "TestUser",
            "age": None
        })
        db.flush()
        db.refresh(target_item)
        target_id = target_item.id

        # Create the matching corrupted_rows entry
        corrupted_item = BaseRepository(corrupted_model).create(db, {
            "target_table": TARGET_TABLE,
            "row_id": str(target_id),
            "error_reason": "TRY_CAST failed: 'abc' is not a valid INTEGER",
            "error_column": "age"
        })
        db.commit()
        db.refresh(corrupted_item)

        yield target_id, corrupted_item.id
    finally:
        # Cleanup
        try:
            if corrupted_item:
                BaseRepository(corrupted_model).delete(db, corrupted_item.id)
            if target_item:
                BaseRepository(target_model).delete(db, target_item.id)
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"Error during teardown: {e}")
        db.close()


# ===========================================================================
# TEST GROUP 1: Basic CRUD for corrupted_rows
# ===========================================================================

class TestCorruptedRowsCRUD:
    """Tests for the basic CRUD endpoints on the corrupted_rows table."""

    def test_create_corrupted_row(self):
        """POST /api/corrupted_rows creates a new entry and returns it."""
        payload = {
            "target_table": "create_test_table",
            "row_id": "999",
            "error_reason": "Creation test message"
        }

        reflect_db()
        model_class = Base.classes.get(CORRUPTED_ROWS_TABLE)
        db = next(get_db())

        created_id = None
        try:
            r = requests.post(f"{API_URL}/api/corrupted_rows", json=payload)
            assert r.status_code == 200
            data = r.json()
            assert data["target_table"] == payload["target_table"]
            assert data["error_reason"] == payload["error_reason"]
            created_id = data["id"]
        finally:
            if created_id:
                try:
                    BaseRepository(model_class).delete(db, created_id)
                    db.commit()
                except Exception as e:
                    db.rollback()
            db.close()

    def test_get_corrupted_rows(self, setup_corrupted_row):
        """GET /api/corrupted_rows returns paginated data with the setup entry."""
        r = requests.get(f"{API_URL}/api/corrupted_rows")
        assert r.status_code == 200
        data = r.json()

        assert "data" in data
        assert "total" in data
        assert "page" in data
        assert "limit" in data
        assert isinstance(data["data"], list)
        assert data["total"] >= 1

        # Check if our setup item is in the list
        setup_id = setup_corrupted_row
        found = any(item["id"] == setup_id for item in data["data"])
        assert found

    def test_delete_corrupted_row(self):
        """DELETE /api/corrupted_rows/{id} removes the entry."""
        # Setup
        reflect_db()
        model_class = Base.classes.get(CORRUPTED_ROWS_TABLE)
        db = next(get_db())
        new_item_data = {
            "target_table": "delete_test_table",
            "row_id": "456",
            "error_reason": "Delete test message"
        }
        created_item = BaseRepository(model_class).create(db, new_item_data)
        db.commit()
        db.refresh(created_item)
        item_id = created_item.id

        # Test
        r = requests.delete(f"{API_URL}/api/corrupted_rows/{item_id}")
        assert r.status_code == 200
        assert r.json()["message"] == "Corrupted row deleted successfully"

        # Verify deleted
        r_check = requests.get(f"{API_URL}/api/corrupted_rows")
        data = r_check.json()
        found = any(item["id"] == item_id for item in data["data"])
        assert not found
        db.close()

    def test_delete_nonexistent_corrupted_row(self):
        """DELETE /api/corrupted_rows/{id} returns 404 for nonexistent ID."""
        r = requests.delete(f"{API_URL}/api/corrupted_rows/999999")
        assert r.status_code == 404

    def test_get_corrupted_rows_pagination(self):
        """GET /api/corrupted_rows respects skip and limit parameters."""
        r = requests.get(f"{API_URL}/api/corrupted_rows?skip=0&limit=1")
        assert r.status_code == 200
        data = r.json()
        assert data["limit"] == 1
        assert len(data["data"]) <= 1


# ===========================================================================
# TEST GROUP 2: Resolve (Heal) Endpoint
# ===========================================================================

class TestResolveEndpoint:
    """Tests for PATCH /api/{table_name}/{row_id}/resolve."""

    def test_resolve_corrupted_row_success(self, setup_target_row_with_corruption):
        """
        Resolving with a valid integer value should:
        1. Update the primary record's age
        2. Delete the corrupted_rows entry
        3. Return success status
        """
        target_id, corrupted_id = setup_target_row_with_corruption

        r = requests.patch(
            f"{API_URL}/api/{TARGET_TABLE}/{target_id}/resolve",
            json={"corrections": {"age": "25"}}
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "success"
        assert data["message"] == "Row healed and error log cleared."
        assert data["updated_record"]["age"] == 25

        # Verify the corrupted entry was deleted
        reflect_db()
        corrupted_model = Base.classes.get(CORRUPTED_ROWS_TABLE)
        db = next(get_db())
        try:
            remaining = db.query(corrupted_model).filter(
                corrupted_model.id == corrupted_id
            ).first()
            assert remaining is None, "Corrupted entry should be deleted after resolve"
        finally:
            db.close()

    def test_resolve_with_invalid_type_rejects(self, setup_target_row_with_corruption):
        """
        Resolving with 'abc' for an integer column should return 400
        due to type validation.
        """
        target_id, _ = setup_target_row_with_corruption

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

    def test_resolve_nonexistent_column(self, setup_target_row_with_corruption):
        """Resolving with a column that doesn't exist returns 400."""
        target_id, _ = setup_target_row_with_corruption

        r = requests.patch(
            f"{API_URL}/api/{TARGET_TABLE}/{target_id}/resolve",
            json={"corrections": {"nonexistent_column": "value"}}
        )
        assert r.status_code == 400
        assert "does not exist" in r.json()["detail"]

    def test_resolve_with_valid_integer_string(self, setup_target_row_with_corruption):
        """A string that represents a valid integer ('42') should be accepted and cast."""
        target_id, _ = setup_target_row_with_corruption

        r = requests.patch(
            f"{API_URL}/api/{TARGET_TABLE}/{target_id}/resolve",
            json={"corrections": {"age": "42"}}
        )
        assert r.status_code == 200
        assert r.json()["updated_record"]["age"] == 42


# ===========================================================================
# TEST GROUP 3: Type Validation Unit Tests (no server required)
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
# TEST GROUP 4: ETL Sidecar — All rows in clean table (Fix 1 verification)
# ===========================================================================

class TestETLSidecarBehavior:
    """
    Verify that after Fix 1, ALL rows land in the clean table
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
        After Fix 1: Every row—including corrupted ones—should exist in clean_data.
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

        # ALL 3 rows should be in clean_data (Fix 1)
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