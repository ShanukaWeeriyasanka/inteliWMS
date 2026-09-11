"""
MCP Client for Coordinator Agent delegation.
Orchestrates communication with specialist sub-agents:
- inventory_agent
- fulfillment_agent
- knowledge_agent
"""
import time
from typing import Dict, Any
from utils.logger import StructuredLogger

logger = StructuredLogger(__name__)

class AgentTimeoutException(Exception):
    """Raised when an agent does not respond within the timeout window."""
    pass

class UnknownAgentException(Exception):
    """Raised when delegation targets an unrecognized agent."""
    pass

class CoordinatorMCPClient:
    """
    Client for delegating sub-tasks from Coordinator to specialist agents via MCP.
    Currently includes robust mock/stub implementations for Inventory, Fulfillment,
    and Knowledge agents with warehouse operational logic.
    """

    SUPPORTED_AGENTS = {
        "inventory_agent": "Manages SKU stock levels, bay locations, and replenishment",
        "fulfillment_agent": "Manages order dispatch, tracking, pick-pack status, and delays",
        "knowledge_agent": "Answers warehouse SOPs, safety protocols, and operational guides"
    }

    def __init__(self, timeout_seconds: float = 5.0):
        self.timeout_seconds = timeout_seconds

    def call_agent(self, agent_name: str, context_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Invokes target specialist agent with context payload.
        
        Args:
            agent_name: Target agent (inventory_agent | fulfillment_agent | knowledge_agent)
            context_payload: Dict containing query, user info, session context
            
        Returns:
            Dict containing agent response, agent_used, and metadata
        """
        start_time = time.time()
        query = context_payload.get("query", "").lower()
        user_id = context_payload.get("user_id", "anonymous")

        logger.log_event("MCP_DELEGATION_START", {
            "target_agent": agent_name,
            "user_id": user_id,
            "query_preview": query[:60]
        })

        if agent_name not in self.SUPPORTED_AGENTS:
            err_msg = f"Target agent '{agent_name}' is not recognized. Supported agents: {list(self.SUPPORTED_AGENTS.keys())}"
            logger.log_event("MCP_UNKNOWN_AGENT", {"agent_name": agent_name})
            raise UnknownAgentException(err_msg)

        try:
            # Dispatch to agent handler
            if agent_name == "inventory_agent":
                response_text = self._handle_inventory_query(query, context_payload)
            elif agent_name == "fulfillment_agent":
                response_text = self._handle_fulfillment_query(query, context_payload)
            elif agent_name == "knowledge_agent":
                response_text = self._handle_knowledge_query(query, context_payload)
            else:
                response_text = f"Agent '{agent_name}' processed request successfully."

            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            logger.log_event("MCP_DELEGATION_SUCCESS", {
                "target_agent": agent_name,
                "elapsed_ms": elapsed_ms
            })

            return {
                "status": "success",
                "agent_used": agent_name,
                "response": response_text,
                "execution_time_ms": elapsed_ms
            }

        except Exception as e:
            logger.log_event("MCP_DELEGATION_ERROR", {
                "target_agent": agent_name,
                "error": str(e)
            })
            raise

    def _handle_inventory_query(self, query: str, context: Dict[str, Any]) -> str:
        """Mock inventory specialist agent logic."""
        if "4521" in query or "battery" in query:
            return (
                "SKU-4521 (Heavy Duty Forklift Battery Lithium) is currently located at "
                "Aisle 4, Bay B-12. Current stock: 42 units on hand, 8 reserved for pending dispatches. "
                "Minimum safety threshold: 25 units."
            )
        if "1088" in query or "label" in query:
            return (
                "SKU-1088 (Thermal Industrial Label Rolls) is at Aisle 1, Bay A-03. "
                "Current stock: 120 rolls on hand. Reorder point: 50 rolls."
            )
        return (
            "Inventory Agent: Verified SKU location and availability across regional fulfillment center. "
            "All items checked are within normal operational stocking thresholds."
        )

    def _handle_fulfillment_query(self, query: str, context: Dict[str, Any]) -> str:
        """Mock fulfillment specialist agent logic."""
        if "4521" in query or "delay" in query:
            return (
                "Order #4521 Status: Currently in 'Pick In-Progress' at Station 3. "
                "Slight delay observed due to heavy machinery transit in Zone B. "
                "Estimated dispatch time updated to 14:45 UTC."
            )
        if "track" in query or "order" in query:
            return (
                "Fulfillment Agent: Order retrieved from Active Dispatch Queue. "
                "Items packaged, QA inspection passed, awaiting courier pickup at Dock Door 4."
            )
        return (
            "Fulfillment Agent: Order routing and packing telemetry verified. "
            "On-time fulfillment rate currently stands at 99.2% for this shift."
        )

    def _handle_knowledge_query(self, query: str, context: Dict[str, Any]) -> str:
        """Invokes real Knowledge Agent (calls execute_knowledge_query with local fallback)."""
        try:
            from agents.knowledge_agent.agent import execute_knowledge_query
            user_role = context.get("role") or context.get("user_role") or "staff"
            res = execute_knowledge_query(query, user_role=user_role, context=context)
            if res and res.get("response"):
                return res["response"]
        except Exception as e:
            logger.log_event("KNOWLEDGE_INTEGRATION_ERROR", {"error": str(e)})

        return (
            "Knowledge Agent: Consulted InteliWMS Operational Manual v2.4. "
            "Standard floor procedures apply. Contact shift supervisor for specialized exception handling."
        )

# Global singleton
coordinator_mcp_client = CoordinatorMCPClient()
