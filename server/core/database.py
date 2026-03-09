import os
from sqlalchemy import create_engine, text, PrimaryKeyConstraint
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
    Reflects both the public schema and the DLT dataset schema.
    """

    
    try:
        with engine.connect() as conn:
            # 1. Create the lock so multiple workers don't reflect at the same time
            lock = create_sadlock(conn, REFRESH_KEY)
            
            with lock:
                # 2. Reflect the public schema
                Base.prepare(autoload_with=engine)

                # 3. Also reflect the DLT dataset schema so tables like
                #    final_patient_records are visible to the API.
                #    DLT tables lack primary keys, so automap won't create
                #    classes for them unless we designate a surrogate PK.
                dlt_schema = settings.DLT_DATASET
                try:
                    Base.metadata.reflect(bind=engine, schema=dlt_schema)

                    # Set surrogate PK on DLT tables so automap can map them.
                    # DLT tables have no PK constraints; we designate
                    # original_csv_row_id (the DLT merge key) as surrogate PK.
                    for key, table in list(Base.metadata.tables.items()):
                        if table.schema != dlt_schema:
                            continue
                        # Skip DLT internal tables
                        if table.name.startswith("_dlt_"):
                            continue
                        # Use original_csv_row_id as surrogate PK if available
                        if not list(table.primary_key.columns) and "original_csv_row_id" in table.c:
                            table.append_constraint(
                                PrimaryKeyConstraint(table.c.original_csv_row_id)
                            )

                    Base.prepare(autoload_with=engine)
                except Exception as e:
                    logger.warning(f"Could not reflect DLT schema '{dlt_schema}': {e}")

        logger.info(f"Tables reflected successfully: {list(Base.classes.keys())}")
    except Exception as e:
        logger.error(f"Error reflecting database: {e}")
        raise