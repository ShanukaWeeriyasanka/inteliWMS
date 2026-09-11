"""
Knowledge Agent Core Engine.
Factory for CrewAI Agent and unified execution pipeline with fast-path optimization.
"""
import os
from typing import Dict, Any, Optional

try:
    from crewai import Agent, Task, Crew
    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False
    Agent = None

from agents.knowledge_agent.shift_handoff import get_latest_shift_handoff
from agents.knowledge_agent.location_resolver import resolve_location
from agents.knowledge_agent.knowledge_store import knowledge_store, seed_warehouse_sops
from agents.knowledge_agent.ner import extract_warehouse_entities
from agents.knowledge_agent.config import knowledge_config
from config.prompts import (
    KNOWLEDGE_AGENT_ROLE,
    KNOWLEDGE_AGENT_GOAL,
    KNOWLEDGE_AGENT_BACKSTORY
)
from utils.logger import StructuredLogger
from agents.knowledge_agent.tools import (
    lookup_warehouse_location,
    search_warehouse_knowledge_rag,
    extract_warehouse_entities_tool,
    get_shift_handoff_summary,
    log_shift_handoff_note,
    check_warehouse_compliance_tool,
    triage_customer_return_tool
)
from agents.knowledge_agent.compliance import evaluate_compliance_query
from agents.knowledge_agent.returns_handler import evaluate_return_query


logger = StructuredLogger(__name__)

# Ensure seed SOPs are present in store
try:
    seed_warehouse_sops(knowledge_store)
except Exception as e:
    logger.log_event("KNOWLEDGE_STORE_SEED_WARN", {"error": str(e)})


def create_knowledge_agent() -> Optional[Any]:
    """Factory function to build the CrewAI Knowledge Agent."""
    if not CREWAI_AVAILABLE:
        return None
    return Agent(
        role=KNOWLEDGE_AGENT_ROLE,
        goal=KNOWLEDGE_AGENT_GOAL,
        backstory=KNOWLEDGE_AGENT_BACKSTORY,
        tools=[
            lookup_warehouse_location,
            search_warehouse_knowledge_rag,
            extract_warehouse_entities_tool,
            get_shift_handoff_summary,
            log_shift_handoff_note,
            check_warehouse_compliance_tool ,
            triage_customer_return_tool
        ],
        llm=knowledge_config.MODEL_NAME,
        verbose=False,
        allow_delegation=False
    )


# Singleton Agent instance
knowledge_agent = create_knowledge_agent()


def execute_knowledge_query(query: str, user_role: str = "staff", context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Unified entry point to execute a Knowledge Agent query.
    
    Optimized fast-path engine:
      - Location queries ("Where is SKU-4521?") resolve directly against DB in <10ms.
      - Policy/SOP queries ("What are pallet limits in Zone A?") retrieve from ChromaDB.
      - Full entity breakdown is included in the structured response.
      
    Args:
        query: User message or question
        user_role: Role of the querying user ('staff', 'manager', 'admin')
        context: Optional conversation context from Coordinator
        
    Returns:
        Dict adhering to KnowledgeQueryResponse schema.
    """
    if not query or not query.strip():
        return {
            "agent": "knowledge_agent",
            "query": "",
            "response": "Please specify a product, SKU, or warehouse procedure question.",
            "entities": {},
            "source": "none"
        }

    clean_query = query.strip()
    entities = extract_warehouse_entities(clean_query)
    intent = entities.get("intent_hint", "general_query")

    logger.log_event("KNOWLEDGE_AGENT_QUERY_RECEIVED", {
        "query": clean_query[:80],
        "user_role": user_role,
        "intent": intent
    })

    # 0. Fast-Path: Shift Handoff Inquiries (e.g. "morning shift notes", "what happened in the last shift")
    lower_q = clean_query.lower()
    if any(k in lower_q for k in ["shift", "handoff", "handover"]):
        # Check if user mentioned a specific shift
        target_shift = None
        for s in ["morning", "afternoon", "evening", "night"]:
            if s in lower_q:
                target_shift = s
                break

        handoff_res = get_latest_shift_handoff(target_shift)
        return {
            "agent": "knowledge_agent",
            "query": clean_query,
            "response": handoff_res.get("formatted_message"),
            "entities": entities,
            "data": handoff_res,
            "source": "shift_handoff"
        }

    # 0.5. Fast-Path: Compliance & Safety Rule Checks (e.g. "can I stack 4 tiers", "is 7 mph allowed")
    if any(k in lower_q for k in ["compliance", "compliant", "allowed", "can we stack", "can i stack", "speed limit", "legal speed"]):
        compliance_res = evaluate_compliance_query(clean_query)
        return {
            "agent": "knowledge_agent",
            "query": clean_query,
            "response": compliance_res.get("formatted_message"),
            "entities": entities,
            "data": compliance_res,
            "source": "compliance_engine"
        }

    # 0.7. Fast-Path: Customer Returns & RMA Triage (e.g. "triage return RMA-4521", "damaged return")
    if any(k in lower_q for k in ["triage return", "process return", "rma-", "customer return", "reverse logistics"]):
        return_res = evaluate_return_query(clean_query)
        return {
            "agent": "knowledge_agent",
            "query": clean_query,
            "response": return_res.get("formatted_message"),
            "entities": entities,
            "data": return_res,
            "source": "returns_triage"
        }



    # 1. Fast-Path: RAG SOP & Policy Retrieval (Prioritized for procedure/safety queries)
    if intent == "document_query" or any(w in clean_query.lower() for w in ["sop", "procedure", "policy", "safety", "rule", "protocol", "height", "speed", "hazard", "battery", "spill", "stacking", "limit"]):
        rag_hits = knowledge_store.query(clean_query, n_results=knowledge_config.DEFAULT_RAG_TOP_K)
        if rag_hits:
            best_hit = rag_hits[0]
            answer = f"According to warehouse protocol '{best_hit['title']}':\n{best_hit['content']}"
            return {
                "agent": "knowledge_agent",
                "query": clean_query,
                "response": answer,
                "entities": entities,
                "rag_sources": rag_hits,
                "source": "vector_rag"
            }

    # 2. Fast-Path: Physical Location Lookup
    if intent == "location_query" or entities.get("skus") or entities.get("locations"):
        loc_result = resolve_location(clean_query)
        if loc_result.get("found"):
            return {
                "agent": "knowledge_agent",
                "query": clean_query,
                "response": loc_result.get("formatted_message"),
                "entities": entities,
                "data": loc_result,
                "source": "database_location"
            }

    # 3. Fallback: Check RAG once more before declaring item not found
    rag_fallback = knowledge_store.query(clean_query, n_results=1)
    if rag_fallback:
        best_hit = rag_fallback[0]
        answer = f"According to warehouse protocol '{best_hit['title']}':\n{best_hit['content']}"
        return {
            "agent": "knowledge_agent",
            "query": clean_query,
            "response": answer,
            "entities": entities,
            "rag_sources": rag_fallback,
            "source": "vector_rag"
        }

    # 4. Fallback: Final attempt against database product location
    loc_fallback = resolve_location(clean_query)
    if loc_fallback.get("found"):
        return {
            "agent": "knowledge_agent",
            "query": clean_query,
            "response": loc_fallback.get("formatted_message"),
            "entities": entities,
            "data": loc_fallback,
            "source": "database_location"
        }

    return {
        "agent": "knowledge_agent",
        "query": clean_query,
        "response": loc_fallback.get("formatted_message", "I could not find a matching product location or warehouse procedure for your request."),
        "entities": entities,
        "source": "general_knowledge"
    }
