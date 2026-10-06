"""
Shared pytest fixtures and configuration for IntelliWMS test suite.
Provides database initialisation, knowledge store seeding, and FastAPI test clients
as reusable session and function-scoped fixtures.
"""
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.connection import Base, init_db
from database.models import ChatMessageRecord, ChatThread
from agents.knowledge_agent.knowledge_store import knowledge_store, seed_warehouse_sops
from agents.knowledge_agent.server import app as knowledge_app


def pytest_configure(config):
    config.addinivalue_line("markers", "mcp_inmemory: real MCP protocol over the in-memory transport (no network)")
    config.addinivalue_line("markers", "mcp_live: needs a running inventory MCP server (set RUN_LIVE_MCP=1)")


@pytest.fixture(autouse=True)
def thread_db(tmp_path):
    """
    Chat threads written by API tests go to a throwaway SQLite file, never intelliwms.db.
    Yields the sessionmaker so tests can inspect what was stored.
    """
    engine = create_engine(f"sqlite:///{tmp_path / 'threads.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine, tables=[ChatThread.__table__, ChatMessageRecord.__table__])
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    app = sys.modules["backend.main"].app if "backend.main" in sys.modules else None
    if app is not None:
        from backend.threads.deps import get_thread_store
        from backend.threads.store import ThreadStore

        def _store():
            session = factory()
            try:
                yield ThreadStore(session)
            finally:
                session.close()

        app.dependency_overrides[get_thread_store] = _store
    yield factory
    if app is not None:
        from backend.threads.deps import get_thread_store
        app.dependency_overrides.pop(get_thread_store, None)
    engine.dispose()


# --------------------------------------------------------------------------- #
# Session-scoped: runs once per test session                                   #
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="session", autouse=True)
def initialise_database():
    """Ensure SQLite tables exist before any test accesses the DB."""
    init_db()


@pytest.fixture
def inventory_server(tmp_path, monkeypatch):
    """
    In-memory MCP inventory server over a seeded throwaway DB (see tests/inventory_testkit.py),
    wired into the real gateway the agent uses. The Digital Twin is switched off so answers come
    from the seeded rows only.
    """
    from mcp_servers.inventory_mcp_server import build_inventory_server
    from mcp_servers.mcp_tool_client import inventory_tool_gateway
    from inventory_testkit import seeded_inventory_db

    factory, engine = seeded_inventory_db(tmp_path / "inventory.db")
    server = build_inventory_server(session_factory=factory)
    monkeypatch.setattr(inventory_tool_gateway, "server_factory", lambda: server)
    monkeypatch.setattr("database.twin.connection.is_enabled", lambda: False)
    for name in ("INVENTORY_MCP_TRANSPORT", "INVENTORY_MCP_URL", "INVENTORY_MCP_TOKEN", "INVENTORY_DEMO_DATA"):
        monkeypatch.delenv(name, raising=False)
    yield factory
    engine.dispose()


@pytest.fixture(scope="session")
def seeded_knowledge_store():
    """Return the singleton knowledge store with SOPs seeded exactly once."""
    seed_warehouse_sops(knowledge_store)
    return knowledge_store


# --------------------------------------------------------------------------- #
# Function-scoped: resets per test                                             #
# --------------------------------------------------------------------------- #

@pytest.fixture(autouse=True)
def ensure_sops_seeded(seeded_knowledge_store):
    """
    Autouse wrapper that guarantees SOP data is present for every test.
    The actual seeding is done once at session scope; this just references it.
    """
    pass


@pytest.fixture
def knowledge_client() -> TestClient:
    """FastAPI TestClient for the Knowledge Agent microservice."""
    return TestClient(knowledge_app)
