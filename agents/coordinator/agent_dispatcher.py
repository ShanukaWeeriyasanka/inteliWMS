from typing import Dict, Any
from sqlalchemy.orm import Session

from utils.logger import StructuredLogger
from mcp_servers.coordinator_client import coordinator_mcp_client
from agents.fulfillment.fulfillment_agent import fulfillment_agent
from agents.fulfillment.schemas import FulfillmentRequest

logger = StructuredLogger(__name__)

async def dispatch_to_agent(target_agent: str, context_payload: Dict[str, Any], db: Session) -> Dict[str, Any]:
    """
    Generalizes specialist-agent dispatch.
    Routes to the real async FulfillmentAgent or falls back to the CoordinatorMCPClient stubs
    for inventory and knowledge agents.
    """
    if target_agent == "fulfillment_agent":
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
        # Fallback to existing mock MCP client for KNOWLEDGE and INVENTORY
        return coordinator_mcp_client.call_agent(target_agent, context_payload)
