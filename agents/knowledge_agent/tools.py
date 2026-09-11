"""
CrewAI Tool Definitions for Knowledge Agent.
Wraps location lookup, vector RAG search, and entity extraction into agent tools.
"""
import json
try:
    from crewai.tools import tool
except ImportError:
    def tool(name):
        """Fallback decorator when crewai is not installed."""
        def decorator(func):
            func.__tool_name__ = name
            return func
        return decorator

from agents.knowledge_agent.location_resolver import resolve_location
from agents.knowledge_agent.knowledge_store import knowledge_store, seed_warehouse_sops
from agents.knowledge_agent.ner import extract_warehouse_entities
from agents.knowledge_agent.config import knowledge_config
from utils.logger import StructuredLogger
from agents.knowledge_agent.shift_handoff import (
    get_latest_shift_handoff,
    record_shift_handoff
)
from agents.knowledge_agent.compliance import (
    check_compliance,
    evaluate_compliance_query
)
from agents.knowledge_agent.returns_handler import (
    triage_returned_item,
    evaluate_return_query
)



logger = StructuredLogger(__name__)

# Ensure default warehouse SOPs are seeded into ChromaDB on tool load
try:
    seed_warehouse_sops(knowledge_store)
except Exception as e:
    logger.log_event("KNOWLEDGE_SEED_NOTICE", {"error": str(e)})


@tool("lookup_warehouse_location")
def lookup_warehouse_location(query_or_sku: str) -> str:
    """
    Look up the exact physical location (aisle, shelf, bin) and stock quantity
    for an item in the warehouse by its SKU (e.g. 'SKU-4521') or product name (e.g. 'barcode scanner').
    """
    res = resolve_location(query_or_sku)
    return res.get("formatted_message", "Location lookup completed.")


@tool("search_warehouse_knowledge_rag")
def search_warehouse_knowledge_rag(question: str) -> str:
    """
    Search the warehouse knowledge base and Standard Operating Procedures (SOPs)
    to answer questions about safety protocols, hazardous material rules,
    pallet stacking limits, forklift speed limits, and storage policies.
    """
    results = knowledge_store.query(question, n_results=knowledge_config.DEFAULT_RAG_TOP_K)
    if not results:
        return "No specific warehouse standard operating procedure found for this question."

    formatted = []
    for r in results:
        formatted.append(f"[{r['title']} ({r['category']})]\n{r['content']}")
    return "\n\n".join(formatted)


@tool("extract_warehouse_entities_tool")
def extract_warehouse_entities_tool(unstructured_text: str) -> str:
    """
    Extract structured warehouse entities (SKUs, quantities, locations, dates)
    from unstructured receiving notes or operator instructions.
    """
    entities = extract_warehouse_entities(unstructured_text)
    return json.dumps(entities, indent=2)


@tool("get_shift_handoff_summary")
def get_shift_handoff_summary(shift_type: str = "") -> str:
    """
    Retrieve the most recent shift handoff briefing, incidents, and pending tasks.
    Optionally specify the shift ('morning', 'afternoon', 'night').
    """
    res = get_latest_shift_handoff(shift_type if shift_type.strip() else None)
    return res.get("formatted_message", "No shift handoff records found.")


@tool("log_shift_handoff_note")
def log_shift_handoff_note(
    shift_type: str,
    supervisor: str,
    summary: str,
    incidents: str = "",
    pending_tasks: str = ""
) -> str:
    """
    Log a new shift transition note with operational summary, incidents, and pending tasks.
    """
    res = record_shift_handoff(
        shift_type=shift_type,
        supervisor=supervisor,
        summary=summary,
        incidents=incidents if incidents else None,
        pending_tasks=pending_tasks if pending_tasks else None
    )
    return res.get("formatted_message", "Shift handoff recorded.")

@tool("check_warehouse_compliance_tool")
def check_warehouse_compliance_tool(operational_query: str) -> str:
    """
    Check whether an operational action complies with warehouse safety and SOP rules.
    Evaluates pallet stacking heights by zone, damaged pallet red-tag rules, forklift speed limits,
    and battery charging PPE protocols.
    """
    res = evaluate_compliance_query(operational_query)
    return res.get("formatted_message", "Compliance check completed.")

@tool("triage_customer_return_tool")
def triage_customer_return_tool(return_query_or_rma: str) -> str:
    """
    Triage inbound customer returns according to SOP-RET-004.
    Evaluates RMA presence, box seals, defects, or water damage, and assigns
    grades (Grade A to Zone B, Grade B to Repackaging 4, Grade C to Bay 11 Quarantine).
    """
    res = evaluate_return_query(return_query_or_rma)
    return res.get("formatted_message", "Return triage completed.")
