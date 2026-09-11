"""
Warehouse Ontology Provider for Knowledge Agent.
Centralizes domain vocabulary, synonyms, stopwords, and indicators.
"""
import json
from typing import Dict, Any, List
from agents.knowledge_agent.config import knowledge_config
from utils.logger import StructuredLogger

logger = StructuredLogger(__name__)

# In-memory cache
_ontology_cache: Dict[str, Any] = {}

DEFAULT_STOP_WORDS = [
    "where", "is", "are", "the", "located", "stored", "kept", "find", 
    "location", "of", "item", "items", "product", "products", "please", 
    "can", "you", "tell", "me", "show", "check", "lookup", "give"
]

DEFAULT_LOCATION_INDICATORS = [
    "aisle", "shelf", "bin", "bay", "zone", "rack", "tier"
]

DEFAULT_UNIT_INDICATORS = [
    "units", "pcs", "pieces", "boxes", "cartons", "pallets", "skids", "packs", "crates"
]

DEFAULT_SYNONYMS = {
    "scanner": ["barcode scanner", "rf gun", "handheld scanner", "scanner", "readers"],
    "printer": ["label printer", "thermal printer", "zebra printer", "printer"],
    "pallet wrap": ["stretch film", "plastic wrap", "pallet wrap", "shrink wrap", "wrapping"]
}


def get_ontology() -> Dict[str, Any]:
    """Loads and caches warehouse ontology definitions from external JSON."""
    global _ontology_cache
    if _ontology_cache:
        return _ontology_cache

    path = knowledge_config.ONTOLOGY_PATH
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                _ontology_cache = json.load(f)
                return _ontology_cache
        except Exception as e:
            logger.log_event("ONTOLOGY_LOAD_ERROR", {"path": str(path), "error": str(e)})

    # Fallback to compiled defaults
    _ontology_cache = {
        "stop_words": DEFAULT_STOP_WORDS,
        "location_indicators": DEFAULT_LOCATION_INDICATORS,
        "unit_indicators": DEFAULT_UNIT_INDICATORS,
        "product_synonyms": DEFAULT_SYNONYMS
    }
    return _ontology_cache


def get_stop_words() -> List[str]:
    """Returns warehouse domain stop words."""
    return get_ontology().get("stop_words", DEFAULT_STOP_WORDS)


def get_product_synonyms() -> Dict[str, List[str]]:
    """Returns canonical product names mapped to common floor aliases."""
    return get_ontology().get("product_synonyms", DEFAULT_SYNONYMS)


def get_location_indicators() -> List[str]:
    """Returns location keywords (aisle, shelf, bin, bay, etc.)."""
    return get_ontology().get("location_indicators", DEFAULT_LOCATION_INDICATORS)


def get_unit_indicators() -> List[str]:
    """Returns unit measurement keywords (units, boxes, pallets, etc.)."""
    return get_ontology().get("unit_indicators", DEFAULT_UNIT_INDICATORS)
