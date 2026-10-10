"""
Routing Decision Engine for IntelliWMS Coordinator Agent (Task 2).
Maps classified user intents to specialist agent identities:
- INVENTORY    -> inventory_agent
- FULFILLMENT  -> fulfillment_agent
- KNOWLEDGE    -> knowledge_agent
- COORDINATOR  -> answered directly (no delegation)

Decision pipeline (rules first, in code):
  1. Code rules on the user's original text.
  2. Only if no rule decides: a guarded LLM rewrite, then the rules again on the rewrite.
  3. Only if still undecided: the LLM may suggest a domain; code accepts it only when
     valid and confident, otherwise a fixed fallback applies (see intent_classifier.py).
Coordinator replies come from a fixed table keyed by rule id; LLM wording is used only
for small talk the LLM itself classified, with a timeout and a fixed fallback.
Every step is recorded as a decision (utils/decisions.py) for logs, metrics and the response.
"""
import inspect
from typing import Any, Callable, Dict, Optional, Tuple

from agents.coordinator.intent_classifier import IntentClassifier, IntentResult, intent_classifier
from agents.coordinator.llm_calls import OK, call_llm
from agents.coordinator.query_normalizer import ACCEPTED, normalize_with_outcome
from config.prompts import (
    COORDINATOR_ACK_REPLY,
    COORDINATOR_BYE_REPLY,
    COORDINATOR_CAPABILITY_REPLY,
    COORDINATOR_CLARIFY_DOMAIN_REPLY,
    COORDINATOR_CONFIDENTIAL_REPLY,
    COORDINATOR_GREETING_REPLY,
    COORDINATOR_UNKNOWN_REPLY,
)
from security.responsible_ai import explain_sources, is_guard_rule, screen_output, screen_request
from security.sanitizer import fence_untrusted
from utils.decisions import FALLBACK, LLM, RULE, record_decision
from utils.logger import StructuredLogger
from utils.metrics import ROUTING_DECISIONS
from utils.tracing import span

logger = StructuredLogger(__name__)

INTENT_TO_AGENT_MAP = {
    "INVENTORY":   "inventory_agent",
    "FULFILLMENT": "fulfillment_agent",
    "KNOWLEDGE":   "knowledge_agent",
    "COORDINATOR": "coordinator",   # Handled in-process, not delegated
}

DEFAULT_FALLBACK_AGENT = "knowledge_agent"

# Fixed coordinator replies by the rule that decided the route
REPLY_BY_RULE = {
    "empty": COORDINATOR_GREETING_REPLY,
    "meta.greeting": COORDINATOR_GREETING_REPLY,
    "meta.capability": COORDINATOR_CAPABILITY_REPLY,
    "meta.help": COORDINATOR_CAPABILITY_REPLY,
    "meta.weak": COORDINATOR_CAPABILITY_REPLY,
    "meta.self_disclosure": COORDINATOR_CONFIDENTIAL_REPLY,
    "social.ack": COORDINATOR_ACK_REPLY,
    "social.bye": COORDINATOR_BYE_REPLY,
    "clarify.domain": COORDINATOR_CLARIFY_DOMAIN_REPLY,
}
_REPLY_MAX_CHARS = 600
# accepted rewrite = the LLM's output was used; guard rejections and skips = code decided;
# LLM failure / timeout = fixed fallback (original text kept)
_NORMALIZE_DECIDER = {ACCEPTED: LLM, "failed": FALLBACK, "timeout": FALLBACK}


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


def select_coordinator_reply(query: str, result: Optional[IntentResult] = None,
                             context: Optional[Dict[str, Any]] = None) -> Tuple[str, str, str, Optional[str]]:
    """
    Reply text for a COORDINATOR decision → (text, reply_rule, decided_by, llm_status).
    Fixed text for every rule; LLM wording only when the LLM itself classified the message.
    """
    rule_id = getattr(result, "rule_id", None)
    if rule_id is None and getattr(result, "decided_by", None) != LLM:
        matched = intent_classifier.match_rules(query, context)
        rule_id = matched.rule_id if matched is not None else None
    if rule_id in REPLY_BY_RULE:
        return REPLY_BY_RULE[rule_id], f"reply.{rule_id}", RULE, None
    if rule_id == "transparency.source":
        return explain_sources((context or {}).get("history")), f"reply.{rule_id}", RULE, None
    if is_guard_rule(rule_id):
        guard = screen_request(query)
        if guard is not None:
            return guard.reply, f"reply.{guard.rule_id}", RULE, None

    if getattr(result, "decided_by", None) == LLM:
        from config.llm_config import llm_config
        from config.prompts import COORDINATOR_DIRECT_REPLY_SYSTEM, COORDINATOR_DIRECT_REPLY_USER
        status, text = call_llm("reply", lambda: llm_config.hybrid_complete(
            prompt=COORDINATOR_DIRECT_REPLY_USER.format(query=fence_untrusted(query)),
            system=COORDINATOR_DIRECT_REPLY_SYSTEM, max_tokens=200),
            available=bool(llm_config.gemini_key or llm_config.groq_key))
        if status == OK and len(str(text).strip()) > 1:
            text = str(text).strip()[:_REPLY_MAX_CHARS]
            blocked = screen_output(text)
            if blocked:
                # Output moderation: the LLM's wording is replaced, never shown
                logger.log_event("LLM_REPLY_BLOCKED", {"reason": blocked})
                return COORDINATOR_UNKNOWN_REPLY, f"reply.blocked_{blocked}", FALLBACK, status
            return text, "reply.llm_small_talk", LLM, status
        return COORDINATOR_UNKNOWN_REPLY, "reply.unknown", FALLBACK, status

    return COORDINATOR_UNKNOWN_REPLY, "reply.unknown", RULE, None


def build_coordinator_direct_response(query: str, result: Optional[IntentResult] = None) -> str:
    """Direct reply for meta/system questions (see select_coordinator_reply)."""
    return select_coordinator_reply(query, result)[0]


def _classify(classifier, query: str, context: Optional[Dict[str, Any]]):
    # Custom / mocked classifiers may not accept conversation context
    if context is not None and "context" in inspect.signature(classifier.classify).parameters:
        return classifier.classify(query, context=context)
    return classifier.classify(query)


def decide_route(query: str, classifier: Optional[IntentClassifier] = None,
                 context: Optional[Dict[str, Any]] = None,
                 normalizer: Callable[..., Tuple[str, str]] = normalize_with_outcome) -> Dict[str, Any]:
    """
    Computes the full routing decision: rules on the original text, then (only if needed)
    a guarded rewrite and the rules again, then (only if still needed) the LLM's suggestion.

    Args:
        query: Sanitized user query message (original wording)
        classifier: Optional custom IntentClassifier instance
        context: Optional thread context (last domain, pending clarification, recent turns)
        normalizer: rewrite step, (text, context) -> (rewritten_text, outcome)

    Returns:
        dict with target_agent, intent/domain, confidence, reasoning, source, follow_up,
        rule_id, decided_by, llm_consulted, llm_status, normalized_query, direct_response,
        decisions (the decisions recorded by this call)
    """
    active = classifier or intent_classifier
    decisions = []
    normalized_query = None

    with span("routing.decide") as sp:
        if isinstance(active, IntentClassifier):
            result = active.match_rules(query, context)
            if result is None:
                rewritten, outcome = normalizer(query, context)
                decisions.append(record_decision(
                    "normalize", outcome, _NORMALIZE_DECIDER.get(outcome, RULE), f"normalize.{outcome}",
                    llm_consulted=not outcome.startswith("skipped")))
                if outcome == ACCEPTED and rewritten and rewritten != query:
                    normalized_query = rewritten
                    result = active.match_rules(rewritten, context)
                if result is None:
                    result = active.classify(normalized_query or query, context)
        else:
            result = _classify(active, query, context)
        source = getattr(result, "source", "heuristic")
        rule_id = getattr(result, "rule_id", None)
        decided_by = getattr(result, "decided_by", RULE)
        sp.set(domain=result.domain, decided_by=decided_by, rule_id=rule_id)

    domain = result.domain
    confidence = result.confidence
    target_agent = route_to_agent(domain)
    llm_consulted = bool(getattr(result, "llm_consulted", False))
    llm_status = getattr(result, "llm_status", None)
    ROUTING_DECISIONS.inc(domain=domain, source=source)
    decisions.append(record_decision(
        "route", domain, decided_by, rule_id, llm_consulted=llm_consulted, llm_status=llm_status,
        confidence=confidence, target_agent=target_agent, normalized=normalized_query is not None))

    direct_response = None
    if domain == "COORDINATOR":
        with span("routing.reply") as rsp:
            direct_response, reply_rule, reply_by, reply_status = select_coordinator_reply(query, result, context)
            rsp.set(rule_id=reply_rule, decided_by=reply_by)
        decisions.append(record_decision("reply", reply_rule.split(".", 1)[1], reply_by, reply_rule,
                                         llm_consulted=reply_status is not None, llm_status=reply_status))

    logger.log_event("COORDINATOR_ROUTING_DECISION", {
        "intent": domain,
        "target_agent": target_agent,
        "confidence": confidence,
        "rule_id": rule_id,
        "decided_by": decided_by,
        "source": source,
        "llm_consulted": llm_consulted,
        "llm_status": llm_status,
        "llm_reasoning": result.reasoning if decided_by == LLM else None,
        "follow_up": source == "context",
        "normalized": normalized_query is not None,
        "direct": direct_response is not None
    })

    return {
        "target_agent": target_agent,
        "intent": domain,
        "domain": domain,
        "confidence": confidence,
        "reasoning": result.reasoning,
        "source": source,
        "follow_up": source == "context",
        "rule_id": rule_id,
        "decided_by": decided_by,
        "llm_consulted": llm_consulted,
        "llm_status": llm_status,
        "normalized_query": normalized_query,
        "direct_response": direct_response,
        "decisions": [d.__dict__ for d in decisions],
    }
