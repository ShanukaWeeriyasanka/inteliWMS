"""
Shared utility package for IntelliWMS.
"""
from utils.spelling import (
    SpellCorrector,
    spell_corrector,
    correct_query,
    correct_query_detailed,
    correct_word,
    fuzzy_match,
    damerau_levenshtein_distance,
    similarity_ratio,
)

__all__ = [
    "SpellCorrector",
    "spell_corrector",
    "correct_query",
    "correct_query_detailed",
    "correct_word",
    "fuzzy_match",
    "damerau_levenshtein_distance",
    "similarity_ratio",
]
