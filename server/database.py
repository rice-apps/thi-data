import os
from dotenv import load_dotenv
from sqlalchemy import NullPool, create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.automap import automap_base

load_dotenv()

USER = os.getenv("user")
PASSWORD = os.getenv("password")
HOST = os.getenv("host")
PORT = int(os.getenv("port", 8000))
DBNAME = os.getenv("dbname")

DATABASE_URL = f"postgresql+psycopg://{USER}:{PASSWORD}@{HOST}:{PORT}/{DBNAME}?sslmode=require"
engine = create_engine(DATABASE_URL, poolclass=NullPool)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = automap_base()

def reflect_db():
    Base.prepare(autoload_with=engine)
    print(f"Tables reflected: {list(Base.classes.keys())}")