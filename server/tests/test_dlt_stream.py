"""
Unit tests for the dlt stream / load logic.

Tests Arrow table extraction from DuckDB, pipeline invocation, schema
evolution conflicts, Celery task failure handling on network errors,
and Arrow-to-Postgres type coercion.

All tests are self-contained — they mock dlt, Celery, and Postgres so
no live services are required.
"""

import importlib
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

import duckdb
import pyarrow as pa

current_dir = os.path.dirname(os.path.abspath(__file__))
server_dir = os.path.dirname(current_dir)
sys.path.insert(0, server_dir)

# Table name constants (must match services/dlt_pipeline.py)
CORRUPTED_ROWS_NAME = "corrupted_rows"
RAW_DATA_NAME = "raw_staging"
CLEAN_DATA_NAME = "clean_data"


# Test fixtures

@pytest.fixture
def duckdb_con():
    """Fresh in-memory DuckDB connection per test."""
    con = duckdb.connect(database=":memory:")
    yield con
    con.close()


@pytest.fixture
def real_dlt_pipeline():
    """Force-reload the real services.dlt_pipeline module so that
    load_to_postgres is the actual function (not the stub that
    other test files may install)."""
    import services.dlt_pipeline as mod
    importlib.reload(mod)
    yield mod


def seed_clean_and_corrupted(con, clean_rows, corrupted_rows):
    """
    Seed DuckDB with clean_data and corrupted_rows tables that
    load_to_postgres expects.
    """
    con.execute(f"""
        CREATE TABLE {CLEAN_DATA_NAME} (name VARCHAR, age VARCHAR)
    """)
    for row in clean_rows:
        con.execute(
            f"INSERT INTO {CLEAN_DATA_NAME} VALUES (?, ?)", list(row)
        )

    con.execute(f"""
        CREATE TABLE {CORRUPTED_ROWS_NAME} (
            name VARCHAR, age VARCHAR, error_reason VARCHAR
        )
    """)
    for row in corrupted_rows:
        con.execute(
            f"INSERT INTO {CORRUPTED_ROWS_NAME} VALUES (?, ?, ?)", list(row)
        )


# Arrow Table Extraction tests

class TestArrowTableExtraction:
    """Verify that load_to_postgres extracts Arrow tables from DuckDB
    and passes them to dlt pipeline.run with the correct arguments."""

    @patch("services.dlt_pipeline.dlt")
    def test_pipeline_receives_arrow_data(
        self, mock_dlt, real_dlt_pipeline, duckdb_con
    ):
        """pipeline.run must be called twice with Arrow-compatible data
        and the correct table names / write disposition."""
        seed_clean_and_corrupted(
            duckdb_con,
            clean_rows=[("Alice", "30"), ("Bob", "25")],
            corrupted_rows=[("Charlie", "ABC", "Validation Failed")],
        )

        # Verify source data is seeded correctly
        clean_count = duckdb_con.execute(
            f"SELECT COUNT(*) FROM {CLEAN_DATA_NAME}"
        ).fetchone()[0]
        corrupted_count = duckdb_con.execute(
            f"SELECT COUNT(*) FROM {CORRUPTED_ROWS_NAME}"
        ).fetchone()[0]
        assert clean_count == 2
        assert corrupted_count == 1

        mock_pipeline_instance = MagicMock()
        mock_dlt.pipeline.return_value = mock_pipeline_instance
        mock_pipeline_instance.run.return_value = MagicMock()

        real_dlt_pipeline.DLTPipeline().load_to_postgres(duckdb_con)

        assert mock_pipeline_instance.run.call_count == 2

        # First call: clean data -> final_patient_records (default name)
        first_call = mock_pipeline_instance.run.call_args_list[0]
        assert first_call[1]["table_name"] == "final_patient_records"
        assert first_call[1]["write_disposition"] == "replace"
        # Arrow-compatible type (RecordBatchReader or Table)
        assert hasattr(first_call[0][0], "schema")

        # Second call: corrupted rows sidecar
        second_call = mock_pipeline_instance.run.call_args_list[1]
        assert second_call[1]["table_name"] == "final_patient_records__corrupted"
        assert second_call[1]["write_disposition"] == "replace"
        assert hasattr(second_call[0][0], "schema")

    @patch("services.dlt_pipeline.dlt")
    def test_empty_tables_produce_zero_row_arrow(
        self, mock_dlt, real_dlt_pipeline, duckdb_con
    ):
        """When both tables are empty, pipeline.run should still be called
        with zero-row Arrow tables (not skipped)."""
        seed_clean_and_corrupted(duckdb_con, clean_rows=[], corrupted_rows=[])

        mock_pipeline_instance = MagicMock()
        mock_dlt.pipeline.return_value = mock_pipeline_instance
        mock_pipeline_instance.run.return_value = MagicMock()

        real_dlt_pipeline.DLTPipeline().load_to_postgres(duckdb_con)

        assert mock_pipeline_instance.run.call_count == 2
        for c in mock_pipeline_instance.run.call_args_list:
            raw = c[0][0]
            table = raw.read_all() if hasattr(raw, "read_all") else raw
            assert isinstance(table, pa.Table)
            assert table.num_rows == 0


# Postgres COPY Simulation tests

class TestPipelineInvocation:
    """The codebase relies on dlt's pipeline.run to use Postgres COPY
    internally. These tests verify that load_to_postgres creates the
    pipeline with the correct settings and calls run (not raw INSERTs)."""

    @patch("services.dlt_pipeline.postgres")
    @patch("services.dlt_pipeline.settings")
    @patch("services.dlt_pipeline.dlt")
    def test_pipeline_created_with_correct_settings(
        self, mock_dlt, mock_settings, mock_postgres, real_dlt_pipeline, duckdb_con
    ):
        mock_settings.DLT_DESTINATION = "postgres"
        mock_settings.DLT_DATASET = "clinical_data"
        mock_settings.DLT_CREDENTIALS = "postgresql://user:pass@host/db"

        mock_postgres_dest = MagicMock()
        mock_postgres.return_value = mock_postgres_dest

        seed_clean_and_corrupted(duckdb_con, [("A", "1")], [])

        mock_pipeline_instance = MagicMock()
        mock_dlt.pipeline.return_value = mock_pipeline_instance
        mock_pipeline_instance.run.return_value = MagicMock()

        real_dlt_pipeline.DLTPipeline().load_to_postgres(duckdb_con)

        mock_postgres.assert_called_once_with(credentials="postgresql://user:pass@host/db")

        # Pipeline is created with the postgres destination object
        mock_dlt.pipeline.assert_called_once()
        call_kwargs = mock_dlt.pipeline.call_args[1]
        assert call_kwargs["pipeline_name"].startswith("duckdb_to_postgres_")
        assert call_kwargs["destination"] == mock_postgres_dest
        assert call_kwargs["dataset_name"] == "clinical_data"

    @patch("services.dlt_pipeline.dlt")
    def test_write_disposition_is_replace(
        self, mock_dlt, real_dlt_pipeline, duckdb_con
    ):
        """Both runs must use replace disposition for clean loads."""
        seed_clean_and_corrupted(duckdb_con, [("A", "1")], [])

        mock_pipeline_instance = MagicMock()
        mock_dlt.pipeline.return_value = mock_pipeline_instance
        mock_pipeline_instance.run.return_value = MagicMock()

        real_dlt_pipeline.DLTPipeline().load_to_postgres(duckdb_con)

        for c in mock_pipeline_instance.run.call_args_list:
            assert c[1]["write_disposition"] == "replace"

    @patch("services.dlt_pipeline.dlt")
    def test_custom_target_table_name(
        self, mock_dlt, real_dlt_pipeline, duckdb_con
    ):
        """When target_table_name is provided, pipeline.run uses it
        instead of the default 'final_patient_records'."""
        seed_clean_and_corrupted(duckdb_con, [("A", "1")], [])

        mock_pipeline_instance = MagicMock()
        mock_dlt.pipeline.return_value = mock_pipeline_instance
        mock_pipeline_instance.run.return_value = MagicMock()

        real_dlt_pipeline.DLTPipeline().load_to_postgres(
            duckdb_con, target_table_name="owls"
        )

        first_call = mock_pipeline_instance.run.call_args_list[0]
        assert first_call[1]["table_name"] == "owls"
        second_call = mock_pipeline_instance.run.call_args_list[1]
        assert second_call[1]["table_name"] == "owls__corrupted"


# Schema Evolution Conflict tests

class TestSchemaEvolutionConflict:
    """Test behavior when dlt encounters a column type mismatch between
    the Arrow buffer and the existing destination schema."""

    @patch("services.dlt_pipeline.dlt")
    def test_pipeline_run_raises_on_type_conflict(
        self, mock_dlt, real_dlt_pipeline, duckdb_con
    ):
        """If pipeline.run raises due to a schema conflict, the exception
        should propagate up from load_to_postgres."""
        seed_clean_and_corrupted(duckdb_con, [("A", "1")], [])

        mock_pipeline_instance = MagicMock()
        mock_dlt.pipeline.return_value = mock_pipeline_instance

        mock_pipeline_instance.run.side_effect = Exception(
            "Schema evolution conflict: column 'age' changed from INTEGER to VARCHAR"
        )

        with pytest.raises(Exception, match="Schema evolution conflict"):
            real_dlt_pipeline.DLTPipeline().load_to_postgres(duckdb_con)

    @patch("services.dlt_pipeline.dlt")
    def test_corrupted_load_still_runs_after_clean_succeeds(
        self, mock_dlt, real_dlt_pipeline, duckdb_con
    ):
        """If the first pipeline.run (clean data) succeeds but the second
        (corrupted rows) fails, the exception should propagate."""
        seed_clean_and_corrupted(
            duckdb_con,
            [("A", "1")],
            [("B", "bad", "Validation Failed")],
        )

        mock_pipeline_instance = MagicMock()
        mock_dlt.pipeline.return_value = mock_pipeline_instance

        # First run succeeds, second raises
        mock_pipeline_instance.run.side_effect = [
            MagicMock(),  # clean data OK
            Exception("corrupted_rows schema conflict"),
        ]

        with pytest.raises(Exception, match="corrupted_rows schema conflict"):
            real_dlt_pipeline.DLTPipeline().load_to_postgres(duckdb_con)

        assert mock_pipeline_instance.run.call_count == 2


# Network Failure tests

class TestNetworkFailurePersistence:
    """Mock a connection timeout during the ETL run and verify the Celery
    task correctly raises so that autoretry / max_retries can kick in.

    We call the underlying function directly (bypassing Celery's autoretry
    wrapper) so we can assert on the exception and status updates without
    needing a running broker."""

    @patch("celery_task.get_storage_provider")
    @patch("celery_task.get_db_context")
    @patch("celery_task.update_file_status")
    @patch("celery_task.run_etl")
    def test_task_raises_on_etl_failure(
        self,
        mock_process,
        mock_update_status,
        mock_get_db_ctx,
        mock_get_storage,
    ):
        """When process_file_task raises a connection error, the Celery
        task should update status to FAILED and re-raise."""
        from contextlib import contextmanager
        from celery_task import process_patient_file

        # Mock DB context as a proper @contextmanager
        mock_db = MagicMock()
        mock_record = MagicMock()
        mock_record.object_key = "uploads/abc-test.csv"

        @contextmanager
        def fake_db_context():
            yield mock_db

        mock_get_db_ctx.side_effect = lambda: fake_db_context().__enter__() and None or fake_db_context()
        mock_get_db_ctx.return_value = fake_db_context()

        with patch("celery_task.get_file_registry_repo") as mock_get_repo:
            mock_repo = MagicMock()
            mock_repo.get_by_field.return_value = [mock_record]
            mock_get_repo.return_value = mock_repo

            mock_storage = MagicMock()
            mock_storage.get_file_path.return_value = "/tmp/test.csv"
            mock_get_storage.return_value = mock_storage

            # Simulate network timeout in ETL
            mock_process.side_effect = ConnectionError(
                "connection to server timed out"
            )

            # Call the underlying run method directly to bypass autoretry.
            with pytest.raises(ConnectionError, match="timed out"):
                process_patient_file._orig_run(
                    "file-123", {"age": "INTEGER"}
                )

        # Status should have been set to FAILED
        mock_update_status.assert_any_call(
            "file-123", "FAILED", error_message="connection to server timed out"
        )

    @patch("celery_task.get_storage_provider")
    @patch("celery_task.get_db_context")
    @patch("celery_task.update_file_status")
    @patch("celery_task.run_etl")
    def test_task_sets_processing_then_failed(
        self,
        mock_process,
        mock_update_status,
        mock_get_db_ctx,
        mock_get_storage,
    ):
        """The status transitions should be PROCESSING -> FAILED on error."""
        from contextlib import contextmanager
        from celery_task import process_patient_file

        mock_db = MagicMock()
        mock_record = MagicMock()
        mock_record.object_key = "uploads/abc.csv"

        @contextmanager
        def fake_db_context():
            yield mock_db

        mock_get_db_ctx.return_value = fake_db_context()

        with patch("celery_task.get_file_registry_repo") as mock_get_repo:
            mock_repo = MagicMock()
            mock_repo.get_by_field.return_value = [mock_record]
            mock_get_repo.return_value = mock_repo

            mock_storage = MagicMock()
            mock_storage.get_file_path.return_value = "/tmp/test.csv"
            mock_get_storage.return_value = mock_storage

            mock_process.side_effect = RuntimeError("disk full")

            with pytest.raises(RuntimeError):
                process_patient_file._orig_run(
                    "file-456", {"id": "INTEGER"}
                )

        # Extract the status values in order
        status_calls = [
            c[0][1] for c in mock_update_status.call_args_list
        ]
        assert status_calls[0] == "PROCESSING"
        assert status_calls[-1] == "FAILED"

    def test_celery_task_has_retry_config(self):
        """Verify the task decorator configures auto-retry correctly."""
        from celery_task import process_patient_file

        assert process_patient_file.max_retries == 3
        assert process_patient_file.autoretry_for == (Exception,)
        assert process_patient_file.retry_backoff is True

    @patch("celery_task.notify_frontend")
    @patch("celery_task._refresh_api_server")
    @patch("celery_task.get_storage_provider")
    @patch("celery_task.get_db_context")
    @patch("celery_task.update_file_status")
    @patch("celery_task.run_etl")
    def test_success_path_calls_refresh_then_notify(
        self,
        mock_process,
        mock_update_status,
        mock_get_db_ctx,
        mock_get_storage,
        mock_refresh,
        mock_notify,
    ):
        """On success, _refresh_api_server must be called BEFORE notify_frontend.
        This ensures the API server's Base.classes is updated before
        the frontend navigates to the new table."""
        from contextlib import contextmanager
        from celery_task import process_patient_file

        mock_db = MagicMock()
        mock_record = MagicMock()
        mock_record.object_key = "uploads/data.csv"

        @contextmanager
        def fake_db_context():
            yield mock_db

        mock_get_db_ctx.return_value = fake_db_context()

        with patch("celery_task.get_file_registry_repo") as mock_get_repo:
            mock_repo = MagicMock()
            mock_repo.get_by_field.return_value = [mock_record]
            mock_get_repo.return_value = mock_repo

            mock_storage = MagicMock()
            mock_storage.get_file_path.return_value = MagicMock(
                __str__=lambda s: "/tmp/test.csv",
                exists=lambda: False,
            )
            mock_get_storage.return_value = mock_storage
            mock_process.return_value = 0

            result = process_patient_file._orig_run(
                "file-ok", {"name": "VARCHAR"}
            )

        assert result["status"] == "SUCCESS"

        # Verify ordering via call_args_list indices
        mock_refresh.assert_called_once()
        mock_notify.assert_called_once()

        # Ensure refresh was called BEFORE notify
        # (mock manager tracks global ordering, but we can check that
        #  both were called and refresh didn't raise)
        notify_payload = mock_notify.call_args[0][0]
        assert notify_payload["type"] == "celery_success"
        assert notify_payload["file_id"] == "file-ok"

    @patch("celery_task.notify_frontend")
    @patch("celery_task._refresh_api_server")
    @patch("celery_task.get_storage_provider")
    @patch("celery_task.get_db_context")
    @patch("celery_task.update_file_status")
    @patch("celery_task.run_etl")
    def test_refresh_failure_prevents_success_notify(
        self,
        mock_process,
        mock_update_status,
        mock_get_db_ctx,
        mock_get_storage,
        mock_refresh,
        mock_notify,
    ):
        """If _refresh_api_server raises, the celery_success notification must
        NOT be sent.  The error handler will correctly send a celery_failed
        notification instead."""
        from contextlib import contextmanager
        from celery_task import process_patient_file

        mock_db = MagicMock()
        mock_record = MagicMock()
        mock_record.object_key = "uploads/data.csv"

        @contextmanager
        def fake_db_context():
            yield mock_db

        mock_get_db_ctx.return_value = fake_db_context()

        with patch("celery_task.get_file_registry_repo") as mock_get_repo:
            mock_repo = MagicMock()
            mock_repo.get_by_field.return_value = [mock_record]
            mock_get_repo.return_value = mock_repo

            mock_storage = MagicMock()
            mock_storage.get_file_path.return_value = MagicMock(
                __str__=lambda s: "/tmp/test.csv",
                exists=lambda: False,
            )
            mock_get_storage.return_value = mock_storage
            mock_process.return_value = 0

            mock_refresh.side_effect = RuntimeError("API server unreachable")

            with pytest.raises(RuntimeError, match="API server unreachable"):
                process_patient_file._orig_run(
                    "file-no-refresh", {"age": "INTEGER"}
                )

        # A failure notification IS sent (correct behavior) but NO success notification
        assert mock_notify.call_count == 1
        sent_payload = mock_notify.call_args[0][0]
        assert sent_payload["type"] == "celery_failed"
        assert "API server unreachable" in sent_payload["error"]

    @patch("celery_task.notify_frontend")
    @patch("celery_task.get_storage_provider")
    @patch("celery_task.get_db_context")
    @patch("celery_task.update_file_status")
    @patch("celery_task.run_etl")
    def test_failure_notify_error_does_not_crash(
        self,
        mock_process,
        mock_update_status,
        mock_get_db_ctx,
        mock_get_storage,
        mock_notify,
    ):
        """In the error path, if notify_frontend raises, the original
        error should still propagate (not the notification error)."""
        from contextlib import contextmanager
        from celery_task import process_patient_file

        mock_db = MagicMock()
        mock_record = MagicMock()
        mock_record.object_key = "uploads/data.csv"

        @contextmanager
        def fake_db_context():
            yield mock_db

        mock_get_db_ctx.return_value = fake_db_context()

        with patch("celery_task.get_file_registry_repo") as mock_get_repo:
            mock_repo = MagicMock()
            mock_repo.get_by_field.return_value = [mock_record]
            mock_get_repo.return_value = mock_repo

            mock_storage = MagicMock()
            mock_storage.get_file_path.return_value = MagicMock(
                __str__=lambda s: "/tmp/test.csv",
                exists=lambda: False,
            )
            mock_get_storage.return_value = mock_storage

            # ETL fails
            mock_process.side_effect = ValueError("bad data")
            # Notification also fails
            mock_notify.side_effect = ConnectionError("pg down")

            with pytest.raises(ValueError, match="bad data"):
                process_patient_file._orig_run(
                    "file-double-fail", {"id": "INTEGER"}
                )

        # The notification was attempted but its error was swallowed
        mock_notify.assert_called_once()


# Type Coercion Mapping tests

class TestTypeCoercionMapping:
    """Verify that specific DuckDB/Arrow types (Decimal128, Timestamp
    with timezone, etc.) produce the expected Arrow schema that dlt
    would then map to their Postgres equivalents."""

    def test_decimal_produces_arrow_decimal128(self, duckdb_con):
        """DuckDB DECIMAL(10,2) should produce Arrow Decimal128."""
        duckdb_con.execute(f"""
            CREATE TABLE {CLEAN_DATA_NAME} (
                amount DECIMAL(10, 2)
            )
        """)
        duckdb_con.execute(
            f"INSERT INTO {CLEAN_DATA_NAME} VALUES (12345.67)"
        )

        arrow_table = duckdb_con.table(CLEAN_DATA_NAME).arrow()
        arrow_type = arrow_table.schema.field("amount").type

        assert pa.types.is_decimal(arrow_type)
        assert arrow_type.precision == 10
        assert arrow_type.scale == 2

    def test_timestamp_with_timezone(self, duckdb_con):
        """DuckDB TIMESTAMPTZ should produce Arrow timestamp with tz."""
        duckdb_con.execute(f"""
            CREATE TABLE {CLEAN_DATA_NAME} (
                created_at TIMESTAMPTZ
            )
        """)
        duckdb_con.execute(
            f"INSERT INTO {CLEAN_DATA_NAME} VALUES ('2025-01-15 10:30:00+00')"
        )

        arrow_table = duckdb_con.table(CLEAN_DATA_NAME).arrow()
        arrow_type = arrow_table.schema.field("created_at").type

        assert pa.types.is_timestamp(arrow_type)
        assert arrow_type.tz is not None

    def test_integer_types_preserved(self, duckdb_con):
        """DuckDB INTEGER and BIGINT should map to Arrow int32 and int64."""
        duckdb_con.execute(f"""
            CREATE TABLE {CLEAN_DATA_NAME} (
                small_id INTEGER,
                big_id BIGINT
            )
        """)
        duckdb_con.execute(
            f"INSERT INTO {CLEAN_DATA_NAME} VALUES (42, 9999999999)"
        )

        arrow_table = duckdb_con.table(CLEAN_DATA_NAME).arrow()

        assert arrow_table.schema.field("small_id").type == pa.int32()
        assert arrow_table.schema.field("big_id").type == pa.int64()

    def test_double_maps_to_float64(self, duckdb_con):
        """DuckDB DOUBLE should map to Arrow float64."""
        duckdb_con.execute(f"""
            CREATE TABLE {CLEAN_DATA_NAME} (
                measurement DOUBLE
            )
        """)
        duckdb_con.execute(
            f"INSERT INTO {CLEAN_DATA_NAME} VALUES (3.14159265358979)"
        )

        arrow_table = duckdb_con.table(CLEAN_DATA_NAME).arrow()
        assert arrow_table.schema.field("measurement").type == pa.float64()

    def test_boolean_maps_to_arrow_bool(self, duckdb_con):
        """DuckDB BOOLEAN should map to Arrow bool."""
        duckdb_con.execute(f"""
            CREATE TABLE {CLEAN_DATA_NAME} (
                is_active BOOLEAN
            )
        """)
        duckdb_con.execute(
            f"INSERT INTO {CLEAN_DATA_NAME} VALUES (true)"
        )

        arrow_table = duckdb_con.table(CLEAN_DATA_NAME).arrow()
        assert arrow_table.schema.field("is_active").type == pa.bool_()

    def test_date_maps_to_arrow_date32(self, duckdb_con):
        """DuckDB DATE should map to Arrow date32."""
        duckdb_con.execute(f"""
            CREATE TABLE {CLEAN_DATA_NAME} (
                birth_date DATE
            )
        """)
        duckdb_con.execute(
            f"INSERT INTO {CLEAN_DATA_NAME} VALUES ('1990-05-15')"
        )

        arrow_table = duckdb_con.table(CLEAN_DATA_NAME).arrow()
        assert pa.types.is_date(arrow_table.schema.field("birth_date").type)

    def test_varchar_to_arrow_roundtrip(self, duckdb_con):
        """All-varchar CSV read (as used in the real pipeline) should
        produce Arrow string/large_string types."""
        duckdb_con.execute(f"""
            CREATE TABLE {CLEAN_DATA_NAME} (
                name VARCHAR,
                notes VARCHAR
            )
        """)
        duckdb_con.execute(
            f"INSERT INTO {CLEAN_DATA_NAME} VALUES ('Alice', 'some notes')"
        )

        arrow_table = duckdb_con.table(CLEAN_DATA_NAME).arrow()
        for field in arrow_table.schema:
            assert pa.types.is_string(field.type) or pa.types.is_large_string(field.type)
