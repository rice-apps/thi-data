from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, create_engine, inspect
import database
from database import User
from schema import Item, UpdateItem


app = FastAPI()
session = database.get_session()
engine = create_engine('postgresql://user:password@localhost/mydb')
inspector = inspect(engine)

#gets table names
@app.get("/api/tables")
def get_table_names():
    table_names = inspector.get_table_names()
    return table_names