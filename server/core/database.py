import os
from sqlalchemy import create_engine, text, PrimaryKeyConstraint, MetaData
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.pool import NullPool
import logging
import time
from .config import settings
from sqlalchemy_dlock.factory import create_sadlock 

logging.basicConfig()
logger = logging.getLogger("sqlalchemy.engine")
logger.setLevel(logging.INFO)

engine = create_engine(settings.DATABASE_URL, poolclass=NullPool)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = automap_base()

REFRESH_KEY = 'db_reflection_schema_refresh'

# Schema-aware class registry: (schema, table_name) -> mapped class
_schema_class_map = {}

def _rebuild_class_map():
    """Rebuild the schema-qualified class map after Base.prepare().
    Uses atomic reference swap so readers never see a partial dict."""
    new_map = {}
    for name, cls in Base.classes.items():
        schema = cls.__table__.schema or "public"
        new_map[(schema, name)] = cls
    global _schema_class_map
    _schema_class_map = new_map

def get_class(table_name, schema=None):
    """Look up a reflected class by table name.
    If schema is None, checks DLT schema first, then public."""
    if schema is not None:
        return _schema_class_map.get((schema, table_name))
    # DLT first, then public
    return (
        _schema_class_map.get((settings.DLT_DATASET, table_name))
        or _schema_class_map.get(("public", table_name))
    )

def get_class_strict(table_name, schema):
    """Look up a reflected class requiring an explicit schema."""
    return _schema_class_map.get((schema, table_name))

def is_dlt_table(model_class):
    """Check whether a mapped class belongs to the DLT dataset schema."""
    return model_class.__table__.schema == settings.DLT_DATASET

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

    Creates a fresh automap_base each time to avoid stale internal mapper state
    that occurs when calling prepare() after classes.clear()/by_module.clear().
    The module-level Base reference is atomically swapped so readers never see
    a partially-built registry.
    """
    global Base
    try:
        with engine.connect() as conn:
            # Create the lock so multiple workers don't reflect at the same time
            lock = create_sadlock(conn, REFRESH_KEY)
            
            with lock:
                # Create a fresh automap_base to avoid stale mapper state.
                # SQLAlchemy's automap_base.prepare() doesn't reliably
                # regenerate mapped classes after classes.clear()/by_module.clear()
                # because internal mapper registries become desynced.
                NewBase = automap_base()

                # Reflect the public schema
                NewBase.prepare(autoload_with=engine)

                # Reflect the DLT dataset schema so tables like
                # final_patient_records are visible to the API.
                #    DLT tables lack primary keys, so automap won't create
                #    classes for them unless we designate a surrogate PK.
                dlt_schema = settings.DLT_DATASET
                try:
                    NewBase.metadata.reflect(bind=engine, schema=dlt_schema)

                    # Set surrogate PK on DLT tables so automap can map them.
                    # DLT tables have no PK constraints; we designate
                    # original_csv_row_id (the DLT merge key) as surrogate PK.
                    for key, table in list(NewBase.metadata.tables.items()):
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

                    NewBase.prepare(autoload_with=engine)
                except Exception as e:
                    logger.warning(f"Could not reflect DLT schema '{dlt_schema}': {e}")

                # Atomically swap the module-level Base
                Base = NewBase
                _rebuild_class_map()

                # Reset repository caches that hold model classes from the old Base
                from core.deps import clear_caches
                clear_caches()

        logger.info(f"Tables reflected successfully: {list(Base.classes.keys())}")
    except Exception as e:
        logger.error(f"Error reflecting database: {e}")
        raise