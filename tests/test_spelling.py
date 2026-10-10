"""
Unit tests for the Global Spelling Correction & Fuzzy Matching Engine (utils/spelling.py).
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from utils.spelling import (
    SpellCorrector,
    spell_corrector,
    correct_word,
    correct_query,
    correct_query_detailed,
    fuzzy_match,
    damerau_levenshtein_distance,
    similarity_ratio,
    is_protected_token,
)


# ==================== 1. Core Typo Fixes ====================

def test_missing_letters():
    """Missing characters should be restored (insertion operation)."""
    assert correct_word("quck") == "quick"
    assert correct_word("stck") == "stock"
    assert correct_word("forklft") == "forklift"
    assert correct_word("invenory") == "inventory"


def test_wrong_letters():
    """Substituted / wrong characters should be corrected."""
    assert correct_word("qwick") == "quick"
    assert correct_word("stoxk") == "stock"
    assert correct_word("fulfilment") == "fulfillment"


def test_scrambled_letters():
    """Adjacent transposed characters should be unscrambled."""
    assert correct_word("qiuck") == "quick"
    assert correct_word("froklift") == "forklift"


def test_extra_letters():
    """Duplicate / accidental extra characters should be removed."""
    assert correct_word("quuick") == "quick"
    assert correct_word("stocck") == "stock"


# ==================== 2. Casing & Punctuation ====================

def test_case_preservation():
    """Capitalization of the original word must be preserved."""
    assert correct_word("Quck") == "Quick"
    assert correct_word("QUCK") == "QUICK"
    assert correct_word("qiuck") == "quick"


def test_query_punctuation_and_spacing():
    """Sentence punctuation, tabs, and spaces must remain identical."""
    original = "Can you Quck check the stck, please?"
    corrected = correct_query(original)
    assert corrected == "Can you Quick check the stock, please?"


# ==================== 3. Protected Identifiers ====================

def test_protected_entity_tokens():
    """Warehouse SKUs, Order IDs, place codes, and numbers must never be modified."""
    assert is_protected_token("SKU-1004") is True
    assert is_protected_token("ORD-4521") is True
    assert is_protected_token("PRD-00002") is True
    assert is_protected_token("WH01-F02") is True
    assert is_protected_token("#4521") is True
    assert is_protected_token("100kg") is True

    # In a full query, entity codes stay untouched while typos are corrected
    query = "Check stck for SKU-1004 and ORD-4521 in WH01-F02"
    result = correct_query(query)
    assert result == "Check stock for SKU-1004 and ORD-4521 in WH01-F02"


# ==================== 4. Detailed Audit & Metrics ====================

def test_correct_query_detailed():
    """Detailed audit dictionary returns changes with distance and similarity."""
    detailed = correct_query_detailed("quck check stck")
    assert detailed["has_corrections"] is True
    assert detailed["corrected"] == "quick check stock"
    assert len(detailed["changes"]) == 2

    # Verify first change
    ch1 = detailed["changes"][0]
    assert ch1["original"] == "quck"
    assert ch1["corrected"] == "quick"
    assert ch1["distance"] == 1
    assert ch1["similarity"] >= 0.8


# ==================== 5. Fuzzy Match Function ====================

def test_fuzzy_match():
    """Finds best candidate above threshold from a candidate list."""
    candidates = ["quick", "pallet", "warehouse", "aisle"]
    match = fuzzy_match("quck", candidates, threshold=0.75)
    assert match is not None
    best_cand, score = match
    assert best_cand == "quick"
    assert score >= 0.8


# ==================== 6. Custom Vocabulary & Catalog Learning ====================

def test_custom_catalog_learning():
    """Custom words learned from catalog should be immediately correctable."""
    custom_corrector = SpellCorrector(initial_vocab=[])
    custom_corrector.learn_catalog({
        "products": [{"name": "Thermal Scanner Handheld", "category": "Electronics"}],
        "facilities": [{"name": "Cold Storage Vault", "building_id": "BLD-04"}],
    })

    assert custom_corrector.correct_word("therml") == "thermal"
    assert custom_corrector.correct_word("scaner") == "scanner"
    assert custom_corrector.correct_word("storag") == "storage"


if __name__ == "__main__":
    test_missing_letters()
    test_wrong_letters()
    test_scrambled_letters()
    test_extra_letters()
    test_case_preservation()
    test_query_punctuation_and_spacing()
    test_protected_entity_tokens()
    test_correct_query_detailed()
    test_fuzzy_match()
    test_custom_catalog_learning()
    print("ALL 10 SPELLING & FUZZY MATCH TESTS PASSED SUCCESSFULLY!")
