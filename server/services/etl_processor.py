import duckdb
import os
from services.dlt_pipeline import load_to_postgres
from services.dlt_pipeline import CORRUPTED_ROWS_NAME, RAW_DATA_NAME, CLEAN_DATA_NAME
from core.config import settings
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(module)s:%(lineno)d -%(levelname)s - %(message)s"
)

def process_file_task(file_path: str, proposed_schema: dict):
    """
    Core ETL function: read CSV → validate with DuckDB TRY_CAST → split clean/corrupted → load to Postgres.
    
    Args:
        file_path: Absolute path to the CSV file on disk.
        proposed_schema: Dict mapping column names to DuckDB types, e.g. {"age": "INTEGER"}.
    """
    logging.info(f"Starting file processing task for: {file_path}")
    logging.debug(f"Proposed schema: {proposed_schema}")
    con = duckdb.connect(database=':memory:')

    # Set temp directory for overflow
    os.makedirs(settings.DUCKDB_TEMP_DIR, exist_ok=True)
    con.execute(f"SET temp_directory='{settings.DUCKDB_TEMP_DIR}'")
    logging.debug(f"DuckDB temp directory set to: {settings.DUCKDB_TEMP_DIR}")
    
    try:
        logging.info(f"Creating raw staging table from CSV: {file_path}")
        con.execute(f"""
            CREATE TABLE {RAW_DATA_NAME} AS 
            SELECT * FROM read_csv('{file_path}', all_varchar=True, auto_detect=True)
        """)
        logging.info("Raw staging table created successfully")
        validate_and_split_data(con, proposed_schema)
        load_to_postgres(con)
        logging.info("File processing task completed successfully")
    finally:
        con.close()
        logging.debug("DuckDB connection closed")

def validate_and_split_data(con, schema_map):
    """
    Split raw data into clean_data (TRY_CAST applied) and corrupted_rows (failed casts).
    
    Clean_data includes ALL rows — invalid values become NULL via TRY_CAST (validate-and-repair).
    Corrupted_rows captures rows where at least one cast failed, preserving original values.
    """
    logging.info("Starting data validation and split process")
    logging.debug(f"Schema map: {schema_map}")
    columns_sql = []
    error_conditions = []
    for col_name, target_type in schema_map.items():
        q = f'"{col_name}"'
        columns_sql.append(f"TRY_CAST({q} AS {target_type}) AS {q}")
        error_conditions.append(f"({q} IS NOT NULL AND TRY_CAST({q} AS {target_type}) IS NULL)")
    where_clause = " OR ".join(error_conditions)
    logging.debug(f"Generated {len(columns_sql)} column casts and {len(error_conditions)} error conditions")
    
    logging.info("Creating corrupted rows table")
    con.execute(f"""
        CREATE TABLE {CORRUPTED_ROWS_NAME} AS 
        SELECT rowid AS original_csv_row_id, *, 'Validation Failed' as error_reason
        FROM {RAW_DATA_NAME}
        WHERE {where_clause}
    """)
    select_clause = ", ".join(columns_sql)
    logging.info("Creating clean data table")
    con.execute(f"""
        CREATE TABLE {CLEAN_DATA_NAME} AS
        SELECT rowid AS original_csv_row_id, {select_clause}
        FROM {RAW_DATA_NAME}
    """)
    error_count = con.execute(f"SELECT COUNT(*) FROM {CORRUPTED_ROWS_NAME}").fetchone()[0]
    logging.info(f"Data validation completed - found {error_count} corrupted rows")
    return error_count

def run_pipeline_with_schema(file_id: str, schema_map: dict, db, storage):
    """
    ETL using the schema confirmed by the user via /api/schema endpoint.
    
    Downloads the file from storage, validates with DuckDB TRY_CAST using 
    the user's confirmed schema, splits clean/corrupted, loads to Postgres.
    
    Args:
        file_id: UUID of the file in the registry.
        schema_map: Dict mapping column names to DuckDB types.
        db: SQLAlchemy Session (injected).
        storage: StorageProvider instance (injected).
    """
    logging.info(f"Starting pipeline with schema for file_id: {file_id}")
    logging.debug(f"Schema map: {schema_map}")

    import crud
    from core.database import Base

    file_records = crud.get_items_by_field(
        db=db,
        model_class=Base.classes.get("file_registry"),
        field_name="file_id",
        value=file_id
    )
    if not file_records:
        logging.error(f"File not found in registry: {file_id}")
        raise Exception("File not found in registry")

    object_key = file_records[0].object_key
    logging.info(f"File record found with object_key: {object_key}")

    # Download the file from storage to a local temp path
    file_path = storage.get_file_path(object_key)
    if not file_path:
        logging.error(f"Could not download file from storage: {object_key}")
        raise Exception(f"Could not download file from storage: {object_key}")

    logging.info(f"File downloaded successfully: {file_path}")
    process_file_task(str(file_path), schema_map)
    logging.info(f"Pipeline with schema completed successfully for file_id: {file_id}")