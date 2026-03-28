"""
Unit tests for server/services/file_loaders.py.

Tests run entirely in-memory using DuckDB — no Celery, no Postgres.
Validates that each loader produces all-VARCHAR tables and that the
registry dispatches correctly.
"""

import duckdb
import os
import sys
import tempfile
import types
import pytest

current_dir = os.path.dirname(os.path.abspath(__file__))
server_dir = os.path.dirname(current_dir)
sys.path.insert(0, server_dir)

# Stub out dlt_pipeline (same pattern as test_duckdb_validation.py)
CORRUPTED_ROWS_NAME = "corrupted_rows"
RAW_DATA_NAME = "raw_staging"
CLEAN_DATA_NAME = "clean_data"

_fake_dlt_pipeline = types.ModuleType("services.dlt_pipeline")
_fake_dlt_pipeline.CORRUPTED_ROWS_NAME = CORRUPTED_ROWS_NAME
_fake_dlt_pipeline.RAW_DATA_NAME = RAW_DATA_NAME
_fake_dlt_pipeline.CLEAN_DATA_NAME = CLEAN_DATA_NAME
class MockDLTPipeline:
    def load_to_postgres(self, con, **kwargs): pass
_fake_dlt_pipeline.DLTPipeline = MockDLTPipeline
sys.modules["services.dlt_pipeline"] = _fake_dlt_pipeline

from services.file_loaders import create_raw_table, _load_csv, _load_xlsx
from services.etl_processor import _validate_and_split_data


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def duckdb_con():
    con = duckdb.connect(database=":memory:")
    yield con
    con.close()


@pytest.fixture
def test_csv_path():
    path = os.path.join(current_dir, "test_data_corrupted.csv")
    if not os.path.exists(path):
        pytest.skip("test_data_corrupted.csv not found")
    return path


@pytest.fixture
def test_xlsx_path():
    path = os.path.join(current_dir, "test_data_corrupted.xlsx")
    if not os.path.exists(path):
        pytest.skip("test_data_corrupted.xlsx not found")
    return path


# ===========================================================================
# CSV Loader
# ===========================================================================

class TestCSVLoader:

    def test_creates_table_with_correct_row_count(self, duckdb_con, test_csv_path):
        _load_csv(duckdb_con, test_csv_path, "raw_staging")
        count = duckdb_con.execute("SELECT COUNT(*) FROM raw_staging").fetchone()[0]
        assert count == 5

    def test_all_columns_are_varchar(self, duckdb_con, test_csv_path):
        _load_csv(duckdb_con, test_csv_path, "raw_staging")
        col_types = duckdb_con.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name = 'raw_staging'"
        ).fetchall()
        for col_name, data_type in col_types:
            assert data_type == "VARCHAR", f"Column '{col_name}' is {data_type}"


# ===========================================================================
# XLSX Loader
# ===========================================================================

class TestXLSXLoader:

    def test_creates_table_with_correct_row_count(self, duckdb_con, test_xlsx_path):
        _load_xlsx(duckdb_con, test_xlsx_path, "raw_staging")
        count = duckdb_con.execute("SELECT COUNT(*) FROM raw_staging").fetchone()[0]
        assert count == 5

    def test_all_columns_are_varchar(self, duckdb_con, test_xlsx_path):
        _load_xlsx(duckdb_con, test_xlsx_path, "raw_staging")
        col_types = duckdb_con.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name = 'raw_staging'"
        ).fetchall()
        for col_name, data_type in col_types:
            assert data_type == "VARCHAR", f"Column '{col_name}' is {data_type}"

    def test_numeric_cells_become_strings(self, duckdb_con, test_xlsx_path):
        _load_xlsx(duckdb_con, test_xlsx_path, "raw_staging")
        row = duckdb_con.execute(
            "SELECT age, blood_pressure FROM raw_staging WHERE patient_id = 'P001'"
        ).fetchone()
        assert row[0] == "30"
        assert row[1] == "120"

    def test_preserves_corrupted_values(self, duckdb_con, test_xlsx_path):
        _load_xlsx(duckdb_con, test_xlsx_path, "raw_staging")
        bob_age = duckdb_con.execute(
            "SELECT age FROM raw_staging WHERE patient_id = 'P002'"
        ).fetchone()[0]
        assert bob_age == "abc"

        carol_bp = duckdb_con.execute(
            "SELECT blood_pressure FROM raw_staging WHERE patient_id = 'P003'"
        ).fetchone()[0]
        assert carol_bp == "HIGH"

    def test_empty_file_raises(self, duckdb_con):
        from openpyxl import Workbook
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            wb = Workbook()
            ws = wb.active
            # Remove the default empty row — leave sheet truly empty
            wb.save(f.name)
            wb.close()
            tmp_path = f.name
        try:
            with pytest.raises(ValueError, match="empty|no header"):
                _load_xlsx(duckdb_con, tmp_path, "raw_staging")
        finally:
            os.unlink(tmp_path)


# ===========================================================================
# CSV vs XLSX Equivalence
# ===========================================================================

class TestCSVXLSXEquivalence:

    def test_same_columns(self, test_csv_path, test_xlsx_path):
        con_csv = duckdb.connect(database=":memory:")
        con_xlsx = duckdb.connect(database=":memory:")
        try:
            _load_csv(con_csv, test_csv_path, "raw_staging")
            _load_xlsx(con_xlsx, test_xlsx_path, "raw_staging")

            csv_cols = con_csv.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'raw_staging' ORDER BY ordinal_position"
            ).fetchall()
            xlsx_cols = con_xlsx.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'raw_staging' ORDER BY ordinal_position"
            ).fetchall()
            assert csv_cols == xlsx_cols
        finally:
            con_csv.close()
            con_xlsx.close()

    def test_same_data(self, test_csv_path, test_xlsx_path):
        con_csv = duckdb.connect(database=":memory:")
        con_xlsx = duckdb.connect(database=":memory:")
        try:
            _load_csv(con_csv, test_csv_path, "raw_staging")
            _load_xlsx(con_xlsx, test_xlsx_path, "raw_staging")

            csv_data = con_csv.execute(
                "SELECT * FROM raw_staging ORDER BY patient_id"
            ).fetchall()
            xlsx_data = con_xlsx.execute(
                "SELECT * FROM raw_staging ORDER BY patient_id"
            ).fetchall()
            assert csv_data == xlsx_data
        finally:
            con_csv.close()
            con_xlsx.close()

    def test_same_validation_results(self, test_csv_path, test_xlsx_path):
        schema_map = {
            "age": "INTEGER",
            "blood_pressure": "INTEGER",
            "admission_date": "DATE",
        }
        con_csv = duckdb.connect(database=":memory:")
        con_xlsx = duckdb.connect(database=":memory:")
        try:
            _load_csv(con_csv, test_csv_path, "raw_staging")
            _load_xlsx(con_xlsx, test_xlsx_path, "raw_staging")

            csv_errors = _validate_and_split_data(con_csv, schema_map)
            xlsx_errors = _validate_and_split_data(con_xlsx, schema_map)
            assert csv_errors == xlsx_errors
        finally:
            con_csv.close()
            con_xlsx.close()


# ===========================================================================
# Registry / Dispatch
# ===========================================================================

class TestRegistry:

    def test_csv_dispatch(self, duckdb_con, test_csv_path):
        create_raw_table(duckdb_con, test_csv_path, "raw_staging")
        count = duckdb_con.execute("SELECT COUNT(*) FROM raw_staging").fetchone()[0]
        assert count == 5

    def test_xlsx_dispatch(self, duckdb_con, test_xlsx_path):
        create_raw_table(duckdb_con, test_xlsx_path, "raw_staging")
        count = duckdb_con.execute("SELECT COUNT(*) FROM raw_staging").fetchone()[0]
        assert count == 5

    def test_unsupported_format_raises(self, duckdb_con):
        with pytest.raises(ValueError, match="Unsupported file format"):
            create_raw_table(duckdb_con, "/tmp/data.json", "raw_staging")

    def test_error_lists_supported_formats(self, duckdb_con):
        with pytest.raises(ValueError, match=r"\.csv"):
            create_raw_table(duckdb_con, "/tmp/data.parquet", "raw_staging")
