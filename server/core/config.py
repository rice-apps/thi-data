import os
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseModel):
    USER: str = os.getenv("user", "postgres")
    PASSWORD: str = os.getenv("password", "password")
    HOST: str = os.getenv("host", "localhost")
    PORT: str = os.getenv("port", "5432")
    DBNAME: str = os.getenv("dbname", "postgres")
    BROKER_URL: str = os.getenv("broker_url", "pyamqp://guest@localhost//")
    ORIGIN_URL: str = os.getenv("origin_url", "http://localhost:3000")
    
    @property
    def DATABASE_URL(self) -> str:
        db_url = f"postgresql+psycopg2://{self.USER}:{self.PASSWORD}@{self.HOST}:{self.PORT}/{self.DBNAME}?sslmode=require"
        print(f"DB_URL = {db_url}")
        return db_url

settings = Settings()
