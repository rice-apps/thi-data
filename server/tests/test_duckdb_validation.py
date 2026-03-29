"""
Unit tests for DuckDB vectorized validation logic.

These tests run entirely in-memory using DuckDB — no Celery, no Postgres, no file I/O.
We test the SQL TRY_CAST validation logic from etl_processor.validate_and_split_data,
ensuring that dirty data is correctly partitioned and original values are preserved.
"""

import duckdb
import os
import sys
import types
import pytest

# Add the 'server' directory to sys.path so we can import modules
current_dir = os.path.dirname(os.path.abspath(__file__))
server_dir = os.path.dirname(current_dir)
sys.path.insert(0, server_dir)

# Table name constants (must match services/dlt_pipeline.py)
CORRUPTED_ROWS_NAME = "corrupted_rows"
RAW_DATA_NAME = "raw_staging"
CLEAN_DATA_NAME = "clean_data"

# Stub out the dlt_pipeline module so importing etl_processor doesn't require `dlt`.
_fake_dlt_pipeline = types.ModuleType("services.dlt_pipeline")
_fake_dlt_pipeline.CORRUPTED_ROWS_NAME = CORRUPTED_ROWS_NAME  # type: ignore[attr-defined]
_fake_dlt_pipeline.RAW_DATA_NAME = RAW_DATA_NAME  # type: ignore[attr-defined]
_fake_dlt_pipeline.CLEAN_DATA_NAME = CLEAN_DATA_NAME  # type: ignore[attr-defined]
class MockDLTPipeline:
    def load_to_postgres(self, con, **kwargs): pass
_fake_dlt_pipeline.DLTPipeline = MockDLTPipeline
sys.modules["services.dlt_pipeline"] = _fake_dlt_pipeline

from services.etl_processor import _validate_and_split_data as validate_and_split_data


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def duckdb_con():
    """
    Provide a fresh in-memory DuckDB connection for each test.
    Automatically closes the connection after the test finishes.
    """
    con = duckdb.connect(database=":memory:")
    yield con
    con.close()


# ---------------------------------------------------------------------------
# Helper: seed a raw_staging table with test data
# ---------------------------------------------------------------------------

def seed_raw_table(con, columns: list[str], rows: list[tuple]):
    """
    Create the raw_staging table that validate_and_split_data expects.
    All columns are VARCHAR (mimicking the all_varchar=True CSV read).
    """
    col_defs = ", ".join(f"{col} VARCHAR" for col in columns)
    con.execute(f"CREATE TABLE {RAW_DATA_NAME} ({col_defs})")

    placeholders = ", ".join(["?"] * len(columns))
    for row in rows:
        con.execute(f"INSERT INTO {RAW_DATA_NAME} VALUES ({placeholders})", list(row))


# ===========================================================================
# TEST 1: TRY_CAST Buffer Test — corrupted_rows catches exactly the bad rows
# ===========================================================================

class TestTryCastValidation:
    """Test that TRY_CAST-based validation correctly partitions dirty data."""

    def test_corrupted_rows_catches_non_integer_strings(self, duckdb_con):
        """
        Given a mix of valid integers, non-numeric strings, and NULLs,
        only rows where a non-NULL value fails TRY_CAST should land in
        corrupted_rows.
        """
        columns = ["name", "age"]
        rows = [
            ("Alice", "30"),       # clean — age casts to INTEGER fine
            ("Bob", "ABC"),        # DIRTY — "ABC" can't cast to INTEGER
            ("Charlie", "NULL"),   # DIRTY — the literal string "NULL" can't cast to INTEGER
            ("Diana", None),       # clean — actual NULL is allowed (not a cast failure)
            ("Eve", "25"),         # clean
            ("Frank", "67.5"),     # clean — DuckDB TRY_CAST truncates "67.5" to 67
        ]
        seed_raw_table(duckdb_con, columns, rows)

        schema_map = {"age": "INTEGER"}

        error_count = validate_and_split_data(duckdb_con, schema_map)

        # Exactly 2 corrupted rows (Bob, Charlie)
        # NOTE: "12.5" is successfully TRY_CAST'd to INTEGER (truncated to 12) by DuckDB
        assert error_count == 2

        corrupted = duckdb_con.execute(
            f"SELECT name FROM {CORRUPTED_ROWS_NAME} ORDER BY name"
        ).fetchall()
        corrupted_names = [r[0] for r in corrupted]
        assert corrupted_names == ["Bob", "Charlie"]

    def test_clean_data_has_correct_cast_types(self, duckdb_con):
        """
        The clean_data table should contain ALL rows. Valid values are cast
        to the target types; invalid values become NULL via TRY_CAST.

        NOTE: clean_data includes ALL rows — corrupted values are NULL,
        not excluded (validate-and-repair workflow).
        """
        columns = ["name", "score"]
        rows = [
            ("Alice", "95"),
            ("Bob", "not_a_number"),
            ("Charlie", "87"),
        ]
        seed_raw_table(duckdb_con, columns, rows)

        # Include both columns in the schema so clean_data has them both
        schema_map = {"name": "VARCHAR", "score": "INTEGER"}

        validate_and_split_data(duckdb_con, schema_map)

        # Clean data should have ALL 3 rows (Bob's score is NULL via TRY_CAST)
        clean = duckdb_con.execute(
            f"SELECT name, score FROM {CLEAN_DATA_NAME} ORDER BY name"
        ).fetchall()
        
        assert len(clean) == 3, f"Expected 3 clean rows (all rows), got {len(clean)}"
        assert clean[0] == ("Alice", 95)    # name is Alice, score is now an actual int
        assert clean[1] == ("Bob", None)     # Bob's score is NULL (TRY_CAST failure)
        assert clean[2] == ("Charlie", 87)   # name is Charlie, score is 87

    def test_all_rows_clean(self, duckdb_con):
        """When every row is valid, corrupted_rows should be empty."""
        columns = ["id", "value"]
        rows = [
            ("1", "100"),
            ("2", "200"),
            ("3", "300"),
        ]
        seed_raw_table(duckdb_con, columns, rows)

        schema_map = {"id": "INTEGER", "value": "INTEGER"}

        error_count = validate_and_split_data(duckdb_con, schema_map)

        assert error_count == 0
        clean_count = duckdb_con.execute(
            f"SELECT COUNT(*) FROM {CLEAN_DATA_NAME}"
        ).fetchone()[0]
        assert clean_count == 3

    def test_all_rows_corrupted(self, duckdb_con):
        """When every row fails validation, clean_data should still have all rows
        but with NULL values (validate-and-repair workflow)."""
        columns = ["code"]
        rows = [
            ("abc",),
            ("def",),
            ("ghi",),
        ]
        seed_raw_table(duckdb_con, columns, rows)

        schema_map = {"code": "INTEGER"}

        error_count = validate_and_split_data(duckdb_con, schema_map)

        assert error_count == 3
        clean_count = duckdb_con.execute(
            f"SELECT COUNT(*) FROM {CLEAN_DATA_NAME}"
        ).fetchone()[0]
        assert clean_count == 3  # All rows present, but with NULL values

        # All values should be NULL via TRY_CAST
        null_count = duckdb_con.execute(
            f"SELECT COUNT(*) FROM {CLEAN_DATA_NAME} WHERE code IS NULL"
        ).fetchone()[0]
        assert null_count == 3

    def test_multi_column_validation(self, duckdb_con):
        """
        When the schema validates multiple columns, a row is corrupted
        if ANY column fails TRY_CAST.
        """
        columns = ["name", "age", "salary"]
        rows = [
            ("Alice", "30", "50000.00"),    # clean
            ("Bob", "ABC", "60000.00"),      # DIRTY — age fails
            ("Charlie", "40", "not_money"),  # DIRTY — salary fails
            ("Diana", "XYZ", "bad_value"),   # DIRTY — both fail
            ("Eve", "25", "70000.00"),       # clean
        ]
        seed_raw_table(duckdb_con, columns, rows)

        # Include name in schema so it appears in clean_data for assertion
        schema_map = {"name": "VARCHAR", "age": "INTEGER", "salary": "DOUBLE"}

        error_count = validate_and_split_data(duckdb_con, schema_map)

        assert error_count == 3

        # All 5 rows should be in clean_data (validate-and-repair workflow)
        clean = duckdb_con.execute(
            f"SELECT name FROM {CLEAN_DATA_NAME} ORDER BY name"
        ).fetchall()
        clean_names = [r[0] for r in clean]
        assert clean_names == ["Alice", "Bob", "Charlie", "Diana", "Eve"]

        # But only Alice and Eve should have non-NULL age AND salary
        fully_clean = duckdb_con.execute(
            f"SELECT name FROM {CLEAN_DATA_NAME} WHERE age IS NOT NULL AND salary IS NOT NULL ORDER BY name"
        ).fetchall()
        assert [r[0] for r in fully_clean] == ["Alice", "Eve"]

    def test_corrupted_rows_preserves_original_values(self, duckdb_con):
        """
        Corrupted rows should retain the original string values
        so you can inspect what went wrong.
        """
        columns = ["patient_id", "bp_reading"]
        rows = [
            ("P001", "120"),
            ("P002", "HIGH"),     # DIRTY
        ]
        seed_raw_table(duckdb_con, columns, rows)

        schema_map = {"bp_reading": "INTEGER"}

        validate_and_split_data(duckdb_con, schema_map)

        corrupted = duckdb_con.execute(
            f"SELECT patient_id, bp_reading, error_reason FROM {CORRUPTED_ROWS_NAME}"
        ).fetchall()
        
        assert len(corrupted) == 1
        # Original patient_id should be preserved
        assert corrupted[0][0] == "P002"
        # Original string 'HIGH' should be preserved for inspection
        assert corrupted[0][1] == "HIGH"
        # Standard error reason should be applied
        assert corrupted[0][2] == "Validation Failed"


# ===========================================================================
# TEST 2: Memory Resilience — DuckDB memory limit configuration
# ===========================================================================

class TestMemoryResilience:
    """Test that DuckDB memory limits can be set and are respected."""

    def test_set_memory_limit(self, duckdb_con):
        """
        Verify that SET memory_limit actually takes effect.
        DuckDB exposes this via the duckdb_settings() function.
        """
        duckdb_con.execute("SET memory_limit='1GB'")

        result = duckdb_con.execute(
            "SELECT value FROM duckdb_settings() WHERE name = 'max_memory'"
        ).fetchone()

        assert result is not None
        # DuckDB converts "1GB" (SI, 10^9 bytes) to binary units for display.
        # 1,000,000,000 bytes = 953.6 MiB. Check the value is in a reasonable range.
        value_str = result[0]
        assert "MiB" in value_str or "GiB" in value_str, f"Unexpected memory format: {value_str}"

    def test_set_temp_directory(self, duckdb_con):
        """
        Verify that SET temp_directory is accepted (used for spill-to-disk).
        """
        tmp_dir = "/tmp/test_duckdb_spill"
        duckdb_con.execute(f"SET temp_directory='{tmp_dir}'")

        result = duckdb_con.execute(
            "SELECT value FROM duckdb_settings() WHERE name = 'temp_directory'"
        ).fetchone()

        assert result is not None
        assert tmp_dir in result[0]

    def test_validation_works_under_memory_limit(self, duckdb_con):
        """
        Run validation with a restrictive memory limit and large dataset
        to confirm DuckDB correctly handles external processing (disk spilling).
        
        We generate 1,000,000 rows and set a 20MB limit.
        """
        # 1M rows of id/value (strings) + temp tables easily exceeds 50MB.
        # We set a tight 50MB limit to force disk spilling without crashing the engine.
        duckdb_con.execute("SET memory_limit='50MB'")
        # Disabling insertion order preservation helps reduce memory overhead during large sorts/splits
        duckdb_con.execute("SET preserve_insertion_order=false")
        
        # Ensure we have a temp directory for spilling
        tmp_dir = os.path.join(current_dir, ".duckdb_temp")
        os.makedirs(tmp_dir, exist_ok=True)
        duckdb_con.execute(f"SET temp_directory='{tmp_dir}'")

        # Efficiently generate 1M rows directly in DuckDB
        duckdb_con.execute(f"CREATE TABLE {RAW_DATA_NAME} AS "
                          "SELECT range::VARCHAR as id, (range * 10)::VARCHAR as value "
                          "FROM range(1000000)")

        schema_map = {"id": "INTEGER", "value": "INTEGER"}

        # This will process 1M rows under 50MB RAM
        error_count = validate_and_split_data(duckdb_con, schema_map)

        assert error_count == 0
        clean_count = duckdb_con.execute(
            f"SELECT COUNT(*) FROM {CLEAN_DATA_NAME}"
        ).fetchone()[0]
        assert clean_count == 1000000
        
        # Cleanup temp directory
        try:
            import shutil
            shutil.rmtree(tmp_dir)
        except Exception:
            pass


# ===========================================================================
# TEST 3: All-Blank Row Filtering
# ===========================================================================

class TestBlankRowFiltering:
    """Rows where every raw value is NULL or empty are excluded from clean_data."""

    def test_all_null_row_excluded(self, duckdb_con):
        columns = ["name", "age"]
        rows = [
            ("Alice", "30"),
            (None, None),
            ("Charlie", "25"),
        ]
        seed_raw_table(duckdb_con, columns, rows)

        schema_map = {"name": "VARCHAR", "age": "INTEGER"}
        validate_and_split_data(duckdb_con, schema_map)

        clean_count = duckdb_con.execute(
            f"SELECT COUNT(*) FROM {CLEAN_DATA_NAME}"
        ).fetchone()[0]
        assert clean_count == 2

    def test_all_empty_string_row_excluded(self, duckdb_con):
        columns = ["name", "age"]
        rows = [
            ("Alice", "30"),
            ("", ""),
            ("  ", "  "),
            ("Charlie", "25"),
        ]
        seed_raw_table(duckdb_con, columns, rows)

        schema_map = {"name": "VARCHAR", "age": "INTEGER"}
        validate_and_split_data(duckdb_con, schema_map)

        clean_count = duckdb_con.execute(
            f"SELECT COUNT(*) FROM {CLEAN_DATA_NAME}"
        ).fetchone()[0]
        assert clean_count == 2

    def test_partial_null_row_kept(self, duckdb_con):
        """A row with at least one non-null value should be kept."""
        columns = ["name", "age"]
        rows = [
            ("Alice", "30"),
            ("Bob", None),
            (None, "25"),
            (None, None),
        ]
        seed_raw_table(duckdb_con, columns, rows)

        schema_map = {"name": "VARCHAR", "age": "INTEGER"}
        validate_and_split_data(duckdb_con, schema_map)

        clean_count = duckdb_con.execute(
            f"SELECT COUNT(*) FROM {CLEAN_DATA_NAME}"
        ).fetchone()[0]
        assert clean_count == 3

    def test_failed_cast_row_not_excluded(self, duckdb_con):
        """Rows with real data that fails casting should NOT be filtered out."""
        columns = ["code"]
        rows = [
            ("abc",),
            ("def",),
            (None,),
        ]
        seed_raw_table(duckdb_con, columns, rows)

        schema_map = {"code": "INTEGER"}
        validate_and_split_data(duckdb_con, schema_map)

        clean_count = duckdb_con.execute(
            f"SELECT COUNT(*) FROM {CLEAN_DATA_NAME}"
        ).fetchone()[0]
        # "abc" and "def" have non-null raw values, so they stay (cast to NULL via TRY_CAST)
        # Only the NULL row is excluded
        assert clean_count == 2
