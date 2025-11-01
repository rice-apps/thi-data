import os
from dotenv import load_dotenv
from sqlalchemy import NullPool, create_engine, select, Column, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session
load_dotenv()

USER = os.getenv("user")
PASSWORD = os.getenv("password")
HOST = os.getenv("host")
PORT = os.getenv("port")
DBNAME = os.getenv("dbname")

DATABASE_URL = f"postgresql+psycopg2://{USER}:{PASSWORD}@{HOST}:{PORT}/{DBNAME}?sslmode=require"
engine = create_engine(DATABASE_URL, poolclass=NullPool)

def get_session():
    return Session(engine)

class Base(DeclarativeBase):
    pass

class User(Base):
    # This will be the name of the table in your database
    __tablename__ = 'thi_database' 
    
    # We add an 'id' column, which is essential for an ORM
    id: Mapped[int] = mapped_column(primary_key=True)
    
    # These columns are from your example
    first_name: Mapped[str] = mapped_column(String(50))
    last_name: Mapped[str] = mapped_column(String(50))
    age: Mapped[int] = mapped_column(Integer)

    # This special method helps print the object nicely
    def __repr__(self) -> str:
        return f"User(id={self.id}, name='{self.first_name} {self.last_name}', age={self.age})"