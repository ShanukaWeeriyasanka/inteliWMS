"""
Request identity for the query gateway and chat threads.

Tokens are verified only against settings.JWT_SECRET (the same secret used to
issue them in security/jwt_handler.py). Hard-coded fallback secrets were removed:
anyone who knew those strings could forge a token and read another user's threads.
"""
from dataclasses import dataclass
from typing import Any, Dict, Optional

import jwt

from backend.middleware.error_handler import UnauthorizedException
from config.settings import settings


from security.subscription import get_user_plan, normalize_plan


@dataclass(frozen=True)
class Identity:
    user_id: str
    role: str
    authenticated: bool
    plan: str = "starter"


ANONYMOUS = Identity(user_id="anonymous", role="staff", authenticated=False, plan="starter")


def verify_and_decode_token(token_str: str) -> Dict[str, Any]:
    """Validates a JWT against settings.JWT_SECRET (HS256)."""
    if not token_str or token_str == "invalid_token":
        raise UnauthorizedException("Invalid authentication token")
    try:
        return jwt.decode(token_str, settings.JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise UnauthorizedException("Authentication token has expired")
    except jwt.InvalidSignatureError:
        raise UnauthorizedException("Token signature verification failed")
    except jwt.PyJWTError as e:
        raise UnauthorizedException(f"Malformed or invalid token: {e}")


def bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    value = authorization.strip()
    if value.lower().startswith("bearer "):
        value = value[7:].strip()
    return value or None


def resolve_identity(body_token: Optional[str], authorization: Optional[str] = None) -> Identity:
    """
    Identity from the body token (legacy frontend payload) or the Authorization header.
    No token → anonymous; a bad token → 401.
    Subscription plan is securely looked up from the database.
    """
    token = body_token or bearer_token(authorization)
    if not token:
        return ANONYMOUS
    claims = verify_and_decode_token(token)
    user_id = claims.get("user_id") or claims.get("sub")
    if not user_id:
        raise UnauthorizedException("Token has no user identity")
    username = claims.get("username")
    plan = get_user_plan(str(user_id), username=str(username) if username else None)
    return Identity(user_id=str(user_id), role=str(claims.get("role", "staff")), authenticated=True, plan=plan)
