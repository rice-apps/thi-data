import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.pool import NullPool
import logging
import time
from .config import settings
from sqlalchemy_dlock.factory import create_sadlock 

# Configure Logging
logging.basicConfig()
logger = logging.getLogger("sqlalchemy.engine")
logger.setLevel(logging.INFO)

engine = create_engine(settings.DATABASE_URL, poolclass=NullPool)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = automap_base()

REFRESH_KEY = 'db_reflection_schema_refresh'

def run_migrations():
    """
    Executes the idempotent SQL migration script.
    """
    migration_path = os.path.join(os.path.dirname(__file__), "..", "migrations", "init_db.sql")
    if not os.path.exists(migration_path):
        logger.error(f"Migration file not found at {migration_path}")
        return

    # Wait for DB to be ready
    retries = 5
    while retries > 0:
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
                break
        except Exception as e:
            logger.warning(f"DB not ready, retrying in 2s... ({retries} retries left): {e}")
            time.sleep(2)
            retries -= 1
    
    if retries == 0:
        logger.error("Could not connect to database after multiple retries.")
        return

    try:
        with open(migration_path, "r") as f:
            sql = f.read()
        
        with engine.begin() as connection:
            # Robust execution of multi-statement SQL files
            statements = [stmt.strip() for stmt in sql.split(";") if stmt.strip()]
            for statement in statements:
                connection.execute(text(statement))

            logger.info("Successfully applied migrations from init_db.sql")
    except Exception as e:
        logger.error(f"Error applying migrations: {e}")

def reflect_db():
    """
    Safely reflects the database schema into SQLAlchemy ORM models using a distributed lock.
    """

    
    try:
        with engine.connect() as conn:
            # 1. Create the lock so multiple workers don't reflect at the same time
            lock = create_sadlock(conn, REFRESH_KEY)
            
            with lock:
                # 2. Perform the actual reflection!
                Base.prepare(autoload_with=engine)
        logger.info(f"Tables reflected successfully: {list(Base.classes.keys())}")
    except Exception as e:
        logger.error(f"Error reflecting database: {e}")
        raise