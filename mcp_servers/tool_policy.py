"""
Per-agent tool allowlists, enforced by the MCP tool gateway (mcp_servers/mcp_tool_client.py).

An agent can only see and call the tools listed for it here. Tools discovered
from an MCP server that are not registered below are never exposed to anyone,
and an unknown agent gets nothing. READ tools may be retried on transient
failures; MUTATION tools are never retried.
"""
from enum import Enum
from typing import Dict, FrozenSet, Optional, Tuple

from agents.inventory_agent import tool_contracts as inv


class ToolKind(str, Enum):
    READ = "read"
    MUTATION = "mutation"


# Every tool the gateway knows about, by MCP tool name
TOOL_REGISTRY: Dict[str, ToolKind] = {
    inv.QUERY_INVENTORY: ToolKind.READ,
    inv.GET_PRODUCT_STOCK: ToolKind.READ,
    inv.SEARCH_PRODUCTS: ToolKind.READ,
    inv.LIST_LOW_STOCK: ToolKind.READ,
    inv.GET_STOCK_MOVEMENTS: ToolKind.READ,
    inv.PREDICT_DEPLETION: ToolKind.READ,
    inv.CHECK_STOCK_ANOMALIES: ToolKind.READ,
    inv.EVALUATE_TRANSFER: ToolKind.READ,
    inv.PARSE_SUPPLIER_DOCUMENT: ToolKind.READ,
    inv.ANALYZE_EQUIPMENT_LOG: ToolKind.READ,
    inv.TWIN_ANSWER: ToolKind.READ,
    inv.PUBLISH_MAP_COMMAND: ToolKind.MUTATION,
}

INVENTORY_READ_TOOLS: FrozenSet[str] = frozenset(n for n, k in TOOL_REGISTRY.items() if k is ToolKind.READ)

AGENT_TOOL_ALLOWLISTS: Dict[str, FrozenSet[str]] = {
    # Classifies and delegates; reads no warehouse data itself
    "coordinator": frozenset(),
    # Stock, availability, locations, low stock, movements, forecasts, transfers, documents,
    # equipment logs and map answers (read) + storing a map command for the user's browser (mutation)
    "inventory_agent": INVENTORY_READ_TOOLS | {inv.PUBLISH_MAP_COMMAND},
    # Checks stock by handing off to inventory_agent through the dispatcher, not by calling tools
    "fulfillment_agent": frozenset(),
}

# Documentation only: the knowledge agent calls its own CrewAI tools in-process
# (agents/knowledge_agent/agent.py); it is not given any MCP tools.
DECLARED_IN_PROCESS_TOOLS: Dict[str, Tuple[str, ...]] = {
    "knowledge_agent": (
        "lookup_warehouse_location",
        "search_warehouse_knowledge_rag",
        "extract_warehouse_entities_tool",
        "get_shift_handoff_summary",
        "log_shift_handoff_note",
        "check_warehouse_compliance_tool",
        "triage_customer_return_tool",
    ),
}


def is_allowed(agent: str, tool: str) -> bool:
    return tool in TOOL_REGISTRY and tool in AGENT_TOOL_ALLOWLISTS.get(agent, frozenset())


def kind_of(tool: str) -> Optional[ToolKind]:
    return TOOL_REGISTRY.get(tool)


def allowed_tools(agent: str) -> FrozenSet[str]:
    return AGENT_TOOL_ALLOWLISTS.get(agent, frozenset())
