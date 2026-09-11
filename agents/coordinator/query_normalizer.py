"""
Query Normalizer for IntelliWMS Coordinator Agent.

Converts vague, broken-English, or incomplete user inputs into clear warehouse
queries before intent classification and agent routing.

Uses Gemini → Groq hybrid LLM. Falls back to the original query if both fail.
"""
from config.llm_config import llm_config
from config.prompts import QUERY_NORMALIZER_PROMPT
from utils.logger import StructuredLogger

logger = StructuredLogger(__name__)


def normalize_query(raw_query: str) -> str:
    """
    Normalize a raw user query into clear, standard English.

    Handles:
    - Broken / pidgin English ("4521 wich aisle")
    - Very short / vague inputs ("stack limit?")
    - Mixed languages or slang
    - Typos and abbreviations

    Args:
        raw_query: The raw string typed by the user.

    Returns:
        A cleaned, normalized query string. Falls back to original if LLM fails.
    """
    if not raw_query or not raw_query.strip():
        return raw_query

    # Skip normalization for already-clear, long queries (saves LLM latency)
    if len(raw_query.split()) >= 8 and raw_query[-1] in ".?!":
        return raw_query.strip()

    try:
        normalized = llm_config.hybrid_complete(
            prompt=f'Input: "{raw_query.strip()}"',
            system=QUERY_NORMALIZER_PROMPT,
            max_tokens=128
        )

        if normalized and len(normalized.strip()) > 3:
            # Strip quotes the LLM sometimes wraps around output
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

    # Fallback: return original unchanged
    return raw_query.strip()
