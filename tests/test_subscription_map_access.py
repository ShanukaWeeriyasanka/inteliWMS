"""
The Warehouse map (Digital Twin) is a Professional / Enterprise dashboard: the /twin API refuses
Starter accounts, whatever the browser shows. The plan is read from the database, not the token.
"""
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from inventory_testkit import token_for
from security.subscription import is_dashboard_allowed

client = TestClient(app)


@pytest.fixture(autouse=True)
def no_twin_database(monkeypatch):
    """Requests that pass the plan check stop at 'twin disabled' instead of touching a real database."""
    monkeypatch.setattr("backend.twin.routes.is_enabled", lambda: False)


def as_plan(monkeypatch, plan):
    monkeypatch.setattr("backend.twin.routes.get_user_plan", lambda *a, **k: plan)
    return {"Authorization": f"Bearer {token_for('map-user')}"}


def test_entitlements_give_the_map_to_professional_and_enterprise_only():
    assert not is_dashboard_allowed("starter", "twin")
    assert is_dashboard_allowed("professional", "twin")
    assert is_dashboard_allowed("enterprise", "twin")
    assert not is_dashboard_allowed("unknown-plan", "twin")  # unknown plans fall back to Starter


@pytest.mark.parametrize("path", ["/twin/products", "/twin/inventory-snapshot", "/twin/layout", "/twin/alerts"])
def test_starter_is_refused_by_every_map_endpoint(monkeypatch, path):
    res = client.get(path, headers=as_plan(monkeypatch, "starter"))
    assert res.status_code == 403
    assert res.json()["error_code"] == "PLAN_RESTRICTED"


def test_starter_cannot_open_the_live_map_stream(monkeypatch):
    as_plan(monkeypatch, "starter")
    res = client.get("/twin/stream", params={"access_token": token_for("map-user")})
    assert res.status_code == 403 and res.json()["error_code"] == "PLAN_RESTRICTED"


@pytest.mark.parametrize("plan", ["professional", "enterprise"])
def test_professional_and_enterprise_pass_the_plan_check(monkeypatch, plan):
    res = client.get("/twin/products", headers=as_plan(monkeypatch, plan))
    assert res.status_code == 503  # past the plan check; the test database is switched off


def test_an_account_without_a_stored_plan_is_treated_as_starter():
    res = client.get("/twin/products", headers={"Authorization": f"Bearer {token_for('no-such-user')}"})
    assert res.status_code == 403 and res.json()["error_code"] == "PLAN_RESTRICTED"


def test_sign_in_is_still_checked_before_the_plan():
    assert client.get("/twin/products").status_code == 401
