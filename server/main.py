from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from core.deps import init_app_services
from api import metadata, tables, rows, reflect, validation, corrupted_rows, files, events
import core.config as config
import logging

# Centralized root logger config — all getLogger(__name__) loggers inherit this
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s",
)

origins = [
    config.settings.ORIGIN_URL
]

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Standard service initialization for both API and Worker
    init_app_services()
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

# Include Routers
app.include_router(corrupted_rows.router)
app.include_router(validation.router)
app.include_router(metadata.router)
app.include_router(reflect.router)
app.include_router(events.router)
app.include_router(files.router)
app.include_router(tables.router)
app.include_router(rows.router)
