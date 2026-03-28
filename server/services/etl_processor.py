import duckdb
import os
from services.dlt_pipeline import DLTPipeline
from services.dlt_pipeline import CORRUPTED_ROWS_NAME, RAW_DATA_NAME, CLEAN_DATA_NAME
from services.file_loaders import create_raw_table
from core.config import settings
import logging

logger = logging.getLogger(__name__)


def process_file(file_path: str, proposed_schema: dict, target_table_name: str = None):
    """
    Core ETL function: read file → validate with DuckDB TRY_CAST → split clean/corrupted → load to Postgres.

    Args:
        file_path: Absolute path to the data file on disk (.csv, .xlsx, etc.).
        proposed_schema: Dict mapping column names to DuckDB types, e.g. {"age": "INTEGER"}.
        target_table_name: Name of the Postgres table to create (derived from filename).
    """
    logger.info(f"Starting file processing task for: {file_path}")
    logger.debug(f"Proposed schema: {proposed_schema}")
    con = duckdb.connect(database=':memory:')

    # Set temp directory for overflow
    os.makedirs(settings.DUCKDB_TEMP_DIR, exist_ok=True)
    con.execute(f"SET temp_directory='{settings.DUCKDB_TEMP_DIR}'")
    logger.debug(f"DuckDB temp directory set to: {settings.DUCKDB_TEMP_DIR}")

    try:
        logger.info(f"Creating raw staging table from file: {file_path}")
        create_raw_table(con, file_path, RAW_DATA_NAME)
        logger.info("Raw staging table created successfully")
        error_count = _validate_and_split_data(con, proposed_schema)
        dlt_pipeline = DLTPipeline()
        dlt_pipeline.load_to_postgres(con, target_table_name=target_table_name)
        logger.info("File processing task completed successfully")
        return error_count
    finally:
        con.close()
        logger.debug("DuckDB connection closed")


def _validate_and_split_data(con, schema_map):
    """
    Split raw data into clean_data (TRY_CAST applied) and corrupted_rows (failed casts).

    Clean_data includes ALL rows — invalid values become NULL via TRY_CAST (validate-and-repair).
    Corrupted_rows captures rows where at least one cast failed, preserving original values.
    """
    logger.info("Starting data validation and split process")
    logger.debug(f"Schema map: {schema_map}")
    columns_sql = []
    error_conditions = []
    for col_name, target_type in schema_map.items():
        q = f'"{col_name}"'
        columns_sql.append(f"TRY_CAST({q} AS {target_type}) AS {q}")
        error_conditions.append(f"({q} IS NOT NULL AND TRY_CAST({q} AS {target_type}) IS NULL)")
    where_clause = " OR ".join(error_conditions)
    logger.debug(f"Generated {len(columns_sql)} column casts and {len(error_conditions)} error conditions")

    logger.info("Creating corrupted rows table")
    con.execute(f"""
        CREATE TABLE {CORRUPTED_ROWS_NAME} AS
        SELECT rowid AS original_csv_row_id, *, 'Validation Failed' as error_reason
        FROM {RAW_DATA_NAME}
        WHERE {where_clause}
    """)
    select_clause = ", ".join(columns_sql)
    logger.info("Creating clean data table")
    con.execute(f"""
        CREATE TABLE {CLEAN_DATA_NAME} AS
        SELECT rowid AS original_csv_row_id, {select_clause}
        FROM {RAW_DATA_NAME}
    """)
    error_count = con.execute(f"SELECT COUNT(*) FROM {CORRUPTED_ROWS_NAME}").fetchone()[0]
    logger.info(f"Data validation completed - found {error_count} corrupted rows")
    return error_count
