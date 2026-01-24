from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from core.database import reflect_db
from api import metadata, tables, rows, upload

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
    allow_methods=["*"], 
    allow_headers=["*"], 
)

# --- API Endpoints ---

@app.get("/")
def read_root():
    return {"Hello": "World"}

# Include Routers
app.include_router(metadata.router)
app.include_router(tables.router)
app.include_router(rows.router)
app.include_router(upload.router)



    