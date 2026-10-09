"""
Centralized Subscription Entitlement & Agent Access Control Service for IntelliWMS.

Enforces:
1. STARTER:
   - Customer-facing agent: Inventory Agent ONLY.
   - Cross-agent communication: NOT allowed.
   - Coordinator intelligent auto-routing: Internal only.
   - Dashboards: Inventory & Bay visualizer only.

2. PROFESSIONAL:
   - Customer-facing agents: Inventory Agent, Fulfillment Agent, Knowledge Agent.
   - User explicitly selects the active specialist from the dropdown.
   - Cross-agent communication: NOT allowed (agents operate independently).
   - Coordinator: NOT customer-selectable.
   - Dashboards: Specialist dashboards (Floor & Bay Map, Fulfillment Dashboard).

3. ENTERPRISE:
   - Customer-facing agents: Inventory, Fulfillment, Knowledge, Coordinator.
   - Full Coordinator autonomous routing enabled.
   - Full cross-agent collaboration enabled (e.g. Fulfillment-to-Inventory investigation).
   - Dashboards: Complete operational suite.

Safe policy: Missing, invalid, or expired entitlements safely default to 'starter'.
"""
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy.orm import Session
from database.connection import SessionLocal
from database.models import User
from utils.logger import StructuredLogger

logger = StructuredLogger(__name__)

PLAN_STARTER = "starter"
PLAN_PROFESSIONAL = "professional"
PLAN_ENTERPRISE = "enterprise"

VALID_PLANS: Set[str] = {PLAN_STARTER, PLAN_PROFESSIONAL, PLAN_ENTERPRISE}
DEFAULT_PLAN = PLAN_STARTER

AGENT_DISPLAY_NAMES: Dict[str, str] = {
    "inventory_agent": "Inventory Agent",
    "fulfillment_agent": "Fulfillment Agent",
    "knowledge_agent": "Knowledge Agent",
    "coordinator": "Coordinator Agent",
}

# Plan entitlement configurations
PLAN_ENTITLEMENTS: Dict[str, Dict[str, Any]] = {
    PLAN_STARTER: {
        "name": "Starter",
        "allowed_customer_agents": {"inventory_agent"},
        "allow_cross_agent": False,
        "requires_manual_agent_selection": False,
        "allow_specialist_dashboards": False,
        "allowed_dashboards": {"inventory", "bay_visualizer", "rbac_claims"},
    },
    PLAN_PROFESSIONAL: {
        "name": "Professional",
        "allowed_customer_agents": {"inventory_agent", "fulfillment_agent", "knowledge_agent"},
        "allow_cross_agent": False,
        "requires_manual_agent_selection": True,
        "allow_specialist_dashboards": True,
        "allowed_dashboards": {"inventory", "fulfillment", "knowledge", "bay_visualizer", "order_timeline", "rbac_claims", "soc_audit"},
    },
    PLAN_ENTERPRISE: {
        "name": "Enterprise",
        "allowed_customer_agents": {"inventory_agent", "fulfillment_agent", "knowledge_agent", "coordinator"},
        "allow_cross_agent": True,
        "requires_manual_agent_selection": False,
        "allow_specialist_dashboards": True,
        "allowed_dashboards": {"inventory", "fulfillment", "knowledge", "coordinator", "bay_visualizer", "order_timeline", "rbac_claims", "soc_audit", "twin"},
    },
}

STARTER_RESTRICTION_MESSAGE = (
    "This feature is not available in your Starter plan. "
    "Your subscription includes the Inventory Agent only. "
    "Upgrade to Professional to access Fulfillment and Knowledge."
)

COLLABORATION_REQUIRES_ENTERPRISE_MESSAGE = (
    "Further cross-agent inventory investigation requires an Enterprise subscription."
)


def normalize_plan(plan: Optional[str]) -> str:
    """Normalize and validate a plan name. Missing/unknown values safely fall back to 'starter'."""
    if not plan or not isinstance(plan, str):
        return DEFAULT_PLAN
    cleaned = plan.strip().lower()
    if cleaned in ("pro", "professional"):
        return PLAN_PROFESSIONAL
    return cleaned if cleaned in VALID_PLANS else DEFAULT_PLAN


PLAN_RANK: Dict[str, int] = {PLAN_STARTER: 0, PLAN_PROFESSIONAL: 1, PLAN_ENTERPRISE: 2}


def parse_plan_strict(plan: Any) -> Optional[str]:
    """A requested plan name, or None when it is not a real plan (no silent fallback for change requests)."""
    if not isinstance(plan, str) or not plan.strip():
        return None
    cleaned = plan.strip().lower()
    if cleaned == "pro":
        cleaned = PLAN_PROFESSIONAL
    return cleaned if cleaned in VALID_PLANS else None


def demo_plan_switching_active() -> bool:
    """The no-payment demo switcher only exists in an explicitly configured development environment."""
    from config.settings import settings
    return settings.APP_ENV == "development" and settings.DEMO_PLAN_SWITCH_ENABLED


def can_upgrade_via_demo(username: Optional[str], account_role: Optional[str]) -> bool:
    """Whether this account may raise its own tier through the demo switcher (no payment gateway)."""
    from config.settings import settings
    if not demo_plan_switching_active():
        return False
    return ((username or "").lower() in settings.DEMO_PLAN_SWITCH_USERS
            or (account_role or "").lower() in settings.DEMO_PLAN_SWITCH_ROLES)


def authorize_plan_change(current_plan: str, target_plan: str, username: Optional[str],
                          account_role: Optional[str]) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Server-side decision for a plan change. Returns (allowed, error_code, message).
    - Same or lower tier: always allowed (a downgrade never grants access).
    - Higher tier: only through the configured development demo switcher, for allow-listed accounts.
      With no payment gateway there is no other way to prove entitlement to a paid tier.
    """
    current = normalize_plan(current_plan)
    if PLAN_RANK[target_plan] <= PLAN_RANK[current]:
        return True, None, None
    if not demo_plan_switching_active():
        return False, "PLAN_UPGRADE_UNAVAILABLE", (
            "Upgrading requires a paid subscription. Plan switching for demonstrations is not enabled "
            "on this server (set APP_ENV=development and DEMO_PLAN_SWITCH_ENABLED=true).")
    if not can_upgrade_via_demo(username, account_role):
        return False, "PLAN_UPGRADE_FORBIDDEN", (
            f"Your account is not authorized to switch to the {PLAN_ENTITLEMENTS[target_plan]['name']} plan. "
            "Ask an administrator to upgrade your subscription.")
    return True, None, None


def get_user_plan(user_id: str, username: Optional[str] = None, db: Optional[Session] = None) -> str:
    """
    Retrieves the verified server-side plan entitlement for a user from the database.
    Safe default: 'starter' if user is not found or in case of any database error.
    """
    if not user_id or user_id == "anonymous":
        return DEFAULT_PLAN

    if isinstance(username, Session):
        db = username
        username = None

    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        from security.auth import resolve_db_user
        user = resolve_db_user(db, user_id, username=username)
        if user and getattr(user, "plan", None):
            return normalize_plan(user.plan)
        return DEFAULT_PLAN
    except Exception as e:
        logger.log_event("SUBSCRIPTION_LOOKUP_ERROR", {"user_id": user_id, "error": str(e)}, level="WARNING")
        return DEFAULT_PLAN
    finally:
        if should_close:
            db.close()


def set_user_plan(
    user_id: str,
    new_plan: str,
    username: Optional[str] = None,
    db: Optional[Session] = None
) -> Tuple[bool, str]:
    """
    Updates the verified server-side subscription entitlement for a user.
    """
    if isinstance(username, Session):
        db = username
        username = None

    plan = normalize_plan(new_plan)
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        from security.auth import resolve_db_user
        user = resolve_db_user(db, user_id, username=username)
        if not user:
            return False, f"User '{user_id}' not found"

        user.plan = plan
        db.commit()
        db.refresh(user)
        logger.log_event("SUBSCRIPTION_PLAN_UPDATED", {"user_id": user_id, "username": user.username, "new_plan": plan}, level="INFO")
        return True, f"Subscription plan updated to '{plan}'"
    except Exception as e:
        if db:
            db.rollback()
        logger.log_event("SUBSCRIPTION_UPDATE_ERROR", {"user_id": user_id, "error": str(e)}, level="ERROR")
        return False, f"Database error updating subscription: {e}"
    finally:
        if should_close:
            db.close()


def is_agent_allowed(plan: str, target_agent: str) -> bool:
    """Checks whether target_agent is customer-accessible in the given plan."""
    norm_plan = normalize_plan(plan)
    entitlements = PLAN_ENTITLEMENTS.get(norm_plan, PLAN_ENTITLEMENTS[DEFAULT_PLAN])
    return target_agent in entitlements["allowed_customer_agents"]


def validate_agent_access(plan: str, target_agent: str) -> Tuple[bool, Optional[str]]:
    """
    Validates agent access against plan permissions.
    Returns (True, None) if allowed, or (False, user_friendly_message) if restricted.
    """
    norm_plan = normalize_plan(plan)
    if is_agent_allowed(norm_plan, target_agent):
        return True, None

    if norm_plan == PLAN_STARTER:
        return False, STARTER_RESTRICTION_MESSAGE

    agent_name = AGENT_DISPLAY_NAMES.get(target_agent, target_agent)
    plan_name = PLAN_ENTITLEMENTS.get(norm_plan, {}).get("name", norm_plan.capitalize())
    return False, f"Access restricted: The {agent_name} is not included in your {plan_name} plan. Upgrade to access this feature."


def validate_specialist_match(plan: str, selected_agent: str, classified_agent: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    For Professional plan users, checks if the query belongs to the chosen specialist.
    If there is a domain mismatch, does NOT silently reroute; returns (False, explanation_message, suggested_agent).
    """
    norm_plan = normalize_plan(plan)
    if norm_plan != PLAN_PROFESSIONAL:
        return True, None, None

    # Normalization: coordinator direct responses (greetings/help) are permitted for any selected agent
    if classified_agent == "coordinator":
        return True, None, None

    if selected_agent != classified_agent:
        suggested_name = AGENT_DISPLAY_NAMES.get(classified_agent, classified_agent)
        chosen_name = AGENT_DISPLAY_NAMES.get(selected_agent, selected_agent)
        message = (
            f"This question belongs to the {suggested_name}. "
            f"As a Professional plan subscriber, please select the {suggested_name} from the specialist dropdown above to ask this question."
        )
        return False, message, classified_agent

    return True, None, None


def is_collaboration_allowed(plan: str, source_agent: str, target_agent: str) -> bool:
    """
    Checks if cross-agent (specialist-to-specialist) communication is authorized.
    Starter: False
    Professional: False
    Enterprise: True
    """
    norm_plan = normalize_plan(plan)
    entitlements = PLAN_ENTITLEMENTS.get(norm_plan, PLAN_ENTITLEMENTS[DEFAULT_PLAN])
    return bool(entitlements.get("allow_cross_agent", False))


def is_dashboard_allowed(plan: str, dashboard_key: str) -> bool:
    """Checks if a dashboard/view route is allowed under the given plan."""
    norm_plan = normalize_plan(plan)
    entitlements = PLAN_ENTITLEMENTS.get(norm_plan, PLAN_ENTITLEMENTS[DEFAULT_PLAN])
    allowed = entitlements.get("allowed_dashboards", set())
    return dashboard_key.lower() in allowed
