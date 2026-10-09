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
            except Exception as e:
                print(f"[DB MIGRATION NOTICE] users.name: {e}")

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

            try:
                # Safe SQLite migration for products table
                result = conn.execute(text("PRAGMA table_info(products)"))
                p_cols = [row[1] for row in result.fetchall()]
                product_columns = {
                    "category": "VARCHAR(100)",
                    "quantity": "INTEGER DEFAULT 0",
                    "safety_stock": "INTEGER DEFAULT 10",
                    "reorder_point": "INTEGER DEFAULT 20",
                    "reorder_quantity": "INTEGER DEFAULT 50",
                    "reserved_quantity": "INTEGER DEFAULT 0",
                    "unit": "VARCHAR(50) DEFAULT 'units'",
                    "daily_burn_rate": "FLOAT DEFAULT 1.0",
                    "lead_time_days": "INTEGER DEFAULT 5",
                    "unit_price": "FLOAT DEFAULT 10.0",
                    "weight_kg": "FLOAT DEFAULT 1.0",
                    "location": "VARCHAR(255)",
                    "aisle": "INTEGER DEFAULT 1",
                    "shelf": "VARCHAR(50)",
                    "tier": "VARCHAR(50)",
                    "bay": "VARCHAR(50)",
                    "occupancy_pct": "FLOAT DEFAULT 0.0",
                    "temperature": "VARCHAR(100)",
                    "is_hazardous": "BOOLEAN DEFAULT 0",
                    "max_stack_tier": "INTEGER DEFAULT 3",
                    "created_at": "DATETIME",
                    "updated_at": "DATETIME",
                }
                for col_name, col_type in product_columns.items():
                    if col_name not in p_cols:
                        conn.execute(text(f"ALTER TABLE products ADD COLUMN {col_name} {col_type}"))
                conn.commit()

                # Seed baseline products if table is empty
                res = conn.execute(text("SELECT count(*) FROM products"))
                count = res.scalar() or 0
                if count == 0:
                    conn.execute(text("""
                        INSERT INTO products (sku, name, category, quantity, location, aisle, shelf, tier, bay)
                        VALUES
                        ('SKU-4521', 'Wireless Barcode Scanner', 'Electronics & Tech', 340, 'Aisle 12, Shelf B3, Bay 04', 12, 'B3', 'B', 'Bay 04'),
                        ('SKU-7788', 'Thermal Label Printer', 'Dispatch Equipment', 15, 'Aisle 5, Shelf A1, Bay 02', 5, 'A1', 'A', 'Bay 02'),
                        ('SKU-9012', 'Heavy Duty Pallet Wrap', 'Packaging Consumables', 5, 'Aisle 3, Shelf C2, Bay 08', 3, 'C2', 'C', 'Bay 08'),
                        ('SKU-1088', 'Thermal Industrial Label Rolls', 'Consumables', 120, 'Aisle 1, Bay A-03, Shelf A3', 1, 'A3', 'A', 'Bay A-03'),
                        ('SKU-2045', 'Heavy Duty Forklift Battery Lithium', 'Heavy Hazmat / Power', 42, 'Aisle 4, Bay B-12, Shelf B12', 4, 'B12', 'B', 'Bay B-12')
                    """))
                    conn.commit()
            except Exception as e:
                print(f"[DB MIGRATION NOTICE] products table migration: {e}")
        else:
            # ---- PostgreSQL (Supabase) migration ----
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

            try:
                product_columns = {
                    "category": "VARCHAR(100)",
                    "quantity": "INTEGER DEFAULT 0",
                    "safety_stock": "INTEGER DEFAULT 10",
                    "reorder_point": "INTEGER DEFAULT 20",
                    "reorder_quantity": "INTEGER DEFAULT 50",
                    "reserved_quantity": "INTEGER DEFAULT 0",
                    "unit": "VARCHAR(50) DEFAULT 'units'",
                    "daily_burn_rate": "FLOAT DEFAULT 1.0",
                    "lead_time_days": "INTEGER DEFAULT 5",
                    "unit_price": "FLOAT DEFAULT 10.0",
                    "weight_kg": "FLOAT DEFAULT 1.0",
                    "location": "VARCHAR(255)",
                    "aisle": "INTEGER DEFAULT 1",
                    "shelf": "VARCHAR(50)",
                    "tier": "VARCHAR(50)",
                    "bay": "VARCHAR(50)",
                    "occupancy_pct": "FLOAT DEFAULT 0.0",
                    "temperature": "VARCHAR(100)",
                    "is_hazardous": "BOOLEAN DEFAULT FALSE",
                    "max_stack_tier": "INTEGER DEFAULT 3",
                    "created_at": "TIMESTAMP WITH TIME ZONE",
                    "updated_at": "TIMESTAMP WITH TIME ZONE",
                }
                for col_name, col_type in product_columns.items():
                    conn.execute(text(
                        f"ALTER TABLE products ADD COLUMN IF NOT EXISTS {col_name} {col_type}"
                    ))
                conn.commit()
            except Exception as e:
                print(f"[DB MIGRATION NOTICE] products table migration (postgres): {e}")

def get_db():
    """Dependency injection helper for FastAPI routes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
