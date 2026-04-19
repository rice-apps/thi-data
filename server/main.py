from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from core.logging_config import configure_logging
from core.deps import init_app_services
from api import metadata, tables, rows, reflect, validation, corrupted_rows, files, events
import core.config as config

configure_logging()

origins = [
    config.settings.ORIGIN_URL
]

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Standard service initialization for both API and Worker
    init_app_services()
    yield

# Docs/OpenAPI under /api/* so the nginx API prefix and Makefile URLs stay consistent.
app = FastAPI(
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"], 
)


@app.get("/")
def read_root():
    return {"Hello": "World"}

app.include_router(corrupted_rows.router)
app.include_router(validation.router)
app.include_router(metadata.router)
app.include_router(reflect.router)
app.include_router(events.router)
app.include_router(files.router)
app.include_router(tables.router)
app.include_router(rows.router)
