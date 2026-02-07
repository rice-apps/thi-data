from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from core.database import reflect_db
from core.deps import init_storage_provider
from api import metadata, tables, rows, reflect, validation, corrupted_rows, upload
from FakeS3.fakeS3 import FakeS3
import core.config as config
from celery_task import process_patient_file

origins = [
    config.settings.ORIGIN_URL
]

@asynccontextmanager
async def lifespan(app: FastAPI):
    reflect_db()
    init_storage_provider(FakeS3())
    yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"], 
)

# --- API Endpoints ---

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.post("/process_file/")
def process_file(file_id: str, proposed_schema: dict):
    """
    Producer endpoint: Pushes a task to the RabbitMQ queue.
    """
    try:
        task = process_patient_file.delay(file_id, proposed_schema) 
        return {"task_id": task.id, "file_id": file_id, "message": f"Processing started for file: {file_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {e}")

# Include Routers
app.include_router(corrupted_rows.router)
app.include_router(validation.router)
app.include_router(metadata.router)
app.include_router(reflect.router)
app.include_router(tables.router)
app.include_router(rows.router)
