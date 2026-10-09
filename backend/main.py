"""
IntelliWMS API Gateway - Coordinator Agent Entrypoint.
Orchestrates:
- Task 1: Security & JWT Validation, Database Auth & RBAC
- Task 2: Intent Classification & Routing
- Task 3: API Gateway & MCP Delegation
"""
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional
from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware

from config.settings import settings
from utils.logger import StructuredLogger
from security.sanitizer import sanitize_input, sanitizer
from security.jwt_handler import jwt_handler
from security.rbac import rbac_manager, PERMISSION_MATRIX
from security.auth import auth_service, ROLE_RANK, SELF_REGISTER_ROLES, SELF_REGISTER_DENIED
from security.audit_logger import audit_logger
from backend.routes.query import router as query_router
from backend.routes.metrics import router as metrics_router
from backend.threads.routes import router as threads_router
from backend.middleware.error_handler import register_error_handlers
from backend.middleware.request_context import RequestContextMiddleware
from mcp_servers.mcp_tool_client import inventory_tool_gateway
from backend.twin.routes import router as twin_router
from backend.twin.realtime import twin_broker
from database.twin import ensure_twin_schema, is_enabled as twin_is_enabled

logger = StructuredLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Warehouse Digital Twin: create + seed the `twin` schema on first start (PostgreSQL only)
    if settings.TWIN_AUTO_SETUP and twin_is_enabled():
        try:
            ensure_twin_schema()
        except Exception as e:
            logger.log_event("TWIN_SETUP_FAILED", {"error": str(e)})
    # Inventory MCP connection settings (no secrets); problems are named exactly
    mcp_config = inventory_tool_gateway.describe()
    logger.log_event("INVENTORY_MCP_CONFIG", mcp_config, level="INFO" if mcp_config["configured"] else "ERROR")
    if settings.JWT_SECRET == "dev-secret-minimum-32-characters-long":
        logger.log_event("JWT_SECRET_DEFAULT", {"message": "JWT_SECRET is the development default; set it in .env"},
                         level="WARNING")
    yield
    twin_broker.stop()


app = FastAPI(
    title="IntelliWMS API Gateway - Coordinator Agent",
    description="Intelligent Agentic Warehouse Management System (Task 1 Security & Task 3 API Gateway)",
    version="0.3.0",
    lifespan=lifespan
)

# Register Global Exception & Error Handlers (Task 3)
register_error_handlers(app)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Trace-ID"],
)

# Request / trace correlation ids for every request (added last = outermost)
app.add_middleware(RequestContextMiddleware)

# Helper function to extract user from Authorization header
def get_current_user(authorization: Optional[str] = Header(None)) -> Optional[dict]:
    if not authorization:
        return None
    if authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
    else:
        token = authorization
    try:
        payload = jwt_handler.decode_token(token)
        return payload
    except Exception:
        return None


def require_user(authorization: Optional[str]) -> Dict[str, Any]:
    """Token claims of the signed-in caller, or 401."""
    user = get_current_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def _text_field(payload: Dict[str, Any], key: str, default: str = "") -> str:
    """A login/register field that must be text (a number, list or null is a client error, not a 500)."""
    value = payload.get(key, default)
    if value is None:
        value = default
    if not isinstance(value, str):
        raise HTTPException(status_code=400, detail=f"'{key}' must be text")
    return value.strip()


def _role_field(payload: Dict[str, Any], default: Optional[str]) -> Optional[str]:
    role = _text_field(payload, "role", default or "").lower() or default
    if role is not None and role not in ROLE_RANK:
        raise HTTPException(status_code=400, detail=f"Unknown role '{role}'")
    return role

# ==================== Health Monitor ====================

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "message": "IntelliWMS API Gateway is running smoothly",
        "primary_llm": settings.LLM_PRIMARY,
        "security_layer": "Task 1 Active (JWT + RBAC + Sanitizer + Audit Logger)",
        "gateway_layer": "Task 3 Active (MCP Client + Global Error Handler)",
        "inventory_mcp": inventory_tool_gateway.describe(),
    }

# ==================== Task 1 Security & Auth Endpoints ====================

@app.post("/auth/login")
def login_endpoint(payload: dict):
    username = _text_field(payload, "username")
    password = _text_field(payload, "password")
    role = _role_field(payload, default=None)

    success, token, user_info, message = auth_service.authenticate(
        username=username,
        password=password,
        requested_role=role
    )
    
    if not success:
        raise HTTPException(status_code=401, detail=message)
        
    return {
        "status": "success",
        "message": message,
        "token": token,
        "user": user_info
    }

@app.post("/auth/register")
def register_endpoint(payload: dict):
    username = _text_field(payload, "username")
    password = _text_field(payload, "password")
    role = _role_field(payload, default="staff")
    name = _text_field(payload, "name") or None
    if role not in SELF_REGISTER_ROLES:
        raise HTTPException(status_code=403, detail=SELF_REGISTER_DENIED)

    success, token, user_info, message = auth_service.register(
        username=username,
        password=password,
        role=role,
        name=name
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
        
    return {
        "status": "success",
        "message": message,
        "token": token,
        "user": user_info
    }

@app.get("/auth/me")
def get_profile(authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or missing authentication token")

    # The role the token was issued for (a user may sign in with a lower role than their own)
    role = user.get("role", "staff")
    profile = auth_service.get_user_profile(str(user.get("user_id") or "")) or {}
    return {
        "user_id": user.get("user_id"),
        "db_id": profile.get("db_id"),
        "username": profile.get("username"),
        "name": profile.get("name"),
        "email": profile.get("email"),
        "role": role,
        "permissions": rbac_manager.get_permissions(role),
        "exp": user.get("exp"),
        "iat": user.get("iat")
    }

@app.post("/security/execute-action")
def execute_role_action(payload: dict, authorization: Optional[str] = Header(None)):
    action = payload.get("action", "")
    user = require_user(authorization)

    role = user.get("role", "staff")
    user_id = user.get("user_id", "unknown")

    try:
        rbac_manager.require_permission(role, action, user_id=user_id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    return {
        "status": "allowed",
        "action": action,
        "role": role,
        "message": f"Success: Action '{action}' authorized for role '{role}'."
    }

@app.get("/security/rbac-matrix")
def get_rbac_matrix(authorization: Optional[str] = Header(None)):
    require_user(authorization)
    return {
        "status": "success",
        "matrix": PERMISSION_MATRIX
    }

@app.post("/security/test-injection")
def test_injection(payload: dict, authorization: Optional[str] = Header(None)):
    require_user(authorization)
    text = payload.get("text", "")
    if not isinstance(text, str):
        raise HTTPException(status_code=400, detail="'text' must be text")
    is_injection, reason = sanitizer.is_injection_attempt(text)
    cleaned, is_safe = sanitizer.sanitize_input(text)
    
    return {
        "input_text": text,
        "is_injection": is_injection,
        "reason": reason,
        "cleaned_text": cleaned,
        "is_safe": is_safe
    }

@app.post("/security/test-permission")
def test_permission(payload: dict, authorization: Optional[str] = Header(None)):
    require_user(authorization)
    role = payload.get("role", "staff")
    action = payload.get("action", "")
    is_allowed = rbac_manager.check_permission(role, action)
    allowed_actions = rbac_manager.get_permissions(role)
    
    return {
        "role": role,
        "action": action,
        "allowed": is_allowed,
        "allowed_actions": allowed_actions
    }

@app.get("/security/audit-logs")
def get_audit_logs(limit: int = Query(50, ge=1, le=500), event_type: Optional[str] = None,
                   authorization: Optional[str] = Header(None)):
    # Audit entries name users and their failed sign-ins: managers and admins only
    user = require_user(authorization)
    try:
        rbac_manager.require_permission(user.get("role", "staff"), "view_audit_logs", user_id=user.get("user_id"))
    except PermissionError:
        raise HTTPException(status_code=403, detail="The security audit log is available to managers and admins.")
    return {
        "status": "success",
        "stats": audit_logger.get_summary_stats(),
        "logs": audit_logger.get_logs(limit=limit, event_type=event_type)
    }

# ==================== Task 3 API Gateway & MCP Query Route ====================

app.include_router(query_router)

# ==================== Conversation threads & observability ====================

app.include_router(threads_router)
app.include_router(metrics_router)

# ==================== Warehouse Digital Twin (map, routes, live updates) ====================

app.include_router(twin_router)

if __name__ == "__main__":
    import uvicorn
    # The twin map keeps a live stream open; without a limit a reload waits for it forever
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True, timeout_graceful_shutdown=3)
