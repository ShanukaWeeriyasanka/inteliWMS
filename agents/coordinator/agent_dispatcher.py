from typing import Dict, Any
from sqlalchemy.orm import Session

from utils.logger import StructuredLogger
from mcp_servers.coordinator_client import coordinator_mcp_client
from agents.fulfillment.fulfillment_agent import fulfillment_agent
from agents.fulfillment.schemas import FulfillmentRequest

logger = StructuredLogger(__name__)

async def dispatch_to_agent(target_agent: str, context_payload: Dict[str, Any], db: Session) -> Dict[str, Any]:
    """
    Dispatches to specialist agents.

    Routing:
      - inventory_agent  → Real InventoryAgent (DB-backed, alias-aware)
      - fulfillment_agent → Real async FulfillmentAgent (DB-backed)
      - knowledge_agent  → Real KnowledgeAgent via MCP client
    """
    if target_agent == "inventory_agent":
        try:
            from agents.inventory_agent.agent import handle_inventory_query
            sku = context_payload.get("extracted_sku")
            user_role = context_payload.get("user_role") or "staff"
            original_query = context_payload.get("original_message") or context_payload.get("query", "")
            resp = handle_inventory_query(original_query, sku=sku, user_role=user_role, db=db)
            return {
                "status": "success",
                "agent_used": target_agent,
                "response": resp.get("response", ""),
                "inventory_details": {
                    "items": resp.get("items", []),
                    "needs_reorder": resp.get("needs_reorder", False),
                    "source": resp.get("source", "database"),
                }
            }
        except Exception as e:
            logger.log_event("INVENTORY_DISPATCH_ERROR", {"error": str(e), "context": context_payload})
            return {
                "status": "success",
                "agent_used": target_agent,
                "response": "Unable to retrieve inventory data at this time. Please try again.",
                "inventory_details": {"items": [], "needs_reorder": False, "source": "error"}
            }

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
