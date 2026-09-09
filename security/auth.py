import hashlib
from typing import Dict, Optional, Tuple
from database.connection import SessionLocal, engine, Base, init_db
from database.models import User
from security.jwt_handler import jwt_handler
from security.rbac import rbac_manager
from security.audit_logger import audit_logger

# Ensure database tables and schema migrations are applied
init_db()

SALT = "intelliwms_secure_salt_2026"

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
                    "password": "pass123"
                },
                {
                    "username": "sarah_manager",
                    "name": "Sarah Miller",
                    "email": "sarah.miller@intelliwms.local",
                    "role": "manager",
                    "password": "pass456"
                },
                {
                    "username": "admin_user",
                    "name": "Alex Vance (Admin)",
                    "email": "admin@intelliwms.local",
                    "role": "admin",
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
                        role=acc["role"]
                    )
                    db.add(new_user)
                else:
                    # Update password and role to ensure valid seed state
                    existing.hashed_password = self._hash_password(acc["password"])
                    existing.role = acc["role"]
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

            # Check unauthorized privilege escalation
            effective_role = requested_role or user.role
            if user.role == "staff" and effective_role in ["manager", "admin"]:
                audit_logger.log_event(
                    event_type="LOGIN_FAILED",
                    severity="HIGH",
                    user_id=clean_user,
                    role=user.role,
                    details={"reason": f"Privilege escalation attempt to {effective_role}"}
                )
                return False, None, None, f"User '{clean_user}' is not authorized for role '{effective_role}'"

            # Generate signed JWT token
            user_id_str = f"usr_{user.role}_{user.id:03d}"
            token = jwt_handler.create_token(user_id=user_id_str, role=effective_role)
            permissions = rbac_manager.get_permissions(effective_role)

            user_info = {
                "user_id": user_id_str,
                "db_id": user.id,
                "username": user.username,
                "name": user.name or user.username,
                "role": effective_role,
                "email": user.email,
                "permissions": permissions
            }

            audit_logger.log_event(
                event_type="LOGIN_SUCCESS",
                severity="INFO",
                user_id=user_id_str,
                role=effective_role,
                details={"username": user.username, "db_id": user.id}
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
        """
        clean_user = username.strip().lower() if username else ""
        if not clean_user or not password:
            return False, None, None, "Username and password are required"

        if role not in ["staff", "manager", "admin"]:
            role = "staff"

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
                role=role
            )
            db.add(new_user)
            db.commit()
            db.refresh(new_user)

            user_id_str = f"usr_{role}_{new_user.id:03d}"
            token = jwt_handler.create_token(user_id=user_id_str, role=role)
            permissions = rbac_manager.get_permissions(role)

            user_info = {
                "user_id": user_id_str,
                "db_id": new_user.id,
                "username": new_user.username,
                "name": new_user.name,
                "role": role,
                "email": new_user.email,
                "permissions": permissions
            }

            audit_logger.log_event(
                event_type="LOGIN_SUCCESS",
                severity="INFO",
                user_id=user_id_str,
                role=role,
                details={"username": clean_user, "action": "registered_in_db"}
            )

            return True, token, user_info, "Registration successful"
        except Exception as e:
            db.rollback()
            return False, None, None, f"Database error during registration: {e}"
        finally:
            db.close()

    def get_user_profile(self, user_id_or_username: str) -> Optional[Dict]:
        """Fetch user profile from SQLite database."""
        db = SessionLocal()
        try:
            # Match by username or parsed ID
            user = db.query(User).filter(User.username == user_id_or_username).first()
            if not user:
                return None

            return {
                "user_id": f"usr_{user.role}_{user.id:03d}",
                "db_id": user.id,
                "username": user.username,
                "name": user.name,
                "role": user.role,
                "email": user.email,
                "permissions": rbac_manager.get_permissions(user.role)
            }
        finally:
            db.close()

# Singleton instance
auth_service = AuthService()
