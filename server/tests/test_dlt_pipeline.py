"""
Unit tests for server/services/dlt_pipeline.py — schema creation and pipeline naming.

All tests use mocked dependencies (no live DLT/Postgres).
"""

from unittest.mock import patch, MagicMock, call
from sqlalchemy import text

import sys
import pytest

@pytest.fixture(autouse=True)
def restore_dlt_module():
    if "services.dlt_pipeline" in sys.modules and not hasattr(sys.modules["services.dlt_pipeline"], "engine"):
        del sys.modules["services.dlt_pipeline"]
class TestDLTPipelineSchemaCreation:

    @patch("services.dlt_pipeline.dlt")
    @patch("services.dlt_pipeline.engine")
    def test_schema_created_before_pipeline_run(self, mock_engine, mock_dlt):
        """CREATE SCHEMA IF NOT EXISTS is executed before the DLT pipeline is created."""
        from services.dlt_pipeline import DLTPipeline

        mock_conn = MagicMock()
        mock_engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.begin.return_value.__exit__ = MagicMock(return_value=False)

        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = MagicMock()
        mock_dlt.pipeline.return_value = mock_pipeline

        con = MagicMock()
        con.table.return_value.arrow.return_value.read_all.return_value = MagicMock()

        pipeline = DLTPipeline(dataset_name="test_schema")
        pipeline.load_to_postgres(con, target_table_name="test_table")

        executed_sql = str(mock_conn.execute.call_args[0][0].text)
        assert "CREATE SCHEMA IF NOT EXISTS test_schema" in executed_sql

    @patch("services.dlt_pipeline.dlt")
    @patch("services.dlt_pipeline.engine")
    def test_pipeline_uses_unique_names(self, mock_engine, mock_dlt):
        """Each pipeline run creates a pipeline with a unique name."""
        from services.dlt_pipeline import DLTPipeline

        mock_conn = MagicMock()
        mock_engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.begin.return_value.__exit__ = MagicMock(return_value=False)

        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = MagicMock()
        mock_dlt.pipeline.return_value = mock_pipeline

        con = MagicMock()
        con.table.return_value.arrow.return_value.read_all.return_value = MagicMock()

        pipeline = DLTPipeline(dataset_name="clinical_data")

        pipeline.load_to_postgres(con, target_table_name="t1")
        name1 = mock_dlt.pipeline.call_args_list[-1][1]["pipeline_name"]

        pipeline.load_to_postgres(con, target_table_name="t2")
        name2 = mock_dlt.pipeline.call_args_list[-1][1]["pipeline_name"]

        assert name1.startswith("duckdb_to_postgres_")
        assert name2.startswith("duckdb_to_postgres_")
        assert name1 != name2
