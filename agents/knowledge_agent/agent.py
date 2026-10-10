"""
Knowledge Agent Core Engine.
Factory for CrewAI Agent and unified execution pipeline with fast-path optimization.
"""
import json
import os
import re
from functools import lru_cache
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
from security.responsible_ai import screen_request


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

    # Responsible AI: the same fixed answers as the coordinator, for callers that reach this agent directly
    guard = screen_request(clean_query)
    if guard is not None:
        return {"agent": "knowledge_agent", "query": clean_query, "response": guard.reply, "entities": {},
                "source": "responsible_ai", "rule_id": guard.rule_id}

    entities = extract_warehouse_entities(clean_query)
    intent = entities.get("intent_hint", "general_query")

    # A named SOP that isn't in the library, or a section it doesn't have: say so, never stand in another
    unknown = _unknown_citation(clean_query)
    if unknown:
        return {"agent": "knowledge_agent", "query": clean_query, "response": unknown, "entities": entities,
                "source": "not_found"}

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
    if intent == "document_query" or any(w in lower_q for w in ["sop", "procedure", "policy", "safety", "rule", "protocol", "height", "speed", "hazard", "spill", "stacking", "limit", "excursion", "weighbridge scale protocol", "carrier check-in"]):
        rag_hits = knowledge_store.query(clean_query, n_results=knowledge_config.DEFAULT_RAG_TOP_K)
        if rag_hits:
            best_hit = rag_hits[0]
            answer = cite_sop(best_hit)
            return {
                "agent": "knowledge_agent",
                "query": clean_query,
                "response": answer,
                "entities": entities,
                "rag_sources": rag_hits,
                "source": "vector_rag"
            }

        # A procedure question the library doesn't cover: say so here, before the fuzzy location lookup can
        # turn its words into an unrelated place or product ("rooftop drone landings" → a battery bay)
        if (_PROCEDURE_QUESTION.search(lower_q) and not entities.get("skus")
                and not re.search(r"\b(where|locate|location)\b", lower_q)):
            return {
                "agent": "knowledge_agent",
                "query": clean_query,
                "response": NO_MATCHING_SOP_REPLY,
                "entities": entities,
                "source": "no_match"
            }

    # 2. Fast-Path: Campus Facility, Vehicle & Physical Location Lookup
    # Matches: "Where is Building 4?", "Where is Cold Vault?", "Where is Forklift 1?", "Where is 60T scale?", "Where is SKU-4521?"
    if (
        intent == "location_query"
        or any(w in lower_q for w in ["where", "locate", "building", "cold vault", "quarantine", "gatehouse", "weighbridge", "forklift", "reach truck", "pallet jack", "agv", "campus"])
        or entities.get("skus")
        or entities.get("locations")
    ):
        loc_result = resolve_location(clean_query)
        if loc_result.get("found"):
            # Set source preserving backward compatibility for unit tests expecting 'database_location'
            entity_type = loc_result.get("entity_type", "database_location")
            source = "database_location" if entity_type == "product_sku" else entity_type
            return {
                "agent": "knowledge_agent",
                "query": clean_query,
                "response": loc_result.get("formatted_message"),
                "entities": entities,
                "data": loc_result,
                "source": source
            }

    # 3. Fallback: Check RAG once more before declaring item not found
    rag_fallback = knowledge_store.query(clean_query, n_results=1)
    if rag_fallback:
        best_hit = rag_fallback[0]
        answer = cite_sop(best_hit)
        return {
            "agent": "knowledge_agent",
            "query": clean_query,
            "response": answer,
            "entities": entities,
            "rag_sources": rag_fallback,
            "source": "vector_rag"
        }

    # 4. Fallback: Final attempt against campus and product location resolver
    loc_fallback = resolve_location(clean_query)
    if loc_fallback.get("found"):
        entity_type = loc_fallback.get("entity_type", "database_location")
        source = "database_location" if entity_type == "product_sku" else entity_type
        return {
            "agent": "knowledge_agent",
            "query": clean_query,
            "response": loc_fallback.get("formatted_message"),
            "entities": entities,
            "data": loc_fallback,
            "source": source
        }

    # Nothing relevant in the SOP library: say so instead of offering the nearest unrelated procedure
    if _PROCEDURE_QUESTION.search(lower_q):
        return {
            "agent": "knowledge_agent",
            "query": clean_query,
            "response": NO_MATCHING_SOP_REPLY,
            "entities": entities,
            "source": "no_match"
        }
    return {
        "agent": "knowledge_agent",
        "query": clean_query,
        "response": loc_fallback.get("formatted_message", "I could not find a matching campus location or warehouse procedure for your request."),
        "entities": entities,
        "source": "general_knowledge"
    }


# ── Grounding helpers ────────────────────────────────────────────────────────

NO_MATCHING_SOP_REPLY = (
    "I couldn't find a documented procedure for that in the SOP library, so I won't guess. "
    "Please check with your shift supervisor or safety officer."
)
_PROCEDURE_QUESTION = re.compile(
    r"\b(sop|procedure|policy|policies|protocol|rules?|guidelines?|safety|how (do|should|to)|what should|"
    r"steps?|allowed|permitted|hazard|emergency|evacuat\w*)\b")
_DOC_ID = re.compile(r"\b(?:SOP|GUIDE)-[A-Z]+-\d{3}\b", re.I)
_SECTION_REF = re.compile(r"(?:\bsection|\bsec\.?|§)\s*(\d+)", re.I)


@lru_cache(maxsize=1)
def _sop_catalogue() -> Dict[str, Dict[str, Any]]:
    """doc_id → {title, sections} from the seeded SOP file (the library the store is built from)."""
    try:
        with open(knowledge_config.SEED_SOPS_PATH, "r", encoding="utf-8") as f:
            docs = json.load(f)
    except (OSError, ValueError):
        return {}
    return {d["doc_id"].upper(): {"title": d.get("title", d["doc_id"]),
                                  "sections": len([p for p in d.get("content", "").split("\n\n") if p.strip()])}
            for d in docs if d.get("doc_id")}


def _unknown_citation(query: str) -> Optional[str]:
    """The reply for an SOP id the library doesn't hold, or a section past the end of one; None otherwise."""
    ids = [m.upper() for m in _DOC_ID.findall(query)]
    catalogue = _sop_catalogue() if ids else {}
    if not catalogue:
        return None
    missing = [i for i in ids if i not in catalogue]
    if missing:
        return (f"I can't find **{missing[0]}** in the SOP library, so I can't tell you what it says — and I won't "
                f"substitute another document. Documents on record: {', '.join(sorted(catalogue))}. "
                f"Check the number with your supervisor.")
    section = _SECTION_REF.search(query)
    doc = catalogue[ids[0]]
    if section and doc["sections"] and int(section.group(1)) > doc["sections"]:
        return (f"**{ids[0]}** ('{doc['title']}') has sections 1–{doc['sections']} only, so there is no section "
                f"{section.group(1)}. Ask me about one of its sections, or check with your supervisor.")
    return None


def cite_sop(hit: Dict[str, Any]) -> str:
    """An SOP chunk quoted with its document id and section, so the answer can be checked."""
    ref = hit.get("doc_id") or "SOP"
    if hit.get("section"):
        ref += f" §{hit['section']}"
    return (f"According to {ref} — '{hit.get('title', 'Warehouse SOP')}':\n{hit['content']}\n\n"
            f"📎 Source: {ref} (SOP library).")
