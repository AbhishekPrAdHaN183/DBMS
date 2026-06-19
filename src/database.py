import os
from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Ensure data directory exists
DB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "inventory.db")

DATABASE_URL = f"sqlite:///{DB_PATH}"

# Create the engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}  # Necessary for FastAPI multi-threading
)

# Enforce Foreign Key constraints in SQLite (disabled by default)
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.close()

# Session local factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base Declarative Class for ORM models
Base = declarative_base()

@contextmanager
def get_db_session():
    """
    Context manager for database sessions.
    Automatically commits transactions or rolls back in case of exceptions.
    Ensures the session is closed.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()
