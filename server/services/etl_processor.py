import duckdb
import os
from dlt.pipeline.exceptions import PipelineStepFailed
from services.column_typing import normalize_duckdb_type, quote_column_id
from services.dlt_pipeline import DLTPipeline
from services.dlt_pipeline import CORRUPTED_ROWS_NAME, RAW_DATA_NAME, CLEAN_DATA_NAME
from services.file_loaders import create_raw_table
from core.config import settings
import logging

logger = logging.getLogger(__name__)


class ETLError(Exception):
    """Non-retryable ETL error with a user-friendly message."""
    pass


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

    if not proposed_schema:
        raise ETLError("No columns were provided in the schema. Please define at least one column.")

    con = duckdb.connect(database=':memory:')

    # Set temp directory for overflow
    os.makedirs(settings.DUCKDB_TEMP_DIR, exist_ok=True)
    con.execute(f"SET temp_directory='{settings.DUCKDB_TEMP_DIR}'")
    logger.debug(f"DuckDB temp directory set to: {settings.DUCKDB_TEMP_DIR}")

    try:
        logger.info(f"Creating raw staging table from file: {file_path}")
        try:
            create_raw_table(con, file_path, RAW_DATA_NAME)
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}", exc_info=True)
            raise ETLError(
                f"Could not read the uploaded file: {e}"
            ) from e
        _normalize_column_names(con, RAW_DATA_NAME)
        logger.info("Raw staging table created successfully")
        _check_columns_exist(con, RAW_DATA_NAME, proposed_schema)
        error_count = _validate_and_split_data(con, proposed_schema)
        dlt_pipeline = DLTPipeline()
        dlt_pipeline.load_to_postgres(con, target_table_name=target_table_name)
        logger.info("File processing task completed successfully")
        return error_count
    except ETLError:
        raise
    except PipelineStepFailed as e:
        logger.error("DLT load failed: %s", e, exc_info=True)
        raise ETLError(
            "Could not load data into the warehouse. If this persists, check column types "
            "and file contents, or contact support."
        ) from e
    except duckdb.Error as e:
        logger.error(f"DuckDB error during processing: {e}", exc_info=True)
        raise ETLError(
            f"Data processing failed due to a database error. Please check your file and schema."
        ) from e
    finally:
        con.close()
        logger.debug("DuckDB connection closed")


def _normalize_column_names(con, table_name):
    """Strip BOM, whitespace, and other invisible characters from column names."""
    cols = [row[0] for row in con.execute(f"DESCRIBE {table_name}").fetchall()]
    renames = []
    for col in cols:
        cleaned = col.strip().lstrip("\ufeff").strip()
        if cleaned != col:
            renames.append((col, cleaned))
    for old, new in renames:
        logger.info(f"Normalizing column name: {repr(old)} -> {repr(new)}")
        con.execute(f'ALTER TABLE {table_name} RENAME COLUMN "{old}" TO "{new}"')


def _check_columns_exist(con, table_name, schema_map):
    """Validate that all proposed schema columns exist in the raw table."""
    actual_cols = {row[0] for row in con.execute(f"DESCRIBE {table_name}").fetchall()}
    missing = [col for col in schema_map if col not in actual_cols]
    if missing:
        raise ETLError(
            f"Column mismatch: schema references {missing} "
            f"but the file only has columns {sorted(actual_cols)}. "
            f"This usually means the file headers don't match the confirmed schema."
        )


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
    col_defs = ["original_csv_row_id BIGINT"]
    for col_name, user_type in schema_map.items():
        q = quote_column_id(col_name)
        dt = normalize_duckdb_type(user_type)
        columns_sql.append(f"TRY_CAST({q} AS {dt}) AS {q}")
        error_conditions.append(f"({q} IS NOT NULL AND TRY_CAST({q} AS {dt}) IS NULL)")
        col_defs.append(f"{q} {dt}")
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
    col_def_clause = ",\n            ".join(col_defs)

    all_blank_parts = [f'("{col}" IS NULL OR TRIM("{col}") = \'\')' for col in schema_map]
    all_blank_condition = " AND ".join(all_blank_parts)

    logger.info("Creating clean data table")
    con.execute(f"""
        CREATE TABLE {CLEAN_DATA_NAME} (
            {col_def_clause}
        )
    """)
    con.execute(f"""
        INSERT INTO {CLEAN_DATA_NAME}
        SELECT rowid AS original_csv_row_id, {select_clause}
        FROM {RAW_DATA_NAME}
        WHERE NOT ({all_blank_condition})
    """)
    error_count = con.execute(f"SELECT COUNT(*) FROM {CORRUPTED_ROWS_NAME}").fetchone()[0]
    logger.info(f"Data validation completed - found {error_count} corrupted rows")
    return error_count
