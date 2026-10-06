"""
Connection to the Warehouse Digital Twin schema.

The twin lives in its own PostgreSQL schema (default ``twin``) so its tables
(products, alerts, ...) never collide with the IntelliWMS tables in ``public``.
Every transaction sets ``search_path`` with SET LOCAL, which also works through
transaction-mode poolers such as the Supabase pooler.

The twin needs PostgreSQL (pg_trgm, plpgsql). With a SQLite DATABASE_URL and no
TWIN_DATABASE_URL the twin is simply disabled and callers fall back.
"""
import re
from contextlib import contextmanager
from typing import Iterator, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from config.settings import settings

_SCHEMA_NAME = re.compile(r"^[a-z_][a-z0-9_]*$")
_engine: Optional[Engine] = None


class TwinUnavailable(RuntimeError):
    """Raised when the twin database is not configured or cannot be reached."""


def twin_schema() -> str:
    schema = settings.TWIN_DB_SCHEMA
    if not _SCHEMA_NAME.match(schema):
        raise TwinUnavailable(f"TWIN_DB_SCHEMA '{schema}' is not a plain lowercase identifier")
    return schema


def twin_database_url() -> Optional[str]:
    """libpq-style URL of the twin database, or None when no PostgreSQL is configured."""
    url = settings.TWIN_DATABASE_URL or settings.DATABASE_URL
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql+psycopg2://"):
        url = "postgresql://" + url[len("postgresql+psycopg2://"):]
    return url if url.startswith("postgresql://") else None


def is_enabled() -> bool:
    return twin_database_url() is not None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        url = twin_database_url()
        if url is None:
            raise TwinUnavailable("The digital twin needs PostgreSQL: set TWIN_DATABASE_URL or a postgresql DATABASE_URL")
        _engine = create_engine(
            url.replace("postgresql://", "postgresql+psycopg2://", 1),
            pool_pre_ping=True,
            pool_recycle=300,
            pool_size=5,
            max_overflow=10,
        )
    return _engine


def search_path_sql() -> str:
    return f"set local search_path to {twin_schema()}, public, extensions"


@contextmanager
def twin_connection() -> Iterator[Connection]:
    """One transaction against the twin schema; commits on success, rolls back on error."""
    try:
        engine = get_engine()
        conn_cm = engine.begin()
        conn = conn_cm.__enter__()
    except TwinUnavailable:
        raise
    except Exception as exc:
        raise TwinUnavailable(f"Cannot connect to the twin database: {exc}") from exc
    try:
        conn.execute(text(search_path_sql()))
        yield conn
    except BaseException as exc:
        conn_cm.__exit__(type(exc), exc, exc.__traceback__)
        raise
    else:
        conn_cm.__exit__(None, None, None)
