"""
Routing Decision Engine for IntelliWMS Coordinator Agent (Task 2).
Maps classified user intents to specialist agent identities:
- INVENTORY    -> inventory_agent
- FULFILLMENT  -> fulfillment_agent
- KNOWLEDGE    -> knowledge_agent
- COORDINATOR  -> answered directly (no delegation)
Logs routing reasoning for Responsible AI audit compliance.
"""
from typing import Optional, Dict, Any
from utils.logger import StructuredLogger
from agents.coordinator.intent_classifier import intent_classifier, IntentClassifier

logger = StructuredLogger(__name__)

INTENT_TO_AGENT_MAP = {
    "INVENTORY":   "inventory_agent",
    "FULFILLMENT": "fulfillment_agent",
    "KNOWLEDGE":   "knowledge_agent",
    "COORDINATOR": "coordinator",   # Handled in-process, not delegated
}

DEFAULT_FALLBACK_AGENT = "knowledge_agent"


def route_to_agent(intent: str) -> str:
    """
    Maps an intent string to its corresponding target agent identifier.
    Returns 'coordinator' for meta/system questions.
    Defaults to 'knowledge_agent' if intent is unrecognized or ambiguous.
    """
    if not intent:
        return DEFAULT_FALLBACK_AGENT
    normalized = str(intent).strip().upper()
    return INTENT_TO_AGENT_MAP.get(normalized, DEFAULT_FALLBACK_AGENT)


def build_coordinator_direct_response(query: str) -> str:
    """
    Uses hybrid LLM (Gemini → Groq) to generate a helpful direct reply for
    meta/system questions that don't need specialist agent delegation.
    """
    # Fast-path for simple greetings to save API latency
    q_lower = query.lower().strip()
    import re
    if re.match(r"^(hi+|hello+|hey+|yo+|greetings|sup|howdy)[\s\!\?\.]*$", q_lower):
        return "👋 Hello! I'm the IntelliWMS Coordinator. I can help you with Inventory 📦, Fulfillment 🚚, or warehouse SOPs 📚. What do you need?"

    from config.llm_config import llm_config
    from config.prompts import COORDINATOR_DIRECT_REPLY_PROMPT, COORDINATOR_UNKNOWN_REPLY

    try:
        prompt = COORDINATOR_DIRECT_REPLY_PROMPT.format(query=query)
        reply = llm_config.hybrid_complete(prompt=prompt, max_tokens=300)
        # Removed the >10 char limit so short answers ("Hi!") don't get blocked
        if reply and len(reply.strip()) > 1:
            return reply.strip()
    except Exception as e:
        logger.log_event("COORDINATOR_DIRECT_REPLY_FAILED", {"error": str(e)})

    return COORDINATOR_UNKNOWN_REPLY


def decide_route(query: str, classifier: Optional[IntentClassifier] = None) -> Dict[str, Any]:
    """
    Classifies a query and computes the full routing decision with reasoning.

    Args:
        query: Sanitized (and optionally normalized) user query message
        classifier: Optional custom IntentClassifier instance

    Returns:
        dict: {
            "target_agent": "...",
            "intent": "...",
            "domain": "...",
            "confidence": float,
            "reasoning": "...",
            "direct_response": str | None   # Only set for COORDINATOR domain
        }
    """
    active_classifier = classifier or intent_classifier
    intent_result = active_classifier.classify(query)

    domain = intent_result.domain
    confidence = intent_result.confidence
    reasoning = intent_result.reasoning
    target_agent = route_to_agent(domain)
    direct_response = None

    # COORDINATOR domain: generate a direct reply from LLM, no specialist delegation
    if domain == "COORDINATOR":
        direct_response = build_coordinator_direct_response(query)

    logger.log_event("COORDINATOR_ROUTING_DECISION", {
        "query_preview": query[:60],
        "intent": domain,
        "target_agent": target_agent,
        "confidence": confidence,
        "reasoning": reasoning,
        "direct": direct_response is not None
    })

    return {
        "target_agent": target_agent,
        "intent": domain,
        "domain": domain,
        "confidence": confidence,
        "reasoning": reasoning,
        "direct_response": direct_response
    }
