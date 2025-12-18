from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.pool import NullPool
import logging
from .config import settings

# Configure Logging
logging.basicConfig()
logger = logging.getLogger("sqlalchemy.engine")
logger.setLevel(logging.WARNING)

engine = create_engine(settings.DATABASE_URL, poolclass=NullPool)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = automap_base()

def reflect_db():
    try:
        Base.prepare(autoload_with=engine)
        logging.info(f"Tables reflected: {list(Base.classes.keys())}")
    except Exception as e:
        logging.error(f"Error reflecting database: {e}")
