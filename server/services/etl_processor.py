import duckdb
import os
from services.dlt_pipeline import load_to_postgres3
from services.dlt_pipeline import CORRUPTED_ROWS_NAME, RAW_DATA_NAME, CLEAN_DATA_NAME
from core.config import settings

def process_file_task(file_path: str, proposed_schema: dict):
    # Initialize DuckDB instance
    con = duckdb.connect(database=':memory:conn')

    # Set temp directory for overflow
    os.makedirs(settings.DUCKDB_TEMP_DIR, exist_ok=True)
    con.execute(f"SET temp_directory='{settings.DUCKDB_TEMP_DIR}'")
    
    try:
        # Load raw data as Strings to prevent crashes
        con.execute(f"""
            CREATE TABLE {RAW_DATA_NAME} AS 
            SELECT * FROM read_csv('{file_path}', all_varchar=True, auto_detect=True)
        """)
        
        validate_and_split_data(con, proposed_schema)
        load_to_postgres(con)

    finally:
        con.close()

def validate_and_split_data(con, schema_map):
    columns_sql = []
    error_conditions = []
    
    for col_name, target_type in schema_map.items():
        columns_sql.append(f"TRY_CAST({col_name} AS {target_type}) AS {col_name}")
        error_conditions.append(f"({col_name} IS NOT NULL AND TRY_CAST({col_name} AS {target_type}) IS NULL)")

    where_clause = " OR ".join(error_conditions)
    
    con.execute(f"""
        CREATE TABLE {CORRUPTED_ROWS_NAME} AS 
        SELECT rowid AS original_csv_row_id, *, 'Validation Failed' as error_reason
        FROM {RAW_DATA_NAME}
        WHERE {where_clause}
    """)
    
    select_clause = ", ".join(columns_sql)
    
    con.execute(f"""
        CREATE TABLE {CLEAN_DATA_NAME} AS
        SELECT rowid AS original_csv_row_id, {select_clause}
        FROM {RAW_DATA_NAME}
    """)
    
    error_count = con.execute(f"SELECT COUNT(*) FROM {CORRUPTED_ROWS_NAME}").fetchone()[0]
    return error_count