from __future__ import annotations

import logging
from uuid import uuid4

import dlt
from dlt.destinations import postgres
from sqlalchemy import text

from core.config import settings
from core.database import engine

logger = logging.getLogger(__name__)

CORRUPTED_ROWS_NAME = "corrupted_rows"
RAW_DATA_NAME = "raw_staging"
CLEAN_DATA_NAME = "clean_data"


def _quote_pg_ident(ident: str) -> str:
    return '"' + ident.replace('"', '""') + '"'


class DLTPipeline:
    def __init__(self, dataset_name: str = settings.DLT_DATASET, destination=None):
        self.dataset_name = dataset_name
        self.destination = destination or postgres(credentials=settings.DLT_CREDENTIALS)

    def load_to_postgres(
        self,
        con,
        target_table_name: str = None,
    ):
        table_name = target_table_name or "final_patient_records"
        corrupted_table_name = f"{table_name}__corrupted"

        logger.info("Starting DLT pipeline to load data to Postgres")

        qschema = _quote_pg_ident(self.dataset_name)
        qtable = _quote_pg_ident(table_name)
        qcorrupt = _quote_pg_ident(corrupted_table_name)

        with engine.begin() as conn:
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {qschema}"))
            conn.execute(text(f"DROP TABLE IF EXISTS {qschema}.{qtable} CASCADE"))
            conn.execute(text(f"DROP TABLE IF EXISTS {qschema}.{qcorrupt} CASCADE"))

        pipeline_name = f"duckdb_to_postgres_{uuid4().hex[:12]}"
        pipeline = dlt.pipeline(
            pipeline_name=pipeline_name,
            destination=self.destination,
            dataset_name=self.dataset_name,
        )

        logger.info(f"DLT pipeline created: destination={self.destination}, dataset={self.dataset_name}")

        logger.info(f"Loading clean data from table: {CLEAN_DATA_NAME}")
        arrow_table = con.table(f"{CLEAN_DATA_NAME}").arrow().read_all()
        corrupted_table = con.table(f"{CORRUPTED_ROWS_NAME}").arrow().read_all()
        logger.debug(f"Arrow tables loaded - clean data rows: {len(arrow_table)}, corrupted rows: {len(corrupted_table)}")

        logger.info(f"Running pipeline for {table_name} table")
        info = pipeline.run(
            arrow_table,
            table_name=table_name,
            write_disposition="replace",
            primary_key="original_csv_row_id"
        )
        logger.info(f"Pipeline run completed for {table_name}: {info}")

        logger.info(f"Running pipeline for {corrupted_table_name} table")
        corrupted = pipeline.run(
            corrupted_table,
            table_name=corrupted_table_name,
            write_disposition="replace",
            primary_key="original_csv_row_id"
        )
        logger.info(f"Pipeline run completed for {corrupted_table_name}: {corrupted}")

        logger.info("DLT pipeline execution completed successfully")
        return info, corrupted
