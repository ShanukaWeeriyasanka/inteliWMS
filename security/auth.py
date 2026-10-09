import hashlib
from typing import Any, Dict, Optional, Tuple
from database.connection import SessionLocal, engine, Base, init_db
from database.models import User
from security.jwt_handler import jwt_handler
from security.rbac import rbac_manager
from security.audit_logger import audit_logger

# Ensure database tables and schema migrations are applied
init_db()

SALT = "intelliwms_secure_salt_2026"

# Privilege order: a user may sign in with their own role or a lower one, never a higher one
ROLE_RANK = {"staff": 0, "manager": 1, "admin": 2}
# Roles anyone may create for themselves; manager and admin accounts are created by an administrator
SELF_REGISTER_ROLES = {"staff"}
SELF_REGISTER_DENIED = ("Only staff accounts can be self-registered; "
                        "ask an administrator for manager or admin access.")


def user_id_for(role: str, db_id: int) -> str:
    return f"usr_{role}_{db_id:03d}"


def db_id_from_user_id(user_id: Any) -> Optional[int]:
    """'usr_staff_017' → 17, '17' → 17, 17 → 17, 'usr_17' → 17 (None for invalid IDs)."""
    if user_id is None:
        return None
    if isinstance(user_id, int):
        return user_id
    if not isinstance(user_id, str):
        return None
    cleaned = user_id.strip()
    if not cleaned:
        return None
    if cleaned.isdigit():
        return int(cleaned)
    if cleaned.startswith("usr_") or cleaned.startswith("user_"):
        tail = cleaned.rsplit("_", 1)[-1]
        if tail.isdigit():
            return int(tail)
    return None


class AuthService:
    """
    Database-backed Authentication Service for Task 1.
    No hardcoded in-memory state; all users and credentials are stored and verified via SQLite.
    """

    def __init__(self):
        self._ensure_seed_users()

    def _hash_password(self, password: str) -> str:
        """Hash a password using SHA-256 with salt for secure storage."""
        return hashlib.sha256(f"{SALT}:{password}".encode()).hexdigest()

    def _ensure_seed_users(self):
        """Ensure standard initial warehouse roles exist in the database."""
        db = SessionLocal()
        try:
            seed_accounts = [
                {
                    "username": "john_staff",
                    "name": "John Davis",
                    "email": "john.davis@intelliwms.local",
                    "role": "staff",
                    "plan": "starter",
                    "password": "pass123"
                },
                {
                    "username": "sarah_manager",
                    "name": "Sarah Miller",
                    "email": "sarah.miller@intelliwms.local",
                    "role": "manager",
                    "plan": "professional",
                    "password": "pass456"
                },
                {
                    "username": "admin_user",
                    "name": "Alex Vance (Admin)",
                    "email": "admin@intelliwms.local",
                    "role": "admin",
                    "plan": "enterprise",
                    "password": "admin123"
                }
            ]

            for acc in seed_accounts:
                existing = db.query(User).filter(User.username == acc["username"]).first()
                if not existing:
                    new_user = User(
                        username=acc["username"],
                        name=acc["name"],
                        email=acc["email"],
                        hashed_password=self._hash_password(acc["password"]),
                        role=acc["role"],
                        plan=acc.get("plan", "starter")
                    )
                    db.add(new_user)
                else:
                    # Update password, role, and plan to ensure valid seed state
                    existing.hashed_password = self._hash_password(acc["password"])
                    existing.role = acc["role"]
                    if not existing.plan:
                        existing.plan = acc.get("plan", "starter")
                    if not existing.name:
                        existing.name = acc["name"]
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"[AUTH INIT] Notice during database user check: {e}")
        finally:
            db.close()

    def authenticate(
        self,
        username: str,
        password: str,
        requested_role: Optional[str] = None
    ) -> Tuple[bool, Optional[str], Optional[Dict], str]:
        """
        Authenticate a user against the SQLite database.
        Returns: (success, token, user_info, message)
        """
        clean_user = username.strip().lower() if username else ""
        if not clean_user or not password:
            return False, None, None, "Username and password required"

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.username == clean_user).first()
            if not user:
                audit_logger.log_event(
                    event_type="LOGIN_FAILED",
                    severity="WARNING",
                    user_id=clean_user,
                    details={"reason": "User not found in database"}
                )
                return False, None, None, "Invalid username or password"

            # Verify password hash
            if self._hash_password(password) != user.hashed_password:
                audit_logger.log_event(
                    event_type="LOGIN_FAILED",
                    severity="WARNING",
                    user_id=clean_user,
                    role=user.role,
                    details={"reason": "Incorrect password"}
                )
                return False, None, None, "Invalid username or password"

            # A user may sign in with their own role or a lower one, never a higher one
            effective_role = requested_role or user.role
            if ROLE_RANK.get(effective_role, 99) > ROLE_RANK.get(user.role, -1):
                audit_logger.log_event(
                    event_type="LOGIN_FAILED",
                    severity="HIGH",
                    user_id=clean_user,
                    role=user.role,
                    details={"reason": f"Privilege escalation attempt to {effective_role}"}
                )
                return False, None, None, f"User '{clean_user}' is not authorized for role '{effective_role}'"

            # Generate signed JWT token
            user_id_str = user_id_for(effective_role, user.id)
            token = jwt_handler.create_token(user_id=user_id_str, role=effective_role, username=user.username)
            permissions = rbac_manager.get_permissions(effective_role)
            plan = getattr(user, "plan", "starter") or "starter"

            user_info = {
                "user_id": user_id_str,
                "db_id": user.id,
                "username": user.username,
                "name": user.name or user.username,
                "role": effective_role,
                "plan": plan,
                "subscription_plan": plan,
                "email": user.email,
                "permissions": permissions
            }

            audit_logger.log_event(
                event_type="LOGIN_SUCCESS",
                severity="INFO",
                user_id=user_id_str,
                role=effective_role,
                details={"username": user.username, "db_id": user.id, "plan": plan}
            )

            return True, token, user_info, "Authentication successful"
        finally:
            db.close()

    def register(
        self,
        username: str,
        password: str,
        role: str = "staff",
        name: Optional[str] = None
    ) -> Tuple[bool, Optional[str], Optional[Dict], str]:
        """
        Register a new user into the database and issue an active JWT token.
        Default plan is 'starter'.
        """
        clean_user = username.strip().lower() if username else ""
        if not clean_user or not password:
            return False, None, None, "Username and password are required"

        # Manager and admin accounts are never self-registered (privilege escalation)
        if role not in SELF_REGISTER_ROLES:
            audit_logger.log_event(
                event_type="REGISTER_DENIED",
                severity="HIGH",
                user_id=clean_user,
                role=role,
                details={"reason": f"Self-registration requested role '{role}'"}
            )
            return False, None, None, SELF_REGISTER_DENIED

        db = SessionLocal()
        try:
            existing = db.query(User).filter(User.username == clean_user).first()
            if existing:
                return False, None, None, f"Username '{clean_user}' is already registered in database"

            display_name = name.strip() if name and name.strip() else clean_user.capitalize()
            new_user = User(
                username=clean_user,
                name=display_name,
                email=f"{clean_user}@intelliwms.local",
                hashed_password=self._hash_password(password),
                role=role,
                plan="starter"
            )
            db.add(new_user)
            db.commit()
            db.refresh(new_user)

            user_id_str = user_id_for(role, new_user.id)
            token = jwt_handler.create_token(user_id=user_id_str, role=role, username=clean_user)
            permissions = rbac_manager.get_permissions(role)

            user_info = {
                "user_id": user_id_str,
                "db_id": new_user.id,
                "username": new_user.username,
                "name": new_user.name,
                "role": role,
                "plan": "starter",
                "subscription_plan": "starter",
                "email": new_user.email,
                "permissions": permissions
            }

            audit_logger.log_event(
                event_type="LOGIN_SUCCESS",
                severity="INFO",
                user_id=user_id_str,
                role=role,
                details={"username": clean_user, "action": "registered_in_db", "plan": "starter"}
            )

            return True, token, user_info, "Registration successful"
        except Exception as e:
            db.rollback()
            return False, None, None, f"Database error during registration: {e}"
        finally:
            db.close()

    def get_user_profile(self, user_id_or_username: str) -> Optional[Dict]:
        """Fetch a user profile by token user_id ('usr_staff_017'), numeric id, or username."""
        db = SessionLocal()
        try:
            user = None
            db_id = db_id_from_user_id(user_id_or_username)
            if db_id is not None:
                user = db.get(User, db_id)
            if user is None:
                user = db.query(User).filter((User.username == user_id_or_username) | (User.email == user_id_or_username)).first()
            if not user:
                return None

            plan = getattr(user, "plan", "starter") or "starter"
            return {
                "user_id": user_id_for(user.role, user.id),
                "db_id": user.id,
                "username": user.username,
                "name": user.name,
                "role": user.role,
                "plan": plan,
                "subscription_plan": plan,
                "email": user.email,
                "permissions": rbac_manager.get_permissions(user.role)
            }
        finally:
            db.close()

    def update_user_plan(self, user_id_or_username: str, new_plan: str) -> Tuple[bool, str, Optional[Dict]]:
        """Safely update a user's subscription plan entitlement."""
        from security.subscription import normalize_plan
        plan = normalize_plan(new_plan)
        db = SessionLocal()
        try:
            user = None
            db_id = db_id_from_user_id(user_id_or_username)
            if db_id is not None:
                user = db.get(User, db_id)
            if user is None:
                user = db.query(User).filter((User.username == user_id_or_username) | (User.email == user_id_or_username)).first()
            if not user:
                return False, f"User '{user_id_or_username}' not found", None

            user.plan = plan
            db.commit()
            db.refresh(user)

            profile = {
                "user_id": user_id_for(user.role, user.id),
                "db_id": user.id,
                "username": user.username,
                "name": user.name,
                "role": user.role,
                "plan": plan,
                "subscription_plan": plan,
                "email": user.email,
                "permissions": rbac_manager.get_permissions(user.role)
            }

            audit_logger.log_event(
                event_type="SUBSCRIPTION_CHANGED",
                severity="INFO",
                user_id=profile["user_id"],
                role=user.role,
                details={"new_plan": plan, "username": user.username}
            )

            return True, f"Subscription updated to {plan}", profile
        except Exception as e:
            db.rollback()
            return False, f"Error updating subscription: {e}", None
        finally:
            db.close()

# Singleton instance
auth_service = AuthService()
