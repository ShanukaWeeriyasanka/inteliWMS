"""
IntelliWMS Knowledge Agent Package.
Provides warehouse SKU location resolution, SOP guideline retrieval via vector RAG,
shift handoff management, safety compliance evaluation, and returns triage.
"""

from agents.knowledge_agent.agent import (
    knowledge_agent,
    create_knowledge_agent,
    execute_knowledge_query
)
from agents.knowledge_agent.location_resolver import resolve_location, get_location_by_sku
from agents.knowledge_agent.knowledge_store import knowledge_store, seed_warehouse_sops
from agents.knowledge_agent.ner import extract_warehouse_entities
from agents.knowledge_agent.shift_handoff import (
    record_shift_handoff,
    get_latest_shift_handoff,
    list_recent_shift_handoffs
)
from agents.knowledge_agent.compliance import (
    check_compliance,
    evaluate_compliance_query
)
from agents.knowledge_agent.returns_handler import (
    triage_returned_item,
    evaluate_return_query
)
from agents.knowledge_agent.config import knowledge_config
from agents.knowledge_agent.schemas import (
    KnowledgeQueryRequest,
    KnowledgeQueryResponse,
    LocationResult,
    RAGHit,
    ExtractedEntities,
    ShiftHandoffCreate,
    ShiftHandoffRecord,
    ComplianceCheckRequest,
    ComplianceCheckResponse,
    ReturnTriageRequest,
    ReturnTriageResponse
)

__all__ = [
    "knowledge_agent",
    "create_knowledge_agent",
    "execute_knowledge_query",
    "resolve_location",
    "get_location_by_sku",
    "knowledge_store",
    "seed_warehouse_sops",
    "extract_warehouse_entities",
    "record_shift_handoff",
    "get_latest_shift_handoff",
    "list_recent_shift_handoffs",
    "check_compliance",
    "evaluate_compliance_query",
    "triage_returned_item",
    "evaluate_return_query",
    "knowledge_config",
    "KnowledgeQueryRequest",
    "KnowledgeQueryResponse",
    "LocationResult",
    "RAGHit",
    "ExtractedEntities",
    "ShiftHandoffCreate",
    "ShiftHandoffRecord",
    "ComplianceCheckRequest",
    "ComplianceCheckResponse",
    "ReturnTriageRequest",
    "ReturnTriageResponse"
]
