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


from agents.knowledge_agent.spatial_registry import (
    RACKS,
    EQUIPMENT_ASSETS,
    SPECIAL_ZONES,
    PRODUCT_SPATIAL_MAP,
    ORIGIN_POINTS,
    compute_waypoint_route
)



def _resolve_rack_query(query: str, start_origin: str = "DOCK-01") -> Optional[Dict[str, Any]]:
    """Resolves queries like 'where is rack no 4', 'where is rack 4 located'."""
    match = re.search(r"\brack(?:\s*(?:no\.?|number))?\s*(\d+)\b", query, re.IGNORECASE)
    if not match:
        return None
    rack_num = int(match.group(1))
    rack_key = f"RACK-{rack_num:02d}"
    rack_data = RACKS.get(rack_key)
    if not rack_data:
        return {
            "found": False,
            "formatted_message": f"Rack #{rack_num} was not found in the warehouse layout (Valid: Rack 1 to 20)."
        }

    start_pt = ORIGIN_POINTS.get(start_origin, ORIGIN_POINTS["DOCK-01"])
    waypoints = compute_waypoint_route(
        start_point=start_pt,
        dest_coords={"x": rack_data["x"], "y": rack_data["y"], "z": rack_data["z"]},
        dest_floor=rack_data["floor"]
    )

    msg = (
        f"📍 Rack #{rack_num} is located on Floor {rack_data['floor']} in {rack_data['zone']}, {rack_data['aisle']} "
        f"(UCID: {rack_data['ucid']}). Destination route highlighted on 3D Map."
    )
    return {
        "found": True,
        "target_type": "rack",
        "name": f"Rack #{rack_num}",
        "ucid": rack_data["ucid"],
        "floor": rack_data["floor"],
        "coordinates": {"x": rack_data["x"], "y": rack_data["y"], "z": rack_data["z"]},
        "dimensions": {"w": rack_data["w"], "h": rack_data["h"], "d": rack_data["d"]},
        "zone": rack_data["zone"],
        "aisle": rack_data["aisle"],
        "waypoints": waypoints,
        "start_origin": start_pt["name"],
        "formatted_message": msg
    }


def _resolve_equipment_query(query: str) -> Optional[Dict[str, Any]]:
    """Resolves queries like 'where are the forklifts', 'forklift locations', 'reach trucks'."""
    lower_q = query.lower()
    has_equipment = any(k in lower_q for k in ["forklift", "reach truck", "pallet jack", "mhe", "equipment"])
    has_loc_intent = any(k in lower_q for k in ["where", "location", "park", "station", "find", "fleet", "available"]) or "forklifts" in lower_q
    is_safety_doc = any(k in lower_q for k in ["speed", "safety", "protocol", "rule", "sop", "limit", "ppe", "charging rules"])
    
    if not (has_equipment and has_loc_intent) or is_safety_doc:
        return None

    # Check if asking for a specific unit
    fl_num_match = re.search(r"forklift\s*(?:#|no\.?|number)?\s*(\d+)", lower_q)
    if fl_num_match:
        target_id = f"EQ-FL-{int(fl_num_match.group(1)):02d}"
        for eq in EQUIPMENT_ASSETS:
            if eq["id"] == target_id:
                msg = f"🚜 {eq['name']} is parked at {eq['zone']} (UCID: {eq['ucid']}). Status: {eq['status']}."
                return {
                    "found": True,
                    "target_type": "equipment_single",
                    "name": eq["name"],
                    "ucid": eq["ucid"],
                    "floor": eq["floor"],
                    "coordinates": eq["coordinates"],
                    "status": eq["status"],
                    "all_pins": [eq],
                    "formatted_message": msg
                }

    # Otherwise return all equipment pins
    equipment_names = ", ".join([f"{eq['name']} ({eq['zone']})" for eq in EQUIPMENT_ASSETS])
    msg = (
        f"🚜 Active Warehouse Material Handling Equipment (MHE):\n"
        f"• {len(EQUIPMENT_ASSETS)} units parked at designated MHE stations:\n"
        f"  - {equipment_names}\n"
        f"All static equipment pins are spotlighted on the 3D Map."
    )
    return {
        "found": True,
        "target_type": "equipment_fleet",
        "name": "Warehouse MHE Fleet",
        "floor": 1,
        "all_pins": EQUIPMENT_ASSETS,
        "formatted_message": msg
    }



def _resolve_special_zone_query(query: str, start_origin: str = "DOCK-01") -> Optional[Dict[str, Any]]:
    """Resolves queries like 'where is bay 11', 'quarantine', 'chilled vault', 'cold storage'."""
    lower_q = query.lower()
    target_zone = None
    if any(k in lower_q for k in ["bay 11", "bay-11", "quarantine", "rma hold"]):
        target_zone = SPECIAL_ZONES["BAY-11"]
    elif any(k in lower_q for k in ["cold storage", "chilled vault", "freezer", "chiller"]):
        target_zone = SPECIAL_ZONES["COLD-VAULT"]
    elif any(k in lower_q for k in ["mhe depot", "charging station", "battery charging"]):
        target_zone = SPECIAL_ZONES["MHE-DEPOT"]

    if not target_zone:
        return None

    start_pt = ORIGIN_POINTS.get(start_origin, ORIGIN_POINTS["DOCK-01"])
    waypoints = compute_waypoint_route(
        start_point=start_pt,
        dest_coords=target_zone["coordinates"],
        dest_floor=target_zone["floor"]
    )

    msg = (
        f"📍 {target_zone['name']} is located on Floor {target_zone['floor']} "
        f"(UCID: {target_zone['ucid']}). Purpose: {target_zone['description']}. Route displayed on 3D Map."
    )
    return {
        "found": True,
        "target_type": "special_zone",
        "name": target_zone["name"],
        "ucid": target_zone["ucid"],
        "floor": target_zone["floor"],
        "coordinates": target_zone["coordinates"],
        "dimensions": {"w": target_zone["w"], "h": target_zone["h"], "d": target_zone["d"]},
        "waypoints": waypoints,
        "start_origin": start_pt["name"],
        "formatted_message": msg
    }


def resolve_location(query: str, db: Optional[Session] = None, start_origin: str = "DOCK-01") -> Dict[str, Any]:
    """
    Main location resolution entrypoint for the Knowledge Agent.
    Handles physical racks, equipment fleets, special zones, and SKU lookups.
    
    Returns:
        Dict containing resolved status, coordinates, waypoints, and formatted message.
    """
    if not query or not query.strip():
        return {
            "found": False,
            "message": "Please specify a product name, rack number, or warehouse equipment."
        }

    raw_query = query.strip()

    # 1. Specialized: Rack Number Lookup ("where is rack no 4", "rack 16")
    rack_result = _resolve_rack_query(raw_query, start_origin=start_origin)
    if rack_result:
        return rack_result

    # 2. Specialized: Equipment Fleet Lookup ("where are the forklifts")
    equipment_result = _resolve_equipment_query(raw_query)
    if equipment_result:
        return equipment_result

    # 3. Specialized: Key Warehouse Zones ("where is bay 11", "cold storage")
    zone_result = _resolve_special_zone_query(raw_query, start_origin=start_origin)
    if zone_result:
        return zone_result

    # 4. Check Product Catalog against Spatial Map first (e.g., SKU-4521, SKU-1088)
    detected_sku = extract_sku_from_text(raw_query)
    if detected_sku and detected_sku in PRODUCT_SPATIAL_MAP:
        pmap = PRODUCT_SPATIAL_MAP[detected_sku]
        rack_data = RACKS.get(pmap.get("rack_id"))
        if rack_data:
            start_pt = ORIGIN_POINTS.get(start_origin, ORIGIN_POINTS["DOCK-01"])
            waypoints = compute_waypoint_route(
                start_point=start_pt,
                dest_coords={"x": rack_data["x"], "y": rack_data["y"], "z": rack_data["z"]},
                dest_floor=rack_data["floor"]
            )
            msg = (
                f"{pmap['name']} ({detected_sku}) is located on Floor {rack_data['floor']} in "
                f"{rack_data['zone']}, {rack_data['aisle']}, {rack_data['id']} ({pmap['shelf']}, {pmap['bin']}). "
                f"Stock: {pmap['quantity']} units. (UCID: {rack_data['ucid']}). Route highlighted on 3D Map."
            )
            return {
                "found": True,
                "target_type": "product",
                "sku": detected_sku,
                "name": pmap["name"],
                "ucid": rack_data["ucid"],
                "floor": rack_data["floor"],
                "coordinates": {"x": rack_data["x"], "y": rack_data["y"], "z": rack_data["z"]},
                "rack": rack_data["id"],
                "shelf": pmap["shelf"],
                "bin": pmap["bin"],
                "quantity": pmap["quantity"],
                "waypoints": waypoints,
                "start_origin": start_pt["name"],
                "formatted_message": msg
            }

    # 5. Database Product Lookup (Existing Relational DB fallback)
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
                "target_type": "database_product",
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

    # 6. Natural Language Product Search using Ontology Synonyms
    clean_text = re.sub(r"[^\w\s-]", " ", raw_query)
    stop_words = get_stop_words()
    stop_pattern = r"\b(" + "|".join(re.escape(w) for w in stop_words) + r")\b"
    cleaned = re.sub(stop_pattern, "", clean_text, flags=re.IGNORECASE).strip()

    search_term = cleaned if len(cleaned) >= 2 else raw_query
    synonyms = get_product_synonyms()
    resolved_synonym = None
    lower_query = raw_query.lower()
    for canonical_term, alias_list in synonyms.items():
        if any(alias in lower_query or alias in search_term.lower() for alias in alias_list):
            resolved_synonym = canonical_term
            break

    # Check if synonym maps to our spatial product map (e.g. rf gun -> barcode scanner -> SKU-4521)
    if resolved_synonym == "Barcode Scanner" and "SKU-4521" in PRODUCT_SPATIAL_MAP:
        pmap = PRODUCT_SPATIAL_MAP["SKU-4521"]
        rack_data = RACKS[pmap["rack_id"]]
        start_pt = ORIGIN_POINTS.get(start_origin, ORIGIN_POINTS["DOCK-01"])
        waypoints = compute_waypoint_route(
            start_point=start_pt,
            dest_coords={"x": rack_data["x"], "y": rack_data["y"], "z": rack_data["z"]},
            dest_floor=rack_data["floor"]
        )
        msg = (
            f"Barcode Scanner (SKU-4521) is located on Floor {rack_data['floor']} in {rack_data['zone']}, "
            f"{rack_data['aisle']}, {rack_data['id']}. Stock: {pmap['quantity']} units. Route highlighted on 3D Map."
        )
        return {
            "found": True,
            "target_type": "product",
            "sku": "SKU-4521",
            "name": pmap["name"],
            "ucid": rack_data["ucid"],
            "floor": rack_data["floor"],
            "coordinates": {"x": rack_data["x"], "y": rack_data["y"], "z": rack_data["z"]},
            "rack": rack_data["id"],
            "waypoints": waypoints,
            "start_origin": start_pt["name"],
            "formatted_message": msg
        }

    # Search DB
    matches = search_locations_by_name(search_term, db=db)
    if not matches and resolved_synonym:
        matches = search_locations_by_name(resolved_synonym, db=db)

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
        return {
            "found": True,
            "target_type": "database_product",
            "sku": item["sku"],
            "name": item["name"],
            "location": item["location"],
            "quantity": item["quantity"],
            "formatted_message": msg
        }

    items_list = ", ".join([f"{m['name']} ({m['sku']} at {m['location']})" for m in matches])
    return {
        "found": True,
        "multiple": True,
        "matches": matches,
        "formatted_message": f"Found multiple matching items: {items_list}."
    }

