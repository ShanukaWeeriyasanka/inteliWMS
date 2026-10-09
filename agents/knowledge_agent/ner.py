"""
Named Entity Recognition (NER) and Intent Analysis for Knowledge Agent.
Extracts SKUs, warehouse coordinates, quantities, dates, and query intents.
"""
from typing import Dict, Any, List, Optional
import re
from agents.knowledge_agent.ontology import (
    get_location_indicators,
    get_unit_indicators,
    get_product_synonyms
)
from utils.logger import StructuredLogger

logger = StructuredLogger(__name__)

# Core SKU Pattern (e.g. SKU-1234, SKU-4521)
SKU_PATTERN = re.compile(r"\b(SKU-\d+)\b", re.IGNORECASE)

DATE_PATTERN = re.compile(
    r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?|today|tomorrow|yesterday)\b",
    re.IGNORECASE
)

# Optional spaCy instance with lazy fallback
_nlp = None

def _get_spacy_model():
    """Lazily loads spaCy model if installed; otherwise returns None."""
    global _nlp
    if _nlp is False:
        return None
    if _nlp is not None:
        return _nlp

    try:
        import spacy
        try:
            _nlp = spacy.load("en_core_web_sm")
        except Exception:
            _nlp = spacy.blank("en")
        return _nlp
    except ImportError:
        _nlp = False
        return None


def _build_dynamic_patterns() -> Dict[str, re.Pattern]:
    """Compiles regex patterns dynamically using ontology indicators."""
    loc_indicators = get_location_indicators()
    unit_indicators = get_unit_indicators()

    loc_regex = r"\b(?:" + "|".join([rf"{w.capitalize()}\s+[A-Z0-9-]+" for w in loc_indicators]) + r")\b"
    unit_regex = r"\b(\d+)\s*(?:" + "|".join(re.escape(u) for u in unit_indicators) + r")?\b"

    return {
        "location": re.compile(loc_regex, re.IGNORECASE),
        "quantity": re.compile(unit_regex, re.IGNORECASE)
    }


def extract_warehouse_entities(text: str) -> Dict[str, Any]:
    """
    Extracts warehouse entities (SKU, locations, quantities, dates) and detects query intent.
    
    Args:
        text: Unstructured user query or operator prompt
        
    Returns:
        Dict adhering to ExtractedEntities schema.
    """
    if not text or not text.strip():
        return {
            "skus": [],
            "locations": [],
            "products": [],
            "quantities": [],
            "dates": [],
            "intent_hint": "unknown",
            "raw_query": ""
        }

    raw = text.strip()
    patterns = _build_dynamic_patterns()

    # 1. Extract SKUs
    skus = list(set(m.upper() for m in SKU_PATTERN.findall(raw)))

    # 2. Extract Warehouse Physical Locations (Aisle X, Shelf Y, Bin Z, Bay B-12)
    locations = list(set(m.strip() for m in patterns["location"].findall(raw)))

    # 3. Extract Quantities
    quantities: List[Dict[str, Any]] = []
    for match in patterns["quantity"].finditer(raw):
        val_str = match.group(1)
        full_match = match.group(0).strip()
        # Avoid capturing location numbers (e.g. '12' in 'Aisle 12') as standalone quantity
        if not re.search(r"(?:Aisle|Shelf|Bin|Bay|Zone|SKU-)\s*" + re.escape(val_str), raw, re.IGNORECASE):
            try:
                quantities.append({
                    "value": int(val_str),
                    "text": full_match
                })
            except ValueError:
                pass

    # 4. Extract Dates
    dates = list(set(m.strip() for m in DATE_PATTERN.findall(raw)))

    # 5. Extract Product Mentions via Synonyms
    synonyms = get_product_synonyms()
    matched_products: List[Dict[str, str]] = []
    lower_raw = raw.lower()
    for canonical, aliases in synonyms.items():
        for alias in aliases:
            if re.search(r"\b" + re.escape(alias) + r"\b", lower_raw):
                matched_products.append({
                    "matched_text": alias,
                    "canonical_name": canonical
                })
                break

    # 6. Intent Classification with Document Precedence
    lower_text = raw.lower()
    doc_keywords = [
        "sop", "procedure", "policy", "safety", "rule", "rules", "protocol", 
        "protocols", "hazard", "manual", "documentation", "guide", "guideline", 
        "guidelines", "regulations", "height limit", "speed limit", 
        "battery spill", "battery acid", "forklift safety", "forklift speed",
        "stacking limit", "pallet limits", "excursion", "limit", "limits"
    ]
    stock_keywords = ["how many", "stock", "quantity", "inventory", "count", "available", "reorder"]
    loc_keywords = [
        "where", "location", "locate", "find", "aisle", "shelf", "bin", "bay", 
        "stored", "kept", "which aisle", "which building", "coords", "position"
    ]

    # If document/procedure/safety words are present, prioritize document_query
    if any(w in lower_text for w in doc_keywords):
        intent_hint = "document_query"
    elif any(w in lower_text for w in stock_keywords):
        intent_hint = "stock_query"
    elif any(w in lower_text for w in loc_keywords) or skus or locations:
        intent_hint = "location_query"
    else:
        intent_hint = "general_query"

    return {
        "skus": skus,
        "locations": locations,
        "products": matched_products,
        "quantities": quantities,
        "dates": dates,
        "intent_hint": intent_hint,
        "raw_query": raw
    }
