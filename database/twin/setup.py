"""
Creates the Warehouse Digital Twin schema and loads the demo data.

    schema.sql   tables, views and functions (unchanged from the design spec)
    seed.sql     demo warehouse: 3 floors, 29 racks, 12 products
    realtime.sql pg_notify triggers that feed GET /twin/stream

Safe to call on every start: schema.sql + seed.sql only run when the twin
tables do not exist yet; realtime.sql is idempotent.
"""
from database.twin.connection import get_engine, twin_schema
from utils.logger import StructuredLogger
from config.settings import settings

logger = StructuredLogger(__name__)

_LOCK_KEY = "intelliwms_twin_setup"


def _read_sql(name: str) -> str:
    return (settings.TWIN_SQL_DIR / name).read_text(encoding="utf-8")


def ensure_twin_schema(seed: bool = True, reset: bool = False) -> bool:
    """Create (or with reset=True, rebuild) the twin schema. Returns True if it was created."""
    schema = twin_schema()
    raw = get_engine().raw_connection()
    created = False
    try:
        cur = raw.cursor()
        # Several processes (backend, seeder) may start at once: serialize setup.
        cur.execute("select pg_advisory_xact_lock(hashtext(%s))", (_LOCK_KEY,))
        if reset:
            cur.execute(f"drop schema if exists {schema} cascade")
        cur.execute(f"create schema if not exists {schema}")
        cur.execute(f"set local search_path to {schema}, public, extensions")
        cur.execute("select to_regclass(%s)", (f"{schema}.warehouses",))
        if cur.fetchone()[0] is None:
            cur.execute(_read_sql("schema.sql"))
            if seed:
                cur.execute(_read_sql("seed.sql"))
            created = True
        cur.execute(_read_sql("realtime.sql"))
        raw.commit()
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()

    logger.log_event("TWIN_SCHEMA_READY", {"schema": schema, "created": created, "seeded": created and seed})
    return created
