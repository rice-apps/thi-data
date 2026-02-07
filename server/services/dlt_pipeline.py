import dlt

CORRUPTED_ROWS_NAME = "corrupted_rows"
RAW_DATA_NAME = "raw_staging"
CLEAN_DATA_NAME = "clean_data"

def load_to_postgres(con):
    # Setup dlt pipeline
    # TODO: Configure data warehouse info
    pipeline = dlt.pipeline(
        pipeline_name='duckdb_to_postgres',
        destination="postgres",
        dataset_name='postgres'
    )
    
    # Stream clean data to data warehouse
    arrow_table = con.table(f"{CLEAN_DATA_NAME}").arrow()
    corrupted_table = con.table(f"{CORRUPTED_ROWS_NAME}").arrow()

    info = pipeline.run(
        arrow_table, 
        table_name="final_patient_records",
        write_disposition="merge", 
        primary_key="original_csv_row_id"
    )

    corrupted = pipeline.run(
        corrupted_table,
        table_name="corrupted_rows",
        write_disposition="merge", 
        primary_key="original_csv_row_id"
    )

    return info, corrupted