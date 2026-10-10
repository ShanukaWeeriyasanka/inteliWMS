"""
FastAPI route for Coordinator Agent Query Gateway (Task 3).
Orchestrates:
1. Security validation (JWT verification + prompt injection defense)
2. Conversation threads (stable thread_id per conversation, owner-scoped history)
3. Intent classification and routing (Task 2), using the thread's context for follow-ups
4. MCP delegation to specialist agents (Task 3)
5. Standardized response formatting and audit metadata

Identifiers are kept separate: thread_id is the conversation (stable across messages),
request_id / trace_id identify this one HTTP request, and session_id is the browser tab
that receives Digital Twin map commands.
"""
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import anyio
from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from agents.coordinator.agent_dispatcher import dispatch_to_agent
from agents.coordinator.context_builder import build_context
from agents.coordinator.router import decide_route
from backend.auth import Identity, resolve_identity, verify_and_decode_token  # noqa: F401  (re-exported)
from backend.middleware.error_handler import AppError
from backend.threads.deps import get_thread_store
from backend.threads.errors import ThreadAuthRequired, ThreadNotFound
from backend.threads.schemas import InventoryThreadContext, ThreadContext
from backend.threads.store import ThreadStore
from backend.twin.sessions import twin_sessions
from config.settings import settings
from database.connection import get_db
from database.models import ChatThread
from security.sanitizer import EMPTY_QUERY_MESSAGE, is_empty_query, sanitize_input
from utils import request_context
from utils.logger import StructuredLogger
from utils.decisions import RULE, collected, record_decision, start_collecting, stop_collecting
from utils.metrics import AGENT_DURATION, AGENT_REQUESTS, THREAD_OPERATIONS
from utils.tracing import span

logger = StructuredLogger(__name__)
router = APIRouter(tags=["Coordinator Query Gateway"])

BLOCKED_PLACEHOLDER = "[message blocked by the security filter]"


class QueryRequest(BaseModel):
    inventory_scope: Optional[str] = Field(None, pattern=r'^WH\d+(?:-F\d+)?(?:-Z\d{2})?(?:-R\d{2})?(?:-S\d{2})?(?:-B\d{2})?$')
    token: Optional[str] = None
    message: Optional[str] = Field(None, max_length=settings.CHAT_MAX_MESSAGE_CHARS)
    query: Optional[str] = Field(None, max_length=settings.CHAT_MAX_MESSAGE_CHARS)
    session_id: Optional[str] = Field(None, max_length=128,
                                      description="Browser session for Digital Twin map commands (not the conversation)")
    thread_id: Optional[str] = Field(None, max_length=64,
                                     description="Conversation id from a previous response; omit to start a new one")


def _ids() -> Dict[str, Optional[str]]:
    ids = request_context.current()
    return {"request_id": ids.get("request_id"), "trace_id": ids.get("trace_id")}


def _persist(store: ThreadStore, thread: Optional[ChatThread], identity: Identity, *, title: str,
             user_text: str, assistant_text: str, agent_used: Optional[str], status: str,
             meta: Optional[Dict[str, Any]], context: ThreadContext) -> Tuple[bool, Optional[str]]:
    """Save the exchange to the conversation (creating it on the first message). Returns (persisted, thread_id)."""
    if not identity.authenticated:
        return False, None
    is_new = thread is None
    try:
        if is_new:
            thread = store.create(identity.user_id, title=title)
        store.append_exchange(thread, user_text=user_text, assistant_text=assistant_text or "",
                              agent_used=agent_used, status=status, request_id=request_context.get("request_id"),
                              meta=meta, context=context)
        return True, thread.id
    except ThreadNotFound:
        # Deleted (e.g. "clear history" in another tab) while this request was running
        logger.log_event("THREAD_PERSIST_FAILED", {"reason": "thread_deleted"}, level="WARNING")
        return False, None
    except Exception as exc:
        THREAD_OPERATIONS.inc(op="persist", outcome="error")
        logger.log_event("THREAD_PERSIST_FAILED", {"reason": "db_error", "error_type": type(exc).__name__},
                         level="ERROR")
        return False, (None if is_new else thread.id)


def _message_meta(body: Dict[str, Any]) -> Dict[str, Any]:
    """What the UI needs to re-render an assistant message from history."""
    routing = body.get("routing") or {}
    meta = {
        "agent_used": body.get("agent_used"),
        "status": body.get("status"),
        "routing": {k: routing.get(k) for k in ("target_agent", "domain", "confidence", "reasoning", "source",
                                                "follow_up", "rule_id", "decided_by", "llm_consulted",
                                                "llm_status", "decisions") if k in routing},
    }
    for key in ("inventory_details", "fulfillment_details", "ui_command", "error_code"):
        if body.get(key) is not None:
            meta[key] = body[key]
    return meta


def _next_context(ctx: ThreadContext, domain: str, target_agent: str, agent_result: Dict[str, Any]) -> ThreadContext:
    nxt = ctx.model_copy(deep=True)
    nxt.turn_count += 1
    nxt.last_domain = domain
    nxt.last_agent = target_agent
    update = agent_result.get("context_update") if target_agent == "inventory_agent" else None
    if update is not None:
        try:
            nxt.inventory = InventoryThreadContext.model_validate(update)
        except ValidationError:
            logger.log_event("THREAD_CONTEXT_UPDATE_REJECTED", {"agent": target_agent}, level="WARNING")
            nxt.inventory.pending_clarification = None
    else:
        # A clarification offer is only valid for the very next message
        nxt.inventory.pending_clarification = None
    return nxt


@router.post("/query")
async def handle_coordinator_query(payload: QueryRequest, request: Request, db: Session = Depends(get_db),
                                   store: ThreadStore = Depends(get_thread_store),
                                   authorization: Optional[str] = Header(None)):
    """
    Main Coordinator entry point.
    Receives user natural language query, enforces security, resolves the conversation thread,
    classifies intent (with the thread's context), and delegates to specialist agents via MCP.
    """
    tokens = []
    decision_token = start_collecting()  # every decision of this request: routing.decisions in the response
    try:
        with span("query.handle") as sp:
            # 1. Resolve query text and identity (body token for the legacy payload, or Authorization header).
            #    Warehouse data is only answered for signed-in users.
            user_query = payload.message or payload.query or ""
            identity = resolve_identity(payload.token, authorization)
            if not identity.authenticated:
                if payload.thread_id is not None:
                    THREAD_OPERATIONS.inc(op="lookup", outcome="unauthenticated")
                    raise ThreadAuthRequired()
                raise AppError(401, "AUTH_REQUIRED", "Sign in to ask the warehouse coordinator")
            user_id, user_role = identity.user_id, identity.role
            # The map session (browser tab) must belong to this user: nobody may push commands onto another map
            if payload.session_id and not twin_sessions.claim(payload.session_id, user_id):
                raise AppError(403, "TWIN_SESSION_FORBIDDEN", "This map session belongs to another user")

            # 2. Conversation thread: reuse the one the client sent, or start a new one on first save
            thread: Optional[ChatThread] = None
            if payload.thread_id is not None:
                if not identity.authenticated:
                    THREAD_OPERATIONS.inc(op="lookup", outcome="unauthenticated")
                    raise ThreadAuthRequired()
                thread_id = store.parse_thread_id(payload.thread_id)
                tokens = request_context.bind(thread_id=thread_id)
                thread = store.get_owned(thread_id, user_id)
            ctx = store.context(thread) if thread is not None else ThreadContext()
            history = store.recent_history(thread, settings.CHAT_HISTORY_CONTEXT_TURNS) if thread is not None else []
            sp.set(authenticated=identity.authenticated, new_thread=thread is None)

            # 2.5. Nothing to answer: a client error, not a security event (and nothing is saved)
            if is_empty_query(user_query):
                record_decision("input", "empty", RULE, "input.empty_query")
                return {
                    "status": "error",
                    "error_code": "EMPTY_QUERY",
                    "message": EMPTY_QUERY_MESSAGE,
                    "response": EMPTY_QUERY_MESSAGE,
                    "audit": {"user_id": user_id, "timestamp": datetime.now(timezone.utc).isoformat(),
                              "path": request.url.path, **_ids()},
                    "routing": {"rule_id": "input.empty_query", "decided_by": RULE, "decisions": collected()},
                    "thread_id": thread.id if thread is not None else None,
                    "persisted": False,
                    **_ids(),
                }

            # 3. Prompt Injection Defense
            is_safe, sanitized_or_reason = sanitize_input(user_query)
            if not is_safe:
                record_decision("security", "blocked", RULE, "security.prompt_injection")
                logger.log_event("SECURITY_BLOCKED", {
                    "user_id": user_id,
                    "query": user_query,
                    "reason": sanitized_or_reason
                })
                body = {
                    "status": "error",
                    "error_code": "PROMPT_INJECTION_DETECTED",
                    "message": sanitized_or_reason,
                    "audit": {
                        "user_id": user_id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "path": request.url.path,
                        **_ids(),
                    },
                    "routing": {"rule_id": "security.prompt_injection", "decided_by": RULE,
                                "decisions": collected()},
                }
                blocked_ctx = ctx.model_copy(deep=True)
                blocked_ctx.inventory.pending_clarification = None
                # The blocked text itself is never stored: history is fed back to the LLM classifier
                persisted, tid = _persist(store, thread, identity, title="Blocked message",
                                          user_text=BLOCKED_PLACEHOLDER, assistant_text=sanitized_or_reason,
                                          agent_used="coordinator", status="blocked",
                                          meta=_message_meta(body), context=blocked_ctx)
                body.update(thread_id=tid, persisted=persisted, **_ids())
                return body

            # 4. Routing: code rules decide on the original text; only when no rule applies does a
            #    guarded LLM rewrite / LLM suggestion get a turn (validated, with fixed fallbacks).
            #    Runs off the event loop because those LLM steps block. Thread context lets
            #    "where is it?" stay with inventory.
            routing_ctx = {**ctx.for_routing(), "history": history} if thread is not None else None
            routing_decision = await anyio.to_thread.run_sync(
                lambda: decide_route(sanitized_or_reason, context=routing_ctx))
            clean_query = routing_decision.get("normalized_query") or sanitized_or_reason
            target_agent = routing_decision["target_agent"]
            domain = routing_decision["domain"]
            confidence = routing_decision["confidence"]
            sp.set(domain=domain, target_agent=target_agent, rule_id=routing_decision.get("rule_id"),
                   decided_by=routing_decision.get("decided_by"))

            # 4.5. Coordinator Direct Reply — meta/system questions answered without delegation
            if routing_decision.get("direct_response"):
                routing_decision["decisions"] = collected()
                body = {
                    "status": "success",
                    "agent_used": "coordinator",
                    "response": routing_decision["direct_response"],
                    "routing": routing_decision,
                    "audit": {
                        "user_id": user_id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "routing_confidence": confidence,
                        "domain": domain,
                        "normalized_query": clean_query,
                        **_ids(),
                    }
                }
                direct_ctx = ctx.model_copy(deep=True)
                direct_ctx.turn_count += 1
                direct_ctx.inventory.pending_clarification = None
                persisted, tid = _persist(store, thread, identity, title=sanitized_or_reason,
                                          user_text=sanitized_or_reason, assistant_text=body["response"],
                                          agent_used="coordinator", status="success",
                                          meta=_message_meta(body), context=direct_ctx)
                body.update(thread_id=tid, persisted=persisted, **_ids())
                return body

            # 5. Context Builder & MCP Delegation (the conversation travels with the hand-off)
            if target_agent == 'inventory_agent' and thread is None and identity.authenticated:
                try:
                    thread = store.create(identity.user_id, title=sanitized_or_reason)
                    request_context.bind(thread_id=thread.id)
                except Exception as exc:
                    logger.log_event('THREAD_CREATE_BEFORE_HANDOFF_FAILED',
                                     {'error_type':type(exc).__name__}, level='WARNING')
            # Agents get the user's own wording; ids from an accepted rewrite are only hints
            context_payload = build_context(
                user_id=user_id,
                message=sanitized_or_reason,
                intent=domain,
                role=user_role,
                session_id=payload.session_id,
                thread_id=thread.id if thread is not None else None,
                conversation=ctx.inventory.model_dump() if domain == "INVENTORY" else None,
                entity_text=routing_decision.get("normalized_query"),
                inventory_scope=payload.inventory_scope if domain == 'INVENTORY' else None,
            )

            dispatch_start = time.perf_counter()
            with span("agent.dispatch", agent=target_agent) as dsp:
                agent_result = await dispatch_to_agent(target_agent, context_payload, db)
                dsp.set(status="error" if agent_result.get("status") == "error" else "ok")
            if target_agent != "inventory_agent":  # the inventory hand-off records its own outcome
                AGENT_REQUESTS.inc(agent=target_agent, outcome=agent_result.get("status", "success"))
                AGENT_DURATION.observe(time.perf_counter() - dispatch_start, agent=target_agent)

            # 6. Structured Response
            audit_meta = {
                "user_id": user_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "routing_confidence": confidence,
                "domain": domain,
                "original_query": user_query,
                "normalized_query": clean_query,
                **_ids(),
            }

            final_response = {
                "status": agent_result.get("status", "success"),
                "agent_used": target_agent,
                "response": agent_result.get("response"),
                "routing": routing_decision,
                "audit": audit_meta
            }
            if agent_result.get("error_code"):
                final_response["error_code"] = agent_result["error_code"]

            if "fulfillment_details" in agent_result:
                final_response["fulfillment_details"] = agent_result["fulfillment_details"]

            if "inventory_details" in agent_result:
                final_response["inventory_details"] = agent_result["inventory_details"]
                # Digital Twin map command (only inventory answers drive the map)
                ui_payload = agent_result["inventory_details"].get("ui_command")
                if ui_payload:
                    final_response["ui_command"] = {
                        "id": agent_result["inventory_details"].get("ui_command_id"),
                        "session_id": payload.session_id,
                        "payload": ui_payload,
                    }

            routing_decision["decisions"] = collected()  # routing + the agent's own decisions

            # 7. Save the exchange to the conversation and carry its context forward
            persisted, tid = _persist(store, thread, identity, title=sanitized_or_reason,
                                      user_text=sanitized_or_reason, assistant_text=final_response["response"],
                                      agent_used=target_agent, status=final_response["status"],
                                      meta=_message_meta(final_response),
                                      context=_next_context(ctx, domain, target_agent, agent_result))
            final_response.update(thread_id=tid, persisted=persisted, **_ids())
            sp.set(status="error" if final_response["status"] == "error" else "ok", persisted=persisted)
            logger.log_event("QUERY_COMPLETED", {
                "agent": target_agent, "domain": domain, "status": final_response["status"],
                "persisted": persisted, "new_thread": thread is None and persisted,
            })
            return final_response
    finally:
        stop_collecting(decision_token)
        request_context.reset(tokens)
