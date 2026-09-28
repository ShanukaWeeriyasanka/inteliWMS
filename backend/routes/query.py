"""
FastAPI route for Coordinator Agent Query Gateway (Task 3).
Orchestrates:
1. Security validation (JWT verification + prompt injection defense)
2. Intent classification and routing (Task 2)
3. MCP delegation to specialist agents (Task 3)
4. Standardized response formatting and audit metadata
"""
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from fastapi import APIRouter, Request, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field
import jwt

from sqlalchemy.orm import Session
from database.connection import get_db
from database.models import ConversationLog

from config.settings import settings
from utils.logger import StructuredLogger
from security.sanitizer import sanitize_input
from agents.coordinator.intent_classifier import intent_classifier
from agents.coordinator.router import decide_route, route_to_agent
from agents.coordinator.query_normalizer import normalize_query
from agents.coordinator.context_builder import build_context
from mcp_servers.coordinator_client import coordinator_mcp_client
from backend.middleware.error_handler import UnauthorizedException

from agents.coordinator.agent_dispatcher import dispatch_to_agent

logger = StructuredLogger(__name__)
router = APIRouter(tags=["Coordinator Query Gateway"])

class QueryRequest(BaseModel):
    token: Optional[str] = None
    message: Optional[str] = None
    query: Optional[str] = None

DOMAIN_TO_AGENT_MAP = {
    "INVENTORY": "inventory_agent",
    "FULFILLMENT": "fulfillment_agent",
    "KNOWLEDGE": "knowledge_agent"
}

def verify_and_decode_token(token_str: str) -> Dict[str, Any]:
    """
    Validates JWT token strictly against the single configured secret.
    SECURITY: Dev fallback secrets have been removed — only settings.JWT_SECRET is accepted.
    """
    if not token_str or token_str == "invalid_token":
        raise UnauthorizedException("Invalid authentication token")

    try:
        return jwt.decode(token_str, settings.JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise UnauthorizedException("Authentication token has expired")
    except jwt.InvalidSignatureError:
        raise UnauthorizedException("Token signature verification failed")
    except Exception as e:
        raise UnauthorizedException(f"Malformed or invalid token: {str(e)}")


def _persist_conversation_log(
    db: Session,
    user_id: str,
    user_role: str,
    message: str,
    agent_used: str,
    intent: str,
    response_text: str,
    latency_ms: int,
) -> None:
    """Background task: commit a conversation turn to the ConversationLog table."""
    try:
        log_entry = ConversationLog(
            user_id=user_id,
            role=user_role,
            message=message,
            agent_routed_to=agent_used,
            intent=intent,
            response=response_text,
            latency_ms=latency_ms,
        )
        db.add(log_entry)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.log_event("CONVERSATION_LOG_FAILED", {"error": str(exc)})

def classify_intent_with_fallback(clean_query: str) -> Dict[str, Any]:
    """Classifies user intent using IntentClassifier with local heuristic fallback."""
    try:
        decision = intent_classifier.classify(clean_query)
        if decision and decision.get("domain") in DOMAIN_TO_AGENT_MAP:
            return decision
    except Exception as e:
        logger.log_event("CLASSIFICATION_FALLBACK_TRIGGERED", {"error": str(e)})

    # Robust keyword fallback
    q_lower = clean_query.lower()
    if any(k in q_lower for k in ["stock", "inventory", "sku", "battery", "label", "aisle"]):
        return {
            "domain": "INVENTORY",
            "confidence": 0.92,
            "reasoning": "Classified as INVENTORY based on warehouse SKU and stock signals."
        }
    elif any(k in q_lower for k in ["order", "delay", "delayed", "track", "dispatch", "ship"]):
        return {
            "domain": "FULFILLMENT",
            "confidence": 0.94,
            "reasoning": "Classified as FULFILLMENT based on order tracking and dispatch signals."
        }
    else:
        return {
            "domain": "KNOWLEDGE",
            "confidence": 0.90,
            "reasoning": "Classified as KNOWLEDGE based on SOP, policy, and instructional signals."
        }

@router.post("/query")
async def handle_coordinator_query(payload: QueryRequest, request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Main Coordinator entry point.
    Receives user natural language query, enforces security, classifies intent,
    and delegates to specialist agents via MCP.
    """
    # 1. Resolve query text
    user_query = payload.message or payload.query or ""
    user_id = "anonymous"
    user_role = "staff"

    # 2. Token Validation (Task 1 interface)
    if payload.token:
        claims = verify_and_decode_token(payload.token)
        user_id = claims.get("user_id") or claims.get("sub") or "user_authenticated"
        user_role = claims.get("role", "staff")

    # 3. Prompt Injection Defense
    is_safe, sanitized_or_reason = sanitize_input(user_query)
    if not is_safe:
        logger.log_event("SECURITY_BLOCKED", {
            "user_id": user_id,
            "query": user_query,
            "reason": sanitized_or_reason
        })
        return {
            "status": "error",
            "error_code": "PROMPT_INJECTION_DETECTED",
            "message": sanitized_or_reason,
            "audit": {
                "user_id": user_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "path": request.url.path
            }
        }

    # 3.5. Query Normalization — convert broken English / vague inputs to clear queries
    #      Uses Gemini → Groq hybrid. Falls back to original on failure.
    clean_query = normalize_query(sanitized_or_reason)

    # 4. Intent Classification & Routing
    routing_decision = decide_route(clean_query)
    target_agent = routing_decision["target_agent"]
    domain = routing_decision["domain"]
    confidence = routing_decision["confidence"]

    # 4.5. Coordinator Direct Reply — meta/system questions answered without delegation
    if routing_decision.get("direct_response"):
        return {
            "status": "success",
            "agent_used": "coordinator",
            "response": routing_decision["direct_response"],
            "routing": routing_decision,
            "audit": {
                "user_id": user_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "routing_confidence": confidence,
                "domain": domain,
                "normalized_query": clean_query
            }
        }

    # 5. Context Builder & MCP Delegation
    context_payload = build_context(
        user_id=user_id,
        message=clean_query,
        intent=domain,
        role=user_role
    )

    t_start = time.monotonic()
    agent_result = await dispatch_to_agent(target_agent, context_payload, db)
    latency_ms = int((time.monotonic() - t_start) * 1000)

    # 6. Structured Response
    audit_meta = {
        "user_id": user_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "routing_confidence": confidence,
        "domain": domain,
        "original_query": user_query,
        "normalized_query": clean_query
    }

    response_text = agent_result.get("response", "")

    final_response = {
        "status": "success",
        "agent_used": target_agent,
        "response": response_text,
        "routing": routing_decision,
        "audit": audit_meta
    }
    
    if "fulfillment_details" in agent_result:
        final_response["fulfillment_details"] = agent_result["fulfillment_details"]

    if "inventory_details" in agent_result:
        final_response["inventory_details"] = agent_result["inventory_details"]

    # 7. Recommendation 3 — Persist conversation turn to audit log (background, non-blocking)
    background_tasks.add_task(
        _persist_conversation_log,
        db=db,
        user_id=user_id,
        user_role=user_role,
        message=clean_query,
        agent_used=target_agent,
        intent=domain,
        response_text=str(response_text),
        latency_ms=latency_ms,
    )

    return final_response
