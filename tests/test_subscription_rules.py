"""
Subscription plan rules, end to end through POST /query and the dashboard endpoints:

- Starter:      Inventory Agent only; no dashboards (no Warehouse map / floor plan).
- Professional: the user must pick Inventory, Fulfillment or Knowledge; that agent answers.
                No Coordinator routing, no silent switching. All dashboards.
- Enterprise:   the user only writes the prompt; the Coordinator picks the agent.

The plan is set per test (no database or .env dependency); questions are matched by the
coordinator's code rules, so no LLM is called.
"""
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from inventory_testkit import token_for
from security.subscription import is_dashboard_allowed

client = TestClient(app)

INVENTORY_Q = "How many SKU-1001 are on hand?"
FULFILLMENT_Q = "Track order ORD-1001"


def on_plan(monkeypatch, plan, role="staff"):
    """Signed-in headers for a user whose stored plan is `plan`."""
    monkeypatch.setattr("backend.auth.get_user_plan", lambda *a, **k: plan)
    monkeypatch.setattr("backend.main.get_user_plan", lambda *a, **k: plan)
    return {"Authorization": f"Bearer {token_for('plan-user', role=role)}"}


def ask(headers, text, selected_agent=None):
    body = {"message": text, **({"selected_agent": selected_agent} if selected_agent else {})}
    res = client.post("/query", json=body, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


# ── Starter ─────────────────────────────────────────────────────────────────

def test_starter_gets_the_inventory_agent(monkeypatch, inventory_server):
    data = ask(on_plan(monkeypatch, "starter"), INVENTORY_Q)
    assert data["agent_used"] == "inventory_agent" and data["status"] == "success"


def test_starter_cannot_reach_other_agents_even_by_selecting_them(monkeypatch, inventory_server):
    headers = on_plan(monkeypatch, "starter")
    for selected in (None, "fulfillment_agent", "knowledge_agent", "coordinator"):
        data = ask(headers, FULFILLMENT_Q, selected)
        assert data["status"] == "restricted" and data["error_code"] == "PLAN_RESTRICTED", selected


def test_starter_selection_never_moves_an_inventory_question_elsewhere(monkeypatch, inventory_server):
    data = ask(on_plan(monkeypatch, "starter"), INVENTORY_Q, "knowledge_agent")
    assert data["agent_used"] == "inventory_agent"


# ── Professional ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("selected", [None, "auto", "unknown_agent"])
def test_professional_must_choose_a_specialist(monkeypatch, inventory_server, selected):
    data = ask(on_plan(monkeypatch, "professional"), INVENTORY_Q, selected)
    assert data["status"] == "restricted"
    assert data["error_code"] == "SPECIALIST_REQUIRED"
    assert data["agent_used"] == "coordinator"  # refused before any agent runs
    assert "specialist dropdown" in data["response"]


def test_professional_cannot_choose_the_coordinator(monkeypatch, inventory_server):
    data = ask(on_plan(monkeypatch, "professional"), INVENTORY_Q, "coordinator")
    assert data["status"] == "restricted" and data["error_code"] == "PLAN_RESTRICTED"
    assert data["required_plan"] == "enterprise"


def test_professional_chosen_specialist_answers(monkeypatch, inventory_server):
    data = ask(on_plan(monkeypatch, "professional"), INVENTORY_Q, "inventory_agent")
    assert data["status"] == "success" and data["agent_used"] == "inventory_agent"


def test_professional_question_for_another_specialist_is_not_rerouted(monkeypatch, inventory_server):
    data = ask(on_plan(monkeypatch, "professional"), FULFILLMENT_Q, "inventory_agent")
    assert data["status"] == "mismatch" and data["error_code"] == "SPECIALIST_MISMATCH"
    assert data["suggested_agent"] == "fulfillment_agent"


# ── Enterprise ──────────────────────────────────────────────────────────────

def test_enterprise_coordinator_picks_the_agent_from_the_prompt(monkeypatch, inventory_server):
    headers = on_plan(monkeypatch, "enterprise")
    assert ask(headers, INVENTORY_Q)["agent_used"] == "inventory_agent"
    assert ask(headers, FULFILLMENT_Q)["agent_used"] == "fulfillment_agent"


def test_enterprise_ignores_a_specialist_selection(monkeypatch, inventory_server):
    data = ask(on_plan(monkeypatch, "enterprise"), FULFILLMENT_Q, "inventory_agent")
    assert data["agent_used"] == "fulfillment_agent"


# ── Dashboards ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("dashboard", ["twin", "bay_visualizer", "fulfillment", "soc_audit", "order_timeline"])
def test_starter_has_no_dashboards(dashboard):
    assert not is_dashboard_allowed("starter", dashboard)


@pytest.mark.parametrize("plan", ["professional", "enterprise"])
@pytest.mark.parametrize("dashboard", ["twin", "fulfillment", "soc_audit", "order_timeline", "inventory"])
def test_professional_and_enterprise_have_every_dashboard(plan, dashboard):
    assert is_dashboard_allowed(plan, dashboard)


def test_soc_audit_stream_needs_professional_or_enterprise(monkeypatch):
    res = client.get("/security/audit-logs", headers=on_plan(monkeypatch, "starter", role="manager"))
    assert res.status_code == 403 and res.json()["error_code"] == "PLAN_RESTRICTED"
    for plan in ("professional", "enterprise"):
        assert client.get("/security/audit-logs", headers=on_plan(monkeypatch, plan, role="manager")).status_code == 200


def test_soc_audit_stream_still_needs_a_manager_or_admin(monkeypatch):
    res = client.get("/security/audit-logs", headers=on_plan(monkeypatch, "enterprise", role="staff"))
    assert res.status_code == 403
