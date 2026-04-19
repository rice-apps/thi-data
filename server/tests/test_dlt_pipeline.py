"""
Unit tests for server/services/dlt_pipeline.py — schema creation and pipeline naming.

All tests use mocked dependencies (no live DLT/Postgres).
"""

from unittest.mock import patch, MagicMock

import sys
import pytest
from services.column_typing import normalize_duckdb_type

@pytest.fixture(autouse=True)
def restore_dlt_module():
    if "services.dlt_pipeline" in sys.modules and not hasattr(sys.modules["services.dlt_pipeline"], "engine"):
        del sys.modules["services.dlt_pipeline"]
class TestDLTPipelineSchemaCreation:

    @patch("services.dlt_pipeline.dlt")
    @patch("services.dlt_pipeline.engine")
    def test_schema_created_before_pipeline_run(self, mock_engine, mock_dlt):
        """Schema is ensured and prior destination tables dropped before DLT runs."""
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

        sqls = [str(c[0][0].text) for c in mock_conn.execute.call_args_list]
        assert any("CREATE SCHEMA IF NOT EXISTS \"test_schema\"" in s for s in sqls)
        assert any(
            "DROP TABLE IF EXISTS \"test_schema\".\"test_table\" CASCADE" in s for s in sqls
        )
        assert any(
            "DROP TABLE IF EXISTS \"test_schema\".\"test_table__corrupted\" CASCADE" in s
            for s in sqls
        )

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


class TestNormalizeDuckdbType:
    def test_aliases_map_to_primitives(self):
        assert normalize_duckdb_type("FLOAT") == "DOUBLE"
        assert normalize_duckdb_type("INT") == "INTEGER"
        assert normalize_duckdb_type("STRING") == "VARCHAR"

    def test_unknown_falls_back_to_varchar(self):
        assert normalize_duckdb_type("DECIMAL(10,2)") == "VARCHAR"
        assert normalize_duckdb_type("") == "VARCHAR"
