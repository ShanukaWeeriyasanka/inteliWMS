"""FastAPI dependencies for chat threads (own DB session; identity from the Authorization header)."""
from typing import Iterator, Optional

from fastapi import Header

from backend.auth import Identity, resolve_identity
from backend.threads.errors import ThreadAuthRequired
from backend.threads.store import ThreadStore
from database.connection import SessionLocal


def get_thread_store() -> Iterator[ThreadStore]:
    """Separate session from the request's get_db(), so an agent's failed transaction can't
    roll back (or be rolled back by) conversation history writes."""
    session = SessionLocal()
    try:
        yield ThreadStore(session)
    finally:
        session.close()


def optional_identity(authorization: Optional[str] = Header(None)) -> Identity:
    return resolve_identity(None, authorization)


def require_identity(authorization: Optional[str] = Header(None)) -> Identity:
    identity = resolve_identity(None, authorization)
    if not identity.authenticated:
        raise ThreadAuthRequired()
    return identity
