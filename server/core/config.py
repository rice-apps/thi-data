import os
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseModel):
    USER: str = os.getenv("user", "postgres")
    PASSWORD: str = os.getenv("password", "password")
    HOST: str = os.getenv("host", "db")
    PORT: str = os.getenv("port", "5432")
    DBNAME: str = os.getenv("dbname", "postgres")

    # Supabase / generic storage
    STORAGE_URL: str = os.getenv("STORAGE_URL")
    STORAGE_SERVICE_KEY: str = os.getenv("STORAGE_SERVICE_KEY")
    
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+psycopg2://{self.USER}:{self.PASSWORD}@{self.HOST}:{self.PORT}/{self.DBNAME}?sslmode=require"

class StorageSettings(BaseModel):
    STORAGE_URL: str = os.getenv("STORAGE_URL", "")
    STORAGE_KEY: str = os.getenv("STORAGE_KEY", "")

settings = Settings()
storage_settings = StorageSettings()
