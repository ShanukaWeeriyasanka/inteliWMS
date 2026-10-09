"""
Shared pytest fixtures and configuration for IntelliWMS test suite.
Provides database initialisation, knowledge store seeding, and FastAPI test clients
as reusable session and function-scoped fixtures.
"""
import os
os.environ["DATABASE_URL"] = "sqlite:///./intelliwms.db"

import pytest
from fastapi.testclient import TestClient

from database.connection import init_db
from agents.knowledge_agent.knowledge_store import knowledge_store, seed_warehouse_sops

from agents.knowledge_agent.server import app as knowledge_app


# --------------------------------------------------------------------------- #
# Session-scoped: runs once per test session                                   #
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="session", autouse=True)
def initialise_database():
    """Ensure SQLite tables exist before any test accesses the DB."""
    init_db()


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
