"""
Physical Location Resolver for Knowledge Agent.
Resolves product physical coordinates in the warehouse via exact SKU or fuzzy name lookup.
"""
from typing import Optional, Dict, Any, List
import re
from sqlalchemy.orm import Session

from database.connection import SessionLocal
from database.models import Product
from agents.knowledge_agent.config import knowledge_config
from agents.knowledge_agent.ontology import get_stop_words, get_product_synonyms
from agents.knowledge_agent.ner import SKU_PATTERN
from utils.logger import StructuredLogger

logger = StructuredLogger(__name__)


def extract_sku_from_text(text: str) -> Optional[str]:
    """Extracts a SKU pattern from text if present (e.g., 'where is SKU-4521?' -> 'SKU-4521')."""
    if not text:
        return None
    match = SKU_PATTERN.search(text)
    return match.group(1).upper() if match else None


def get_location_by_sku(sku: str, db: Optional[Session] = None) -> Optional[Dict[str, Any]]:
    """
    Look up a product's location by its exact SKU.
    
    Args:
        sku: The SKU string (e.g., 'SKU-4521')
        db: Optional SQLAlchemy session
        
    Returns:
        Dict with product location info or None if not found.
    """
    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True

    try:
        clean_sku = sku.strip().upper()
        product = db.query(Product).filter(Product.sku.ilike(clean_sku)).first()
        if not product:
            return None

        return {
            "sku": product.sku,
            "name": product.name,
            "location": product.location or "Location not assigned",
            "quantity": product.quantity,
            "found": True
        }
    finally:
        if own_session:
            db.close()


def search_locations_by_name(query_term: str, db: Optional[Session] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Searches products by matching against their names or descriptions.
    
    Args:
        query_term: Keyword or partial product name (e.g., 'scanner', 'printer')
        db: Optional SQLAlchemy session
        limit: Max search results (defaults to knowledge_config.LOCATION_SEARCH_LIMIT)
    """
    search_limit = limit or knowledge_config.LOCATION_SEARCH_LIMIT
    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True

    try:
        term = query_term.strip()
        products = (
            db.query(Product)
            .filter(Product.name.ilike(f"%{term}%"))
            .limit(search_limit)
            .all()
        )
        return [
            {
                "sku": p.sku,
                "name": p.name,
                "location": p.location or "Location not assigned",
                "quantity": p.quantity,
                "found": True
            }
            for p in products
        ]
    finally:
        if own_session:
            db.close()


def resolve_location(query: str, db: Optional[Session] = None) -> Dict[str, Any]:
    """
    Main location resolution entrypoint for the Knowledge Agent.
    Handles explicit SKUs and natural language product lookups.
    
    Returns:
        Dict containing resolved status, product details, and a formatted response.
    """
    if not query or not query.strip():
        return {
            "found": False,
            "message": "Please specify a product name or SKU to check its warehouse location."
        }

    raw_query = query.strip()
    
    # 1. Check if query contains an explicit SKU code
    detected_sku = extract_sku_from_text(raw_query)
    if detected_sku:
        result = get_location_by_sku(detected_sku, db=db)
        if result:
            msg = (
                f"{result['name']} ({result['sku']}) is stored at {result['location']}. "
                f"Current stock: {result['quantity']} units."
            )
            logger.log_event("KNOWLEDGE_LOCATION_FOUND", {"sku": detected_sku, "location": result["location"]})
            return {
                "found": True,
                "sku": result["sku"],
                "name": result["name"],
                "location": result["location"],
                "quantity": result["quantity"],
                "formatted_message": msg
            }
        else:
            return {
                "found": False,
                "sku": detected_sku,
                "formatted_message": f"Product with SKU '{detected_sku}' was not found in the warehouse database."
            }

    # 2. Clean query using centralized stop words
    clean_text = re.sub(r"[^\w\s-]", " ", raw_query)
    stop_words = get_stop_words()
    stop_pattern = r"\b(" + "|".join(re.escape(w) for w in stop_words) + r")\b"
    cleaned = re.sub(stop_pattern, "", clean_text, flags=re.IGNORECASE).strip()

    search_term = cleaned if len(cleaned) >= 2 else raw_query
    
    # Check ontology for product synonyms
    synonyms = get_product_synonyms()
    resolved_synonym = None
    lower_query = raw_query.lower()
    for canonical_term, alias_list in synonyms.items():
        if any(alias in lower_query or alias in search_term.lower() for alias in alias_list):
            resolved_synonym = canonical_term
            break

    # Attempt 1: search by cleaned term
    matches = search_locations_by_name(search_term, db=db)

    # Attempt 2: search by ontology canonical synonym
    if not matches and resolved_synonym:
        matches = search_locations_by_name(resolved_synonym, db=db)

    # Attempt 3: search by largest significant singularized keyword
    if not matches and (" " in search_term or search_term.endswith("s")):
        words = [w.rstrip("s") for w in search_term.split() if len(w) >= 3]
        for w in words:
            matches = search_locations_by_name(w, db=db)
            if matches:
                break

    if not matches:
        return {
            "found": False,
            "query": raw_query,
            "formatted_message": f"Could not find any warehouse items matching '{search_term}'. Please check the SKU or name."
        }

    if len(matches) == 1:
        item = matches[0]
        msg = (
            f"{item['name']} ({item['sku']}) is stored at {item['location']}. "
            f"Current stock: {item['quantity']} units."
        )
        logger.log_event("KNOWLEDGE_LOCATION_FOUND", {"sku": item["sku"], "location": item["location"]})
        return {
            "found": True,
            "sku": item["sku"],
            "name": item["name"],
            "location": item["location"],
            "quantity": item["quantity"],
            "formatted_message": msg
        }

    # Multiple matches found
    items_list = ", ".join([f"{m['name']} ({m['sku']} at {m['location']})" for m in matches])
    return {
        "found": True,
        "multiple": True,
        "matches": matches,
        "formatted_message": f"Found multiple matching items: {items_list}."
    }
