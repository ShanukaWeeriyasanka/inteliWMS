import time
from typing import Dict, Any

import anyio
from sqlalchemy.orm import Session

from utils import request_context
from utils.logger import StructuredLogger
from utils.metrics import AGENT_DURATION, AGENT_REQUESTS
from mcp_servers.coordinator_client import coordinator_mcp_client
from agents.fulfillment.fulfillment_agent import fulfillment_agent
from agents.fulfillment.schemas import FulfillmentRequest

logger = StructuredLogger(__name__)

INVENTORY_UNREACHABLE = "⚠️ Inventory data could not be retrieved right now, so no stock figures are shown. Please try again."


async def _dispatch_inventory(context_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Hand off to the Inventory Agent (async, MCP-backed) under the agent timeout.
    The agent's own outcome decides the status, so a failed lookup is never reported as success.
    """
    from agents.inventory_agent.agent import handle_inventory_query_async
    from agents.inventory_agent.config import inventory_config

    agent = "inventory_agent"
    tokens = request_context.bind(agent=agent)
    start = time.perf_counter()
    logger.log_event("INVENTORY_HANDOFF", {
        "has_thread": bool(context_payload.get("thread_id")),
        "has_sku": bool(context_payload.get("extracted_sku")),
        "has_conversation": bool(context_payload.get("conversation")),
    })
    try:
        with anyio.fail_after(inventory_config.REQUEST_TIMEOUT_SECONDS):
            resp = await handle_inventory_query_async(
                context_payload.get("original_message") or context_payload.get("query", ""),
                sku=context_payload.get("extracted_sku"),
                user_role=context_payload.get("user_role") or "staff",
                session_id=context_payload.get("session_id"),
                thread_id=context_payload.get('thread_id'),
                conversation=context_payload.get("conversation"),
                inventory_scope=context_payload.get('inventory_scope'),
            )
    except Exception as e:  # TimeoutError, ExceptionGroup from MCP task groups, anything else (not cancellation)
        code = "INVENTORY_TIMEOUT" if isinstance(e, TimeoutError) else "INVENTORY_AGENT_ERROR"
        AGENT_REQUESTS.inc(agent=agent, outcome="error")
        AGENT_DURATION.observe(time.perf_counter() - start, agent=agent)
        logger.log_event("INVENTORY_DISPATCH_ERROR", {"agent": agent, "error_code": code,
                                                      "error_type": type(e).__name__}, level="ERROR")
        return {
            "status": "error",
            "agent_used": agent,
            "error_code": code,
            "response": INVENTORY_UNREACHABLE,
            "inventory_details": {"items": [], "needs_reorder": False, "source": "error",
                                  "outcome": "error", "error_code": code},
        }
    finally:
        request_context.reset(tokens)

    outcome = resp.get("outcome", "answered")
    AGENT_REQUESTS.inc(agent=agent, outcome=outcome)
    AGENT_DURATION.observe(time.perf_counter() - start, agent=agent)
    return {
        "status": "error" if outcome == "error" else "success",
        "agent_used": agent,
        "response": resp.get("response", ""),
        "error_code": resp.get("error_code"),
        "context_update": resp.get("context_update"),
        "inventory_details": {
            "sub_intent": resp.get("sub_intent", "stock_check"),
            "items": resp.get("items", []),
            "needs_reorder": resp.get("needs_reorder", False),
            "source": resp.get("source", "database"),
            "document_result": resp.get("document_result"),
            "prediction_result": resp.get("prediction_result"),
            "anomaly_result": resp.get("anomaly_result"),
            "transfer_result": resp.get("transfer_result"),
            "equipment_health_result": resp.get("equipment_health_result"),
            "warehouse_layout": resp.get("warehouse_layout"),
            "ui_command": resp.get("ui_command"),
            "ui_command_id": resp.get("ui_command_id"),
            "outcome": outcome,
            "error_code": resp.get("error_code"),
            "clarification": resp.get("clarification"),
            "execution_time_ms": resp.get("execution_time_ms")
        }
    }

async def dispatch_to_agent(target_agent: str, context_payload: Dict[str, Any], db: Session) -> Dict[str, Any]:
    """
    Dispatches to specialist agents.

    Routing:
      - inventory_agent  → Real InventoryAgent (DB-backed, alias-aware)
      - fulfillment_agent → Real async FulfillmentAgent (DB-backed)
      - knowledge_agent  → Real KnowledgeAgent via MCP client
    """
    if target_agent == "inventory_agent":
        return await _dispatch_inventory(context_payload)

    elif target_agent == "fulfillment_agent":
        try:
            f_req = FulfillmentRequest(
                query=context_payload.get("query", ""),
                user_id=context_payload.get("user_id"),
                role=context_payload.get("user_role"),
                order_id=context_payload.get("extracted_order_id")
            )
            f_resp = await fulfillment_agent.handle(f_req, db)
            
            return {
                "status": "success",
                "agent_used": target_agent,
                "response": f_resp.message,
                "fulfillment_details": {
                    "success": f_resp.success,
                    "intent": f_resp.intent.value if f_resp.intent else None,
                    "order_id": f_resp.order_id
                }
            }
        except Exception as e:
            logger.log_event("FULFILLMENT_DISPATCH_ERROR", {"error": str(e), "context": context_payload})
            return {
                "status": "success",
                "agent_used": target_agent,
                "response": "Unable to process the fulfillment request at this time.",
                "fulfillment_details": {
                    "success": False,
                    "intent": None,
                    "order_id": context_payload.get("extracted_order_id")
                }
            }

    else:
        # knowledge_agent → real Knowledge Agent via MCP client
        return coordinator_mcp_client.call_agent(target_agent, context_payload)
