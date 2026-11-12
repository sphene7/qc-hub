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


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default

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
    
    # Now create engine with the database.
    # 读请求算完 pandas 前会 rollback 把连接还回池；超时避免一条慢 SQL 一直占着连接。
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=3600,
        pool_size=_env_int("DB_POOL_SIZE", 10),
        max_overflow=_env_int("DB_MAX_OVERFLOW", 20),
        pool_timeout=_env_int("DB_POOL_TIMEOUT", 30),
        connect_args={
            "connect_timeout": _env_int("DB_CONNECT_TIMEOUT", 10),
            "read_timeout": _env_int("DB_READ_TIMEOUT", 120),
            "write_timeout": _env_int("DB_WRITE_TIMEOUT", 120),
        },
        echo=False,
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

        result = conn.execute(text("SHOW COLUMNS FROM project_members LIKE 'role_id'"))
        if not result.fetchone():
            conn.execute(text("ALTER TABLE project_members ADD COLUMN role_id INT NULL, ADD INDEX ix_project_members_role_id (role_id)"))
            conn.commit()
            print("Added project_members.role_id column.")

        for col in ("confirmer", "room_owner", "dept_head", "quality_engineer"):
            result = conn.execute(text(
                "SELECT COUNT(*) FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'sampling_exceptions' "
                f"AND COLUMN_NAME = '{col}'"
            ))
            if not result.fetchone()[0]:
                conn.execute(text(f"ALTER TABLE sampling_exceptions ADD COLUMN {col} VARCHAR(50) NULL"))
                conn.commit()
                print(f"Added sampling_exceptions.{col}.")

        result = conn.execute(text(
            "SELECT DATA_TYPE FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'sampling_submissions' "
            "AND COLUMN_NAME = 'submit_date'"
        ))
        row = result.fetchone()
        if row and str(row[0]).lower() == "date":
            conn.execute(text("ALTER TABLE sampling_submissions MODIFY submit_date DATETIME NOT NULL"))
            conn.execute(text(
                "UPDATE sampling_submissions SET submit_date = created_at "
                "WHERE TIME(submit_date) = '00:00:00'"
            ))
            conn.commit()
            print("Changed sampling_submissions.submit_date to DATETIME.")

        result = conn.execute(text("SHOW COLUMNS FROM sampling_submissions LIKE 'part_no'"))
        if not result.fetchone():
            conn.execute(text("ALTER TABLE sampling_submissions ADD COLUMN part_no VARCHAR(100) NULL, ADD INDEX ix_sampling_submissions_part_no (part_no)"))
            # 旧数据：model 存的是完整部番，拆成 part_no + model(机种)
            conn.execute(text("UPDATE sampling_submissions SET part_no = model WHERE part_no IS NULL"))
            conn.execute(text("UPDATE sampling_submissions SET model = SUBSTRING_INDEX(model, '-', 1) WHERE model LIKE '%-%'"))
            conn.execute(text("UPDATE sampling_submissions SET series = model WHERE series IS NULL OR series <> model"))
            conn.commit()
            print("Added sampling_submissions.part_no and normalized 机种.")

        result = conn.execute(text("SHOW COLUMNS FROM sampling_submissions LIKE 'business_unit'"))
        if not result.fetchone():
            conn.execute(text("ALTER TABLE sampling_submissions ADD COLUMN business_unit VARCHAR(50) NULL, ADD INDEX ix_sampling_submissions_business_unit (business_unit)"))
            conn.commit()
            print("Added sampling_submissions.business_unit column.")

        result = conn.execute(text("SHOW COLUMNS FROM sampling_submissions LIKE 'submit_type'"))
        if not result.fetchone():
            conn.execute(text("ALTER TABLE sampling_submissions ADD COLUMN submit_type VARCHAR(50) NULL"))
            conn.commit()
            print("Added sampling_submissions.submit_type column.")

        result = conn.execute(text("SHOW COLUMNS FROM sampling_submissions LIKE 'completed_at'"))
        if not result.fetchone():
            conn.execute(text("ALTER TABLE sampling_submissions ADD COLUMN completed_at DATETIME NULL"))
            conn.commit()
            print("Added sampling_submissions.completed_at column.")

        result = conn.execute(text("SHOW COLUMNS FROM departments LIKE 'parent_id'"))
        if not result.fetchone():
            conn.execute(text("ALTER TABLE departments ADD COLUMN parent_id INT NULL, ADD INDEX ix_departments_parent_id (parent_id)"))
            conn.commit()
            print("Added departments.parent_id column.")

        result = conn.execute(text("SHOW COLUMNS FROM users LIKE 'department_id'"))
        if not result.fetchone():
            conn.execute(text("ALTER TABLE users ADD COLUMN department_id INT NULL, ADD INDEX ix_users_department_id (department_id)"))
            conn.commit()
            print("Added users.department_id column.")

        # 检验员名单：空表时写入历史固定名单，便于类别管理增删改
        result = conn.execute(text("SHOW TABLES LIKE 'sampling_inspectors'"))
        if result.fetchone():
            count = conn.execute(text("SELECT COUNT(*) FROM sampling_inspectors")).scalar() or 0
            if int(count) == 0:
                defaults = [
                    "张安粉", "王小兰", "周  旭", "夏爱民", "郭志文", "唐光朗",
                    "冯永秀", "李  赫", "任宁宁", "雷  璇", "武佳佳", "卢  雨",
                    "林金云", "冯祖乐", "黎薇", "黄雨洁", "周俊宏", "肖复原",
                ]
                for i, name in enumerate(defaults):
                    conn.execute(
                        text(
                            "INSERT INTO sampling_inspectors (name, active, sort_order, created_at) "
                            "VALUES (:name, 1, :sort_order, UTC_TIMESTAMP())"
                        ),
                        {"name": name, "sort_order": i + 1},
                    )
                conn.commit()
                print(f"Seeded {len(defaults)} sampling_inspectors.")

        if not _has_column(conn, "sheet_data", "submission_code"):
            conn.execute(text(
                "ALTER TABLE sheet_data ADD COLUMN submission_code VARCHAR(80) "
                "GENERATED ALWAYS AS (JSON_UNQUOTE(JSON_EXTRACT(`row_data`, '$.\"送检单号\"'))) STORED"
            ))
            conn.commit()
            print("Added sheet_data.submission_code generated column.")
        if not _has_index(conn, "sheet_data", "idx_sheet_submission_code"):
            conn.execute(text(
                "ALTER TABLE sheet_data ADD INDEX idx_sheet_submission_code "
                "(project_id, sheet_name, submission_code)"
            ))
            conn.commit()
            print("Added idx_sheet_submission_code.")
        if not _has_index(conn, "sampling_submissions", "idx_sampling_project_deleted"):
            conn.execute(text(
                "ALTER TABLE sampling_submissions ADD INDEX idx_sampling_project_deleted "
                "(project_id, deleted_at)"
            ))
            conn.commit()
            print("Added idx_sampling_project_deleted.")


def _has_column(conn, table: str, column: str) -> bool:
    result = conn.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table AND COLUMN_NAME = :column"
        ),
        {"table": table, "column": column},
    )
    return bool(result.scalar())


def _has_index(conn, table: str, index: str) -> bool:
    result = conn.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.STATISTICS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table AND INDEX_NAME = :index"
        ),
        {"table": table, "index": index},
    )
    return bool(result.scalar())


def release_db(db: Session) -> None:
    """结束当前事务，把连接还回池。读出的普通 dict / DataFrame 不受影响。"""
    try:
        db.rollback()
    except Exception:
        pass


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
