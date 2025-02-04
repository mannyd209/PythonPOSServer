import os
import logging
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from config import SQLALCHEMY_DATABASE_URL

logger = logging.getLogger(__name__)

# Define USB drive database directory
DB_DIR = '/media/usbdrive/pos_data'

# Ensure database directory exists
os.makedirs(DB_DIR, exist_ok=True)

# Create SQLAlchemy engine with better defaults
engine = create_engine(
    f"sqlite:///{DB_DIR}/pos_db.sqlite",
    connect_args={
        "check_same_thread": False,  # Needed for SQLite
        "timeout": 30  # Increase SQLite timeout
    },
    pool_pre_ping=True,  # Enable connection health checks
    pool_recycle=3600,  # Recycle connections after 1 hour
    echo=False  # Set to True for SQL query logging
)

# Add SQLite pragmas for better performance
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging
    cursor.execute("PRAGMA synchronous=NORMAL")  # Faster, still safe
    cursor.execute("PRAGMA foreign_keys=ON")  # Enforce foreign key constraints
    cursor.close()

# Create sessionmaker with better defaults
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False  # Prevent detached instance errors
)

# Create base class for models
Base = declarative_base()

# Dependency to get DB session with better error handling
def get_db():
    db = SessionLocal()
    try:
        # Test the connection
        db.execute("SELECT 1")
        yield db
    except SQLAlchemyError as e:
        logger.error(f"Database error: {str(e)}")
        raise
    finally:
        db.close() 