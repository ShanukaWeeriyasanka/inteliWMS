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
    Returns a direct reply for meta/system questions without specialist delegation.

    Uses an expanded keyword fast-path map to avoid LLM API calls for common
    coordinator questions. Falls back to LLM only for truly novel questions.
    """
    import re
    q_lower = query.lower().strip()

    # --- Expanded fast-path map (instant, no API call) ---
    CAPABILITY_RESPONSE = (
        "I'm the **IntelliWMS Coordinator** 🤖. I manage 3 specialist agents:\n"
        "• 📦 **Inventory Agent** — stock levels, SKU locations, restock alerts\n"
        "• 🚚 **Fulfillment Agent** — order status, delays, shipping & dispatch\n"
        "• 📚 **Knowledge Agent** — SOPs, safety protocols, compliance, returns\n\n"
        "Just ask me a warehouse question and I'll route it to the right agent!"
    )
    GREETING_RESPONSE = (
        "👋 Hello! I'm the IntelliWMS Coordinator. I can help you with:\n"
        "📦 Inventory • 🚚 Fulfillment • 📚 Warehouse SOPs\n"
        "What do you need?"
    )

    # Greetings
    if re.match(r"^(hi+|hello+|hey+|yo+|greetings|sup|howdy|hiya)[\s\!\?\.]*$", q_lower):
        return GREETING_RESPONSE

    # Capability / what-can-you-do questions
    capability_patterns = [
        r"\bwhat can you do\b", r"\bwhat do you do\b", r"\bwhat are you\b",
        r"\bwho are you\b", r"\bintroduce yourself\b", r"\bwhat is intelliwms\b",
        r"\bhow many agents\b", r"\bhow many subagents\b", r"\blist.*agents\b",
        r"\bwhat agents\b", r"\bwhat subagents\b", r"\byour (agents|subagents|capabilities)\b",
        r"\bwhat.*system\b", r"\btell me about yourself\b",
    ]
    if any(re.search(p, q_lower) for p in capability_patterns):
        return CAPABILITY_RESPONSE

    # Help
    if re.match(r"^help[\s\!\?\.]*$", q_lower) or re.match(r"^what\?*$", q_lower):
        return CAPABILITY_RESPONSE

    # --- LLM fallback for genuinely novel questions ---
    from config.llm_config import llm_config
    from config.prompts import COORDINATOR_DIRECT_REPLY_PROMPT, COORDINATOR_UNKNOWN_REPLY

    try:
        prompt = COORDINATOR_DIRECT_REPLY_PROMPT.format(query=query)
        reply = llm_config.hybrid_complete(prompt=prompt, max_tokens=200)
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
