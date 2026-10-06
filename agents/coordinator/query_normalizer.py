"""
Query Normalizer for IntelliWMS Coordinator Agent.

Converts vague, broken-English, or incomplete user inputs into clear warehouse
queries before intent classification and agent routing.

PERFORMANCE NOTE: LLM normalization is skipped for most inputs to keep
response time < 1s. The heuristic classifier handles routing correctly
without normalized text. LLM normalization only activates for very short
or clearly broken inputs when GEMINI_API_KEY is configured.
"""
import re
from typing import Any, Dict, Optional, Tuple

from agents.coordinator.llm_calls import OK, TIMEOUT, call_llm
from config.llm_config import llm_config
from config.prompts import QUERY_NORMALIZER_PROMPT
from utils.logger import StructuredLogger

logger = StructuredLogger(__name__)

# Patterns that indicate the query is already clear enough — skip LLM
_CLEAR_QUERY_PATTERNS = [
    r"\b(sku|order|sop|stock|inventory|aisle|shelf|bin|zone|hazmat|forklift|rma)\b",
    r"\b(where is|what is|how many|check|find|locate|status|delay|ship|track)\b",
    r"\b(safety|compliance|protocol|procedure|guideline|return|dispatch)\b",
    # Digital Twin place IDs ("rack 2", "cold 3", PRD-00002) must reach resolve_location() as typed
    r"\b(rack|crate|cold|freezer)\s*#?\s*\d+\b|\bprd-\d{5}\b|\bwh\d+-f\d+",
]
_CLEAR_PATTERN = re.compile("|".join(_CLEAR_QUERY_PATTERNS), re.IGNORECASE)


def _is_already_clear(query: str) -> bool:
    """
    Returns True if the query already contains recognizable warehouse keywords
    or is long enough to be unambiguous — meaning LLM normalization adds no value.
    """
    words = query.strip().split()
    # Already long and ends with punctuation → definitely clear
    if len(words) >= 6 and query.strip()[-1] in ".?!":
        return True
    # Contains warehouse domain keywords → heuristic classifier handles fine
    if _CLEAR_PATTERN.search(query):
        return True
    # Not too short → reasonable to pass as-is
    if len(words) >= 4:
        return True
    return False


_FOLLOW_UP = re.compile(r"\b(it|its|that|this|those|these|them|they|same|the one)\b|^\s*(and|also|what about|how about)\b"
                        r"|^\s*#?\d\s*[.!?]?\s*$", re.IGNORECASE)

# Ids a rewrite might add: SKU-4521, ORD-1001, PRD-00002, #4521
_ID_IN_TEXT = re.compile(r"\b(?:sku|ord|prd)[-\s]?(\d{3,6})\b|#(\d{3,6})\b", re.IGNORECASE)
MAX_REWRITE_CHARS = 200

# Outcomes (recorded as the "normalize" decision by the router)
ACCEPTED = "accepted"
SKIPPED_EMPTY, SKIPPED_CLEAR, SKIPPED_FOLLOW_UP, SKIPPED_NO_LLM = (
    "skipped_empty", "skipped_clear", "skipped_follow_up", "skipped_no_llm")
REJECTED_NEW_ID, REJECTED_TOO_LONG = "rejected_new_id", "rejected_too_long"
FAILED, TIMED_OUT = "failed", "timeout"


def _invents_id(original: str, rewritten: str) -> bool:
    """True when the rewrite names an id whose digits the user never typed."""
    typed_digits = set(re.findall(r"\d+", original))
    for match in _ID_IN_TEXT.finditer(rewritten):
        if (match.group(1) or match.group(2)) not in typed_digits:
            return True
    return False


def normalize_with_outcome(raw_query: str, context: Optional[Dict[str, Any]] = None) -> Tuple[str, str]:
    """
    Rewrite short / broken input into a clear sentence so the code rules can try again.

    Only used after the rules found nothing to decide on the original text. The rewrite
    is accepted only if it adds no id the user didn't type and stays a short sentence;
    otherwise the original text is kept. Returns (text, outcome).
    """
    if not raw_query or not raw_query.strip():
        return raw_query, SKIPPED_EMPTY
    original = raw_query.strip()

    # Fast path: skip expensive LLM call for clear inputs
    if _is_already_clear(original):
        return original, SKIPPED_CLEAR

    # Follow-ups only make sense with their conversation; rewriting "the second one" or "and that?"
    # without it would change their meaning, so keep them exactly as typed.
    if context and context.get("last_domain") and (_FOLLOW_UP.search(original) or len(original.split()) <= 4):
        return original, SKIPPED_FOLLOW_UP

    if not llm_config.gemini_key and not llm_config.groq_key:
        return original, SKIPPED_NO_LLM

    status, rewritten = call_llm("normalize", lambda: llm_config.hybrid_complete(
        prompt=f'Input: "{original}"', system=QUERY_NORMALIZER_PROMPT, max_tokens=64))
    if status == TIMEOUT:
        return original, TIMED_OUT
    if status != OK:
        return original, FAILED
    cleaned = str(rewritten).strip().strip('"').strip("'").strip()
    if len(cleaned) <= 3:
        return original, FAILED
    if len(cleaned) > MAX_REWRITE_CHARS:
        return original, REJECTED_TOO_LONG
    if _invents_id(original, cleaned):
        return original, REJECTED_NEW_ID
    logger.log_event("QUERY_NORMALIZED", {"original": original, "normalized": cleaned})
    return cleaned, ACCEPTED


def normalize_query(raw_query: str, context: Optional[Dict[str, Any]] = None) -> str:
    """Rewritten text when a rewrite was accepted, otherwise the original (stripped) text."""
    return normalize_with_outcome(raw_query, context)[0]
