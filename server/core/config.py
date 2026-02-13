import os
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseModel):
    # Database
    USER: str = os.getenv("user", "postgres")
    PASSWORD: str = os.getenv("password", "password")
    HOST: str = os.getenv("host", "db") # Default to 'db' for docker-compose
    PORT: str = os.getenv("port", "5432")
    DBNAME: str = os.getenv("dbname", "postgres")

    # Storage Settings (SeaweedFS / S3)
    USE_S3: bool = os.getenv("USE_S3", "false").lower() == "true"
    S3_ENDPOINT: str = os.getenv("S3_ENDPOINT", "http://localhost:8333")
    S3_KEY: str = os.getenv("S3_KEY", "")
    S3_SECRET: str = os.getenv("S3_SECRET", "")
    S3_BUCKET: str = os.getenv("S3_BUCKET", "thi-data")
    S3_REGION: str = os.getenv("S3_REGION", "us-east-1")

    # Supabase (Legacy/Cloud option)
    STORAGE_URL: str = os.getenv("NEXT_PUBLIC_SUPABASE_URL", "")
    STORAGE_SERVICE_KEY: str = os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "")

    # Celery / RabbitMQ
    BROKER_URL: str = os.getenv("broker_url", "amqp://guest:guest@localhost:5672/")

    # CORS
    ORIGIN_URL: str = os.getenv("origin_url", "http://localhost:3000")

    # ETL & DLT Settings
    DLT_DESTINATION: str = os.getenv("DLT_DESTINATION", "postgres")
    DLT_DATASET: str = os.getenv("DLT_DATASET", "clinical_data")
    DUCKDB_TEMP_DIR: str = os.getenv("DUCKDB_TEMP_DIR", os.path.join(os.getcwd(), "tmp_duckdb_spill"))
    
    @property
    def DATABASE_URL(self) -> str:
        # Standard SQLAlchemy URL with driver
        return f"postgresql+psycopg2://{self.USER}:{self.PASSWORD}@{self.HOST}:{self.PORT}/{self.DBNAME}"

    @property
    def DLT_CREDENTIALS(self) -> str:
        # DLT-friendly URL (no +psycopg2 driver prefix)
        return f"postgresql://{self.USER}:{self.PASSWORD}@{self.HOST}:{self.PORT}/{self.DBNAME}"

settings = Settings()
