import dlt
from core.config import settings

CORRUPTED_ROWS_NAME = "corrupted_rows"
RAW_DATA_NAME = "raw_staging"
CLEAN_DATA_NAME = "clean_data"

def load_to_postgres(con):
    # Setup dlt pipeline using settings
    pipeline = dlt.pipeline(
        pipeline_name='duckdb_to_postgres',
        destination=settings.DLT_DESTINATION,
        dataset_name=settings.DLT_DATASET,
        credentials=settings.DLT_CREDENTIALS
    )
    
    # Stream clean data to data warehouse
    arrow_table = con.table(f"{CLEAN_DATA_NAME}").arrow()
    corrupted_table = con.table(f"{CORRUPTED_ROWS_NAME}").arrow()

    info = pipeline.run(
        arrow_table, 
        table_name="final_patient_records",
        write_disposition="append"
    )

    corrupted = pipeline.run(
        corrupted_table,
        table_name="corrupted_rows",
        write_disposition="append"
    )

    return info, corrupted