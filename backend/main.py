from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from config.settings import settings
from utils.logger import StructuredLogger
from security.sanitizer import sanitize_input, sanitizer
from security.jwt_handler import jwt_handler
from security.rbac import rbac_manager, PERMISSION_MATRIX
from security.auth import auth_service
from security.audit_logger import audit_logger
from agents.coordinator.intent_classifier import intent_classifier

app = FastAPI(
    title="IntelliWMS API - Task 1 Security & Authentication",
    description="Intelligent Agentic Warehouse Management System",
    version="0.2.0"
)

logger = StructuredLogger(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "message": "IntelliWMS backend is running smoothly",
        "primary_llm": settings.LLM_PRIMARY,
        "security_layer": "Task 1 Active (JWT + RBAC + Sanitizer + Audit Logger)"
    }

# ==================== Task 1 Security & Auth Endpoints ====================

@app.post("/auth/login")
def login_endpoint(payload: dict):
    username = payload.get("username", "").strip()
    password = payload.get("password", "").strip()
    role = payload.get("role")
    
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
    username = payload.get("username", "").strip()
    password = payload.get("password", "").strip()
    role = payload.get("role", "staff")
    name = payload.get("name")
    
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

@app.post("/security/execute-action")
def execute_role_action(payload: dict, authorization: Optional[str] = Header(None)):
    action = payload.get("action", "")
    user = get_current_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
        
    role = user.get("role", "staff")
    user_id = user.get("user_id", "unknown")
    
    try:
        rbac_manager.require_permission(role, action, user_id=user_id)
        return {
            "status": "allowed",
            "action": action,
            "role": role,
            "message": f"Success: Action '{action}' authorized for role '{role}'."
        }
    except PermissionError as e:
        return {
            "status": "denied",
            "action": action,
            "role": role,
            "message": str(e)
        }

@app.get("/auth/me")
def get_profile(authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or missing authentication token")
    
    role = user.get("role", "staff")
    permissions = rbac_manager.get_permissions(role)
    
    return {
        "user_id": user.get("user_id"),
        "role": role,
        "permissions": permissions,
        "exp": user.get("exp"),
        "iat": user.get("iat")
    }

@app.get("/security/rbac-matrix")
def get_rbac_matrix():
    return {
        "status": "success",
        "matrix": PERMISSION_MATRIX
    }

@app.post("/security/test-injection")
def test_injection(payload: dict):
    text = payload.get("text", "")
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
def test_permission(payload: dict):
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
def get_audit_logs(limit: int = 50, event_type: Optional[str] = None):
    return {
        "status": "success",
        "stats": audit_logger.get_summary_stats(),
        "logs": audit_logger.get_logs(limit=limit, event_type=event_type)
    }

# ==================== Main Warehouse Query Endpoint ====================

@app.post("/query")
def query_endpoint(payload: dict, authorization: Optional[str] = Header(None)):
    user_query = payload.get("query", "")
    token = payload.get("token")
    
    # 1. Auth & Token Validation (if token provided)
    user_id = "anonymous"
    user_role = "staff"
    
    auth_header = authorization or (f"Bearer {token}" if token else None)
    if auth_header:
        user = get_current_user(auth_header)
        if user:
            user_id = user.get("user_id", "user")
            user_role = user.get("role", "staff")
    
    # 2. Security & Prompt Injection Check
    is_safe, sanitized_or_reason = sanitize_input(user_query, user_id=user_id, role=user_role)
    if not is_safe:
        logger.log_event("SECURITY_BLOCKED", {"query": user_query, "reason": sanitized_or_reason, "user_id": user_id})
        return {
            "status": "blocked",
            "message": sanitized_or_reason,
            "security": {
                "authenticated": bool(auth_header and user_id != "anonymous"),
                "user_id": user_id,
                "role": user_role,
                "is_safe": False
            },
            "decision": None
        }

    # Log successful sanitized query event
    audit_logger.log_event(
        event_type="REQUEST_SANITIZED",
        severity="INFO",
        user_id=user_id,
        role=user_role,
        details={"query_length": len(sanitized_or_reason)}
    )

    # 3. Intent Classification via Coordinator/Gemini
    decision = intent_classifier.classify(sanitized_or_reason)

    return {
        "status": "success",
        "query": sanitized_or_reason,
        "security": {
            "authenticated": bool(auth_header and user_id != "anonymous"),
            "user_id": user_id,
            "role": user_role,
            "is_safe": True
        },
        "routing": decision
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
