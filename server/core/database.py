import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.pool import NullPool
import logging
import time
from .config import settings

# Configure Logging
logging.basicConfig()
logger = logging.getLogger("sqlalchemy.engine")
logger.setLevel(logging.INFO)

engine = create_engine(settings.DATABASE_URL, poolclass=NullPool)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = automap_base()

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
            # Split by semicolon and filter out empty strings to execute properly
            # Actually, engine.execute(text(sql)) should work for PG with begin()
            connection.execute(text(sql))
            logger.info("Successfully applied migrations from init_db.sql")
    except Exception as e:
        logger.error(f"Error applying migrations: {e}")

def reflect_db():
    try:
        # Re-initialize Base to ensure fresh reflection if called multiple times
        # though usually called once at startup.
        Base.prepare(autoload_with=engine)
        logging.info(f"Tables reflected: {list(Base.classes.keys())}")
    except Exception as e:
        logging.error(f"Error reflecting database: {e}")
        