from celery import Celery
from services.etl_processor import process_file_task
from typing import Literal

# TODO: Change to actual rabbitmq image location
app = Celery('tasks', broker='pyamqp://guest@localhost//')

# TODO: To be filled in when file registry/S3 exists
def download_file_from_s3(bucket: str, key: str, destination: str) -> Literal["SUCCESS", "FAILURE"]:
    pass
def get_object_key(file_id: str) -> Literal["SUCCESS", "FAILURE"]:
    try:
        pass
    except Exception:
        pass
    
def get_status(file_id: str) -> Literal["PROCESSING", "SUCCESS", "FAILURE"]:
    pass
def update_status(file_id: str, status: Literal["PROCESSING", "SUCCESS", "FAILURE"]):
    pass

@app.task(bind=True, acks_late=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def process_patient_file(self, file_id: str, proposed_schema: dict) -> dict:
    """
    Celery task to process a patient data file.

    :param file_id: Identifier of the file to be processed.
    """
    update_status(file_id, "PROCESSING")
    object_key = get_object_key(file_id)
    file_path = f"/tmp/{file_id}_{object_key}"


    status = download_file_from_s3(bucket="my-bucket", key=object_key, destination=file_path)
    update_status(file_id, status)
    
    return process_file_task(file_path, proposed_schema)
