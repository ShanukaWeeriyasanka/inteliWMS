"""
Subscription-Based Agent Access Control & Entitlement Security Tests.

Covers:
- Starter: Inventory only, restriction messages on Fulfillment/Knowledge, no cross-agent dispatch.
- Professional: 3 specialists selectable, domain mismatch detection, no cross-agent dispatch (Fulfillment order facts preserved with truthful Enterprise explanation).
- Enterprise: Autonomous coordinator routing, full cross-agent collaboration.
- Security: Server-side database entitlement verification, safe default fallback on invalid/missing entitlements, rejection of forged client parameters.
"""
import time
import jwt
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from config.settings import settings
from security.subscription import (
    PLAN_STARTER,
    PLAN_PROFESSIONAL,
    PLAN_ENTERPRISE,
    get_user_plan,
    set_user_plan,
    is_agent_allowed,
    is_collaboration_allowed,
    is_dashboard_allowed,
    validate_agent_access,
    validate_specialist_match,
    normalize_plan,
)
from agents.coordinator.agent_dispatcher import dispatch_to_agent
from database.connection import get_db
from database.models import User

client = TestClient(app)
TEST_SECRET = settings.JWT_SECRET


def create_token(user_id: str, username: str, role: str = "staff") -> str:
    payload = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "exp": int(time.time()) + 3600,
    }
    return jwt.encode(payload, TEST_SECRET, algorithm="HS256")


@pytest.fixture
def starter_user():
    # john_staff is seeded with starter plan
    set_user_plan("john_staff", PLAN_STARTER)
    return {"username": "john_staff", "token": create_token("user_john", "john_staff", "staff")}


@pytest.fixture
def pro_user():
    # sarah_manager is seeded with professional plan
    set_user_plan("sarah_manager", PLAN_PROFESSIONAL)
    return {"username": "sarah_manager", "token": create_token("user_sarah", "sarah_manager", "manager")}


@pytest.fixture
def enterprise_user():
    # admin_user is seeded with enterprise plan
    set_user_plan("admin_user", PLAN_ENTERPRISE)
    return {"username": "admin_user", "token": create_token("user_admin", "admin_user", "admin")}


# =========================================================================
# 1. STARTER PLAN TESTS
# =========================================================================

def test_starter_inventory_query_succeeds(starter_user):
    """Starter users can query the Inventory Agent."""
    res = client.post(
        "/query",
        json={
            "token": starter_user["token"],
            "message": "Check stock availability for SKU-3300",
            "selected_agent": "inventory_agent"
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ("success", "ok")
    assert data["agent_used"] == "inventory_agent"
    assert data.get("plan_restricted") is not True


def test_starter_fulfillment_query_blocked(starter_user):
    """Starter users asking about order fulfillment receive a friendly restriction notice."""
    res = client.post(
        "/query",
        json={
            "token": starter_user["token"],
            "message": "What is the status of order ORD-1001?",
            "selected_agent": "auto"
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert data.get("plan_restricted") is True
    assert "Starter plan" in data["response"]
    assert "Inventory Agent only" in data["response"]
    assert "Professional" in data["response"]


def test_starter_knowledge_query_blocked(starter_user):
    """Starter users asking SOP questions receive a friendly restriction notice."""
    res = client.post(
        "/query",
        json={
            "token": starter_user["token"],
            "message": "What does SOP-002 explain regarding safety?",
            "selected_agent": "auto"
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert data.get("plan_restricted") is True
    assert "Starter plan" in data["response"]


def test_starter_cross_agent_dispatch_blocked():
    """Starter users cannot perform cross-agent dispatch."""
    assert is_collaboration_allowed(PLAN_STARTER, "fulfillment_agent", "inventory_agent") is False


# =========================================================================
# 2. PROFESSIONAL PLAN TESTS
# =========================================================================

def test_pro_inventory_selected_succeeds(pro_user):
    """Professional user with Inventory Agent selected succeeds."""
    res = client.post(
        "/query",
        json={
            "token": pro_user["token"],
            "message": "Check stock availability for SKU-3300",
            "selected_agent": "inventory_agent"
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert data["agent_used"] == "inventory_agent"


def test_pro_fulfillment_selected_succeeds(pro_user):
    """Professional user with Fulfillment Agent selected succeeds on fulfillment query."""
    res = client.post(
        "/query",
        json={
            "token": pro_user["token"],
            "message": "What is the status of ORD-1001?",
            "selected_agent": "fulfillment_agent"
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert data["agent_used"] == "fulfillment_agent"
    assert "ORD-1001" in data["response"]


def test_pro_knowledge_selected_succeeds(pro_user):
    """Professional user with Knowledge Agent selected succeeds on SOP query."""
    res = client.post(
        "/query",
        json={
            "token": pro_user["token"],
            "message": "What does SOP-002 explain?",
            "selected_agent": "knowledge_agent"
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert data["agent_used"] == "knowledge_agent"


def test_pro_wrong_agent_mismatch_detected(pro_user):
    """If Pro user selects Fulfillment but asks Knowledge question, mismatch is returned without silent switch."""
    res = client.post(
        "/query",
        json={
            "token": pro_user["token"],
            "message": "What does SOP-002 describe about battery safety?",
            "selected_agent": "fulfillment_agent"
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert data.get("specialist_mismatch") is True
    assert data.get("suggested_agent") == "knowledge_agent"
    assert "Knowledge Agent" in data["response"]


def test_pro_fulfillment_cross_agent_investigation_blocked(pro_user):
    """
    When Fulfillment handles a delayed order requiring inventory investigation,
    cross-agent dispatch is blocked. Confirmed order facts are returned with truthful explanation.
    """
    # ORD-1004 is DELAYED without recorded delay reason, which normally triggers inventory consultation
    res = client.post(
        "/query",
        json={
            "token": pro_user["token"],
            "message": "Investigate why ORD-1004 is delayed",
            "selected_agent": "fulfillment_agent"
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert data["agent_used"] == "fulfillment_agent"
    response_text = data["response"]
    # Confirmed order facts are preserved
    assert "ORD-1004" in response_text or "DELAYED" in response_text or "delayed" in response_text
    # Cross-agent investigation restriction is truthfully stated
    assert "Enterprise" in response_text or "Cross-agent" in response_text or "independent" in response_text.lower()


# =========================================================================
# 3. ENTERPRISE PLAN TESTS
# =========================================================================

def test_enterprise_auto_routing(enterprise_user):
    """Enterprise users have intelligent coordinator autonomous routing enabled."""
    res = client.post(
        "/query",
        json={
            "token": enterprise_user["token"],
            "message": "Where is SKU-3300 located?",
            "selected_agent": "auto"
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert data["agent_used"] == "inventory_agent"


def test_enterprise_fulfillment_collaboration_allowed(enterprise_user):
    """Enterprise users allow cross-agent Fulfillment to Inventory collaboration."""
    assert is_collaboration_allowed(PLAN_ENTERPRISE, "fulfillment_agent", "inventory_agent") is True

    res = client.post(
        "/query",
        json={
            "token": enterprise_user["token"],
            "message": "Why is ORD-1004 delayed? Check inventory",
            "selected_agent": "auto"
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert data["agent_used"] == "fulfillment_agent"


# =========================================================================
# 4. SECURITY & ENTITLEMENT VERIFICATION
# =========================================================================

def test_forged_frontend_plan_ignored(starter_user):
    """A Starter user sending an unauthorized query with fake plan payload is rejected based on DB plan."""
    # Attempting to access knowledge agent while user in DB is Starter
    res = client.post(
        "/query",
        json={
            "token": starter_user["token"],
            "message": "What does SOP-001 say?",
            "plan": "enterprise",  # Forged parameter
            "selected_agent": "knowledge_agent"
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert data.get("plan_restricted") is True
    assert "Starter plan" in data["response"]


def test_invalid_plan_defaults_safely_to_starter():
    """Missing, None, or invalid plans normalize safely to starter."""
    assert normalize_plan(None) == PLAN_STARTER
    assert normalize_plan("invalid_tier") == PLAN_STARTER
    assert normalize_plan("unknown_plan") == PLAN_STARTER
    assert normalize_plan("starter") == PLAN_STARTER
    assert normalize_plan("professional") == PLAN_PROFESSIONAL
    assert normalize_plan("pro") == PLAN_PROFESSIONAL
    assert normalize_plan("enterprise") == PLAN_ENTERPRISE


def test_dashboard_access_entitlement():
    """Starter is restricted from fulfillment dashboard; Professional and Enterprise are allowed."""
    assert is_dashboard_allowed(PLAN_STARTER, "fulfillment") is False
    assert is_dashboard_allowed(PLAN_PROFESSIONAL, "fulfillment") is True
    assert is_dashboard_allowed(PLAN_ENTERPRISE, "fulfillment") is True


def test_set_plan_endpoint(pro_user):
    """Safe admin/dev plan switching via /auth/set-plan updates the DB correctly."""
    res = client.post(
        "/auth/set-plan",
        json={"token": pro_user["token"], "plan": "enterprise"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["plan"] == "enterprise"

    # Verify user profile reflects new plan
    me_res = client.get("/auth/me", headers={"Authorization": f"Bearer {pro_user['token']}"})
    assert me_res.status_code == 200
    assert me_res.json()["plan"] == "enterprise"


def test_real_login_and_plan_preservation():
    """Verify login with AuthService creates tokens that properly resolve the database plan."""
    from security.auth import auth_service
    # Authenticate sarah_manager as staff (sub-role login)
    ok, token, user_info, _ = auth_service.authenticate("sarah_manager", "pass456", requested_role="staff")
    assert ok is True
    assert token is not None

    # Query with this real token on fulfillment query
    res = client.post(
        "/query",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "message": "What is the status of ORD-1001?",
            "selected_agent": "fulfillment_agent"
        }
    )
    assert res.status_code == 200
    data = res.json()
    # Must NOT return Starter restriction
    assert data.get("plan_restricted") is not True
    assert data["agent_used"] == "fulfillment_agent"
    assert "Starter plan" not in data.get("response", "")


def test_starter_restricted_response_has_proper_structure(starter_user):
    """Restricted response must have clean error_code and coordinator target_agent."""
    res = client.post(
        "/query",
        headers={"Authorization": f"Bearer {starter_user['token']}"},
        json={
            "message": "What is the status of ORD-1001?",
            "selected_agent": "auto"
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "restricted"
    assert data["error_code"] == "PLAN_RESTRICTED"
    assert data["agent_used"] == "coordinator"
    assert data["routing"]["target_agent"] == "coordinator"
    assert data["routing"]["status"] == "restricted"
    assert "fulfillment_details" not in data

