from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from database import reflect_db
from api import metadata, tables, metadata_filters

origins = [
    "http://localhost:3000",
]

@asynccontextmanager
async def lifespan(app: FastAPI):
    reflect_db()
    yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Allows all methods
    allow_headers=["*"], # Allows all headers
)


# --- API Endpoints ---

@app.get("/")
def read_root():
    return {"Hello": "World"}

app.include_router(metadata_filters.router)
app.include_router(metadata.router)
app.include_router(tables.router)
