"""
Verification tests for Task 5:
- Existing user login resolves to a real database user.
- /auth/me returns the correct user and plan.
- Starter -> Professional works for an authorized demo user.
- Professional -> Enterprise works.
- Enterprise -> Starter works.
- Page refresh (GET /auth/me) preserves the selected plan.
- Logout/login (POST /auth/login) preserves the selected plan.
- Missing users cannot change subscriptions.
- Forged user IDs cannot change another account's plan.
- Existing agent restrictions still work.
"""
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from database.connection import SessionLocal
from database.models import User
from security.auth import auth_service, user_id_for
from security.subscription import (
    PLAN_STARTER,
    PLAN_PROFESSIONAL,
    PLAN_ENTERPRISE,
    set_user_plan,
    get_user_plan,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def ensure_clean_demo_state():
    """Ensure john_staff exists and has starter plan before test, restore afterwards."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == "john_staff").first()
        if user:
            user.plan = PLAN_STARTER
            db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == "john_staff").first()
        if user:
            user.plan = PLAN_STARTER
            db.commit()
    finally:
        db.close()


def test_login_resolves_to_real_database_user():
    """Existing user login resolves to real database user with matching db_id, username, and plan."""
    db = SessionLocal()
    real_user = db.query(User).filter(User.username == "john_staff").first()
    db.close()
    assert real_user is not None

    res = client.post("/auth/login", json={"username": "john_staff", "password": "pass123", "role": "staff"})
    assert res.status_code == 200
    data = res.json()
    user_info = data["user"]
    assert user_info["db_id"] == real_user.id
    assert user_info["username"] == "john_staff"
    assert user_info["plan"] == "starter"
    assert user_info["user_id"] == user_id_for("staff", real_user.id)


def test_auth_me_returns_correct_user():
    """/auth/me returns the verified database record."""
    login_res = client.post("/auth/login", json={"username": "john_staff", "password": "pass123", "role": "staff"})
    token = login_res.json()["token"]

    me_res = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["username"] == "john_staff"
    assert me_data["plan"] == "starter"
    assert me_data["role"] == "staff"


def test_plan_switching_lifecycle_and_persistence():
    """
    Verifies:
    1. Starter -> Professional
    2. Professional -> Enterprise
    3. Enterprise -> Starter
    4. Page refresh (/auth/me) preserves selected plan
    5. Logout/login preserves selected plan
    """
    # 1. Login as john_staff
    login_res = client.post("/auth/login", json={"username": "john_staff", "password": "pass123", "role": "staff"})
    assert login_res.status_code == 200
    token = login_res.json()["token"]

    # --- Step 1: Starter -> Professional ---
    switch_pro = client.post(
        "/auth/set-plan",
        headers={"Authorization": f"Bearer {token}"},
        json={"plan": "professional"}
    )
    assert switch_pro.status_code == 200
    assert switch_pro.json()["plan"] == "professional"
    assert switch_pro.json()["user"]["plan"] == "professional"

    # Verify via /auth/me (simulate page refresh)
    me_pro = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_pro.status_code == 200
    assert me_pro.json()["plan"] == "professional"

    # Verify directly in database
    db = SessionLocal()
    db_user = db.query(User).filter(User.username == "john_staff").first()
    assert db_user.plan == "professional"
    db.close()

    # --- Step 2: Professional -> Enterprise ---
    switch_ent = client.post(
        "/auth/set-plan",
        headers={"Authorization": f"Bearer {token}"},
        json={"plan": "enterprise"}
    )
    assert switch_ent.status_code == 200
    assert switch_ent.json()["plan"] == "enterprise"

    me_ent = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_ent.status_code == 200
    assert me_ent.json()["plan"] == "enterprise"

    # --- Step 3: Enterprise -> Starter (Downgrade) ---
    switch_starter = client.post(
        "/auth/set-plan",
        headers={"Authorization": f"Bearer {token}"},
        json={"plan": "starter"}
    )
    assert switch_starter.status_code == 200
    assert switch_starter.json()["plan"] == "starter"

    me_starter = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_starter.status_code == 200
    assert me_starter.json()["plan"] == "starter"

    # Switch back to Professional to test logout/login preservation
    client.post("/auth/set-plan", headers={"Authorization": f"Bearer {token}"}, json={"plan": "professional"})

    # --- Step 4: Logout / Login preserves the selected plan ---
    relogin_res = client.post("/auth/login", json={"username": "john_staff", "password": "pass123", "role": "staff"})
    assert relogin_res.status_code == 200
    relogin_user = relogin_res.json()["user"]
    assert relogin_user["plan"] == "professional"
    assert relogin_user["subscription_plan"] == "professional"


def test_missing_user_cannot_change_subscriptions():
    """Missing user token fails /auth/set-plan with 404 or 401 without creating any user."""
    from security.jwt_handler import jwt_handler
    # Create token for non-existent user
    ghost_token = jwt_handler.create_token(
        user_id="usr_staff_99999",
        role="staff",
        username="nonexistent_ghost_user_xyz"
    )

    res = client.post(
        "/auth/set-plan",
        headers={"Authorization": f"Bearer {ghost_token}"},
        json={"plan": "enterprise"}
    )
    assert res.status_code == 404

    # Ensure no ghost user was silently created in database
    db = SessionLocal()
    ghost = db.query(User).filter(User.username == "nonexistent_ghost_user_xyz").first()
    db.close()
    assert ghost is None


def test_forged_user_id_in_payload_does_not_modify_other_user():
    """Frontend-supplied user_id in request body is ignored; only the authenticated caller's account changes."""
    # Ensure sarah_manager starts as professional
    set_user_plan("sarah_manager", PLAN_PROFESSIONAL)

    # Login as john_staff
    login_john = client.post("/auth/login", json={"username": "john_staff", "password": "pass123", "role": "staff"})
    john_token = login_john.json()["token"]

    # John attempts to send a payload asking to modify sarah_manager or admin_user
    res = client.post(
        "/auth/set-plan",
        headers={"Authorization": f"Bearer {john_token}"},
        json={
            "plan": "professional",
            "user_id": "usr_manager_033",
            "username": "sarah_manager",
            "db_id": 33
        }
    )
    assert res.status_code == 200
    # Response must be for john_staff, NOT sarah_manager
    assert res.json()["user"]["username"] == "john_staff"

    # Sarah's account must remain untouched as professional
    db = SessionLocal()
    sarah = db.query(User).filter(User.username == "sarah_manager").first()
    db.close()
    assert sarah.plan == "professional"


def test_agent_restrictions_enforced_by_plan():
    """Existing agent restrictions work according to the user's plan."""
    # John on Starter
    login_john = client.post("/auth/login", json={"username": "john_staff", "password": "pass123", "role": "staff"})
    john_token = login_john.json()["token"]
    client.post("/auth/set-plan", headers={"Authorization": f"Bearer {john_token}"}, json={"plan": "starter"})

    # Query fulfillment agent under starter plan
    res_starter = client.post(
        "/query",
        headers={"Authorization": f"Bearer {john_token}"},
        json={"message": "What is the status of ORD-1001?", "selected_agent": "fulfillment_agent"}
    )
    assert res_starter.status_code == 200
    data_starter = res_starter.json()
    assert data_starter.get("status") == "restricted"
    assert data_starter.get("error_code") == "PLAN_RESTRICTED"

    # Upgrade John to Professional
    client.post("/auth/set-plan", headers={"Authorization": f"Bearer {john_token}"}, json={"plan": "professional"})

    # Re-run fulfillment query under professional plan — must NOT be plan restricted
    res_pro = client.post(
        "/query",
        headers={"Authorization": f"Bearer {john_token}"},
        json={"message": "What is the status of ORD-1001?", "selected_agent": "fulfillment_agent"}
    )
    assert res_pro.status_code == 200
    data_pro = res_pro.json()
    assert data_pro.get("plan_restricted") is not True
    assert data_pro.get("error_code") != "PLAN_RESTRICTED"
