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

# Create SQLAlchemy engine
engine = create_engine(db_url, connect_args=connect_args, **engine_kwargs)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for all ORM models
Base = declarative_base()

def init_db():
    """Create all tables and perform lightweight safe schema migrations."""
    from database import models  # ensure models are imported
    Base.metadata.create_all(bind=engine)

    # Safe column migrations (idempotent — safe to run every startup)
    with engine.connect() as conn:
        from sqlalchemy import text
        is_sqlite = settings.DATABASE_URL.startswith("sqlite")

        if is_sqlite:
            # ---- SQLite migration ----
            try:
                result = conn.execute(text("PRAGMA table_info(users)"))
                cols = [row[1] for row in result.fetchall()]
                if "name" not in cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN name VARCHAR"))
                    conn.commit()
                if "plan" not in cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN plan VARCHAR(50) DEFAULT 'starter'"))
                    conn.commit()
            except Exception as e:
                print(f"[DB MIGRATION NOTICE] users columns: {e}")

            try:
                result = conn.execute(text("PRAGMA table_info(orders)"))
                existing = [row[1] for row in result.fetchall()]
                delay_cols = {
                    "delay_reason": "VARCHAR(255)",
                    "carrier_name": "VARCHAR(150)",
                    "revised_delivery_date": "DATETIME",
                }
                for col, col_type in delay_cols.items():
                    if col not in existing:
                        conn.execute(text(f"ALTER TABLE orders ADD COLUMN {col} {col_type}"))
                conn.commit()
            except Exception as e:
                print(f"[DB MIGRATION NOTICE] orders delay fields: {e}")
        else:
            # ---- PostgreSQL (Supabase) migration ----
            try:
                conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS name VARCHAR"))
                conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS plan VARCHAR(50) DEFAULT 'starter'"))
                conn.commit()
            except Exception as e:
                print(f"[DB MIGRATION NOTICE] users columns (postgres): {e}")

            try:
                delay_cols = {
                    "delay_reason": "VARCHAR(255)",
                    "carrier_name": "VARCHAR(150)",
                    "revised_delivery_date": "TIMESTAMPTZ",
                }
                for col, col_type in delay_cols.items():
                    # ADD COLUMN IF NOT EXISTS is supported in PostgreSQL 9.6+
                    conn.execute(text(
                        f"ALTER TABLE orders ADD COLUMN IF NOT EXISTS {col} {col_type}"
                    ))
                conn.commit()
            except Exception as e:
                print(f"[DB MIGRATION NOTICE] orders delay fields (postgres): {e}")

def get_db():
    """Dependency injection helper for FastAPI routes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
