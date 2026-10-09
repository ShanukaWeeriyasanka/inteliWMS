from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from config.settings import settings

# Database URL configuration
db_url = settings.DATABASE_URL
# Automatically normalize postgresql:// to postgresql+psycopg2:// for SQLAlchemy
if db_url.startswith("postgresql://") and not db_url.startswith("postgresql+"):
    db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)

# Connect args (only check_same_thread for SQLite)
connect_args = {}
engine_kwargs = {"pool_pre_ping": True}

if db_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
else:
    # Cloud PostgreSQL / Supabase pool recycling to prevent connection drops
    engine_kwargs["pool_recycle"] = 300
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20

try:
    engine = create_engine(db_url, connect_args=connect_args, **engine_kwargs)
    with engine.connect() as _test_conn:
        pass
except Exception:
    # Graceful fallback to local SQLite for offline development and testing
    db_url = "sqlite:///./intelliwms.db"
    connect_args = {"check_same_thread": False}
    engine = create_engine(db_url, connect_args=connect_args)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Base class for all ORM models
Base = declarative_base()

def init_db():
    """Create all tables and perform lightweight safe schema migrations."""
    from database import models  # ensure models are imported
    Base.metadata.create_all(bind=engine)
    
    # Safe SQLite column migrations if needed
    if settings.DATABASE_URL.startswith("sqlite"):
        try:
            with engine.connect() as conn:
                # Check columns in users table
                from sqlalchemy import text
                result = conn.execute(text("PRAGMA table_info(users)"))
                cols = [row[1] for row in result.fetchall()]
                if "name" not in cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN name VARCHAR"))
                    conn.commit()
        except Exception as e:
            print(f"[DB MIGRATION NOTICE] {e}")

def get_db():
    """Dependency injection helper for FastAPI routes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
