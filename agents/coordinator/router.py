"""
Routing Decision Engine for IntelliWMS Coordinator Agent (Task 2).
Maps classified user intents to specialist agent identities:
- INVENTORY -> inventory_agent
- FULFILLMENT -> fulfillment_agent
- KNOWLEDGE -> knowledge_agent
Logs routing reasoning for Responsible AI audit compliance.
"""
from typing import Optional, Dict, Any
from utils.logger import StructuredLogger
from agents.coordinator.intent_classifier import intent_classifier, IntentClassifier

logger = StructuredLogger(__name__)

INTENT_TO_AGENT_MAP = {
    "INVENTORY": "inventory_agent",
    "FULFILLMENT": "fulfillment_agent",
    "KNOWLEDGE": "knowledge_agent"
}

DEFAULT_FALLBACK_AGENT = "knowledge_agent"

def route_to_agent(intent: str) -> str:
    """
    Maps an intent string to its corresponding target agent identifier.
    Defaults to 'knowledge_agent' if intent is unrecognized or ambiguous.
    """
    if not intent:
        return DEFAULT_FALLBACK_AGENT
    normalized = str(intent).strip().upper()
    return INTENT_TO_AGENT_MAP.get(normalized, DEFAULT_FALLBACK_AGENT)

def decide_route(query: str, classifier: Optional[IntentClassifier] = None) -> Dict[str, Any]:
    """
    Classifies a query and computes the full routing decision with reasoning.
    
    Args:
        query: Sanitized user query message
        classifier: Optional custom IntentClassifier instance
        
    Returns:
        dict: {
            "target_agent": "...",
            "intent": "...",
            "domain": "...",
            "confidence": float,
            "reasoning": "..."
        }
    """
    active_classifier = classifier or intent_classifier
    intent_result = active_classifier.classify(query)

    domain = intent_result.domain
    confidence = intent_result.confidence
    reasoning = intent_result.reasoning
    target_agent = route_to_agent(domain)

    logger.log_event("COORDINATOR_ROUTING_DECISION", {
        "query_preview": query[:60],
        "intent": domain,
        "target_agent": target_agent,
        "confidence": confidence,
        "reasoning": reasoning
    })

    return {
        "target_agent": target_agent,
        "intent": domain,
        "domain": domain,
        "confidence": confidence,
        "reasoning": reasoning
    }
