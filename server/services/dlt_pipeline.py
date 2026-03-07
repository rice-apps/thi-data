import dlt
from dlt.destinations import postgres

from core.config import settings
from core.config import settings
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(module)s:%(lineno)d -%(levelname)s - %(message)s"
)

CORRUPTED_ROWS_NAME = "corrupted_rows"
RAW_DATA_NAME = "raw_staging"
CLEAN_DATA_NAME = "clean_data"

def load_to_postgres(con):
    credentials = (
        f"postgresql://{settings.USER}:{settings.PASSWORD}"
        f"@{settings.HOST}:{settings.PORT}/{settings.DBNAME}?sslmode=require"
    )
    logging.info("Starting DLT pipeline to load data to Postgres")
    # Setup dlt pipeline using settings
    pipeline = dlt.pipeline(
        pipeline_name='duckdb_to_postgres',
        destination=settings.DLT_DESTINATION,
        dataset_name=settings.DLT_DATASET,
        credentials=settings.DLT_CREDENTIALS
    )
    logging.info(f"DLT pipeline created: destination={settings.DLT_DESTINATION}, dataset={settings.DLT_DATASET}")
    
    # Stream clean data to data warehouse
    logging.info(f"Loading clean data from table: {CLEAN_DATA_NAME}")
    arrow_table = con.table(f"{CLEAN_DATA_NAME}").arrow()
    corrupted_table = con.table(f"{CORRUPTED_ROWS_NAME}").arrow()
    logging.debug(f"Arrow tables loaded - clean data rows: {len(arrow_table)}, corrupted rows: {len(corrupted_table)}")

    logging.info("Running pipeline for final_patient_records table")
    info = pipeline.run(
        arrow_table, 
        table_name="final_patient_records",
        write_disposition="merge", 
        primary_key="original_csv_row_id"
    )
    logging.info(f"Pipeline run completed for final_patient_records: {info}")

    logging.info("Running pipeline for corrupted_rows table")
    corrupted = pipeline.run(
        corrupted_table,
        table_name="corrupted_rows",
        write_disposition="merge", 
        primary_key="original_csv_row_id"
    )
    logging.info(f"Pipeline run completed for corrupted_rows: {corrupted}")

    logging.info("DLT pipeline execution completed successfully")
    return info, corrupted