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
from config.llm_config import llm_config
from config.prompts import QUERY_NORMALIZER_PROMPT
from utils.logger import StructuredLogger

logger = StructuredLogger(__name__)

# Patterns that indicate the query is already clear enough — skip LLM
_CLEAR_QUERY_PATTERNS = [
    r"\b(sku|order|sop|stock|inventory|aisle|shelf|bin|zone|hazmat|forklift|rma)\b",
    r"\b(where is|what is|how many|check|find|locate|status|delay|ship|track)\b",
    r"\b(safety|compliance|protocol|procedure|guideline|return|dispatch)\b",
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


def normalize_query(raw_query: str) -> str:
    """
    Normalize a raw user query into clear, standard English.

    For performance, skips the LLM call when the input is already
    clear (contains warehouse keywords, is long enough, or has punctuation).
    LLM normalization only fires for very short / ambiguous inputs.

    Args:
        raw_query: The raw string typed by the user.

    Returns:
        A cleaned, normalized query string. Falls back to original if LLM fails.
    """
    if not raw_query or not raw_query.strip():
        return raw_query

    # Fast path: skip expensive LLM call for clear inputs (saves 5-7s)
    if _is_already_clear(raw_query):
        return raw_query.strip()

    # Only call LLM for genuinely short/broken inputs (e.g. "4521 where", "stack?")
    if not llm_config.gemini_key and not llm_config.groq_key:
        return raw_query.strip()

    try:
        normalized = llm_config.hybrid_complete(
            prompt=f'Input: "{raw_query.strip()}"',
            system=QUERY_NORMALIZER_PROMPT,
            max_tokens=64
        )

        if normalized and len(normalized.strip()) > 3:
            cleaned = normalized.strip().strip('"').strip("'")
            logger.log_event("QUERY_NORMALIZED", {
                "original": raw_query,
                "normalized": cleaned
            })
            return cleaned

    except Exception as e:
        logger.log_event("QUERY_NORMALIZATION_FAILED", {
            "error": str(e),
            "falling_back_to_original": raw_query
        })

    return raw_query.strip()
