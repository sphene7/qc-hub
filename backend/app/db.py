"""
Database connection and session management.
"""
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
from dotenv import load_dotenv
import pymysql

# Load environment variables
load_dotenv()

DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = int(os.getenv('DB_PORT', '3306'))
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_NAME = os.getenv('DB_NAME', 'excel_to_web')

# Database URL
DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"

# Create engine (will be initialized after DB creation)
engine = None
SessionLocal = None


def init_database():
    """Create database if it doesn't exist, then initialize engine and tables."""
    global engine, SessionLocal
    
    # First, connect without specifying database to create it if needed
    conn_url = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/?charset=utf8mb4"
    temp_engine = create_engine(conn_url, poolclass=NullPool)
    
    with temp_engine.connect() as conn:
        # Check if database exists
        result = conn.execute(text(f"SHOW DATABASES LIKE '{DB_NAME}'"))
        if not result.fetchone():
            # Create database
            conn.execute(text(f"CREATE DATABASE {DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
            print(f"Database '{DB_NAME}' created.")
        else:
            print(f"Database '{DB_NAME}' already exists.")
    
    temp_engine.dispose()
    
    # Now create engine with the database
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=False
    )
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Create all tables
    from app.models import Base
    Base.metadata.create_all(bind=engine)
    _migrate_schema(engine)
    print("Database tables initialized.")


def _migrate_schema(engine):
    """Lightweight schema patches for existing deployments."""
    with engine.connect() as conn:
        result = conn.execute(text("SHOW COLUMNS FROM project_members LIKE 'permissions'"))
        if not result.fetchone():
            conn.execute(text("ALTER TABLE project_members ADD COLUMN permissions JSON NULL"))
            conn.commit()
            print("Added project_members.permissions column.")


def get_db():
    """Get database session for FastAPI dependency injection."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_session() -> Session:
    """Get database session (for direct use)."""
    return SessionLocal()
