"""
Physical & Campus Spatial Location Resolver for Knowledge Agent.
Resolves multi-building campus facilities, fleet vehicles, static infrastructure,
and stored product coordinates across the Colombo Logistics Complex.
"""
from typing import Optional, Dict, Any, List
import re
from sqlalchemy.orm import Session

from database.connection import SessionLocal
from database.models import Product
from agents.knowledge_agent.config import knowledge_config
from agents.knowledge_agent.ontology import get_stop_words, get_product_synonyms
from agents.knowledge_agent.ner import SKU_PATTERN
from agents.knowledge_agent.campus_data import (
    CAMPUS_BUILDINGS,
    CAMPUS_VEHICLES,
    CAMPUS_OBJECTS,
    CAMPUS_SKUS,
    CAMPUS_OVERVIEW
)
from utils.logger import StructuredLogger

logger = StructuredLogger(__name__)


def extract_sku_from_text(text: str) -> Optional[str]:
    """Extracts a SKU pattern from text if present (e.g., 'where is SKU-4521?' -> 'SKU-4521')."""
    if not text:
        return None
    match = SKU_PATTERN.search(text)
    return match.group(1).upper() if match else None


def resolve_facility(query_text: str) -> Optional[Dict[str, Any]]:
    """
    Matches query against Campus Buildings & Facilities (BLD-01 to BLD-07).
    Recognizes names, IDs, numbers, and operational aliases (e.g. 'Cold Vault', 'Building 4', 'Quarantine').
    """
    if not query_text:
        return None
    ql = query_text.lower().strip()

    # Exact or alias matching
    for bld_id, bld in CAMPUS_BUILDINGS.items():
        if bld_id.lower() in ql:
            return bld
        for alias in bld.get("aliases", []):
            pattern = r"\b" + re.escape(alias) + r"\b"
            if re.search(pattern, ql):
                return bld

    # Partial number matching: "building 1", "building 7", "bld 3"
    bld_num_match = re.search(r"\b(?:building|bld)\s*#?\s*([1-7])\b", ql)
    if bld_num_match:
        target_num = bld_num_match.group(1)
        for bld_id, bld in CAMPUS_BUILDINGS.items():
            if bld.get("number") == target_num:
                return bld

    return None


def resolve_vehicle(query_text: str) -> Optional[Dict[str, Any]]:
    """
    Matches query against Campus Fleet Vehicles (FL-01, RT-01, PJ-01, AGV-01, RT-02).
    """
    if not query_text:
        return None
    ql = query_text.lower().strip()

    for veh_id, veh in CAMPUS_VEHICLES.items():
        if veh_id.lower() in ql:
            return veh
        for alias in veh.get("aliases", []):
            pattern = r"\b" + re.escape(alias) + r"\b"
            if re.search(pattern, ql):
                return veh

    return None


def resolve_static_object(query_text: str) -> Optional[Dict[str, Any]]:
    """
    Matches query against Campus Static Infrastructure (60T Scale, Fast Chargers, Airlock, etc.).
    """
    if not query_text:
        return None
    ql = query_text.lower().strip()

    for obj_id, obj in CAMPUS_OBJECTS.items():
        if obj_id.lower() in ql:
            return obj
        for alias in obj.get("aliases", []):
            pattern = r"\b" + re.escape(alias) + r"\b"
            if re.search(pattern, ql):
                return obj

    return None


def resolve_campus_sku(query_text: str) -> Optional[Dict[str, Any]]:
    """
    Matches query against Campus SKUs (SKU-4521, SKU-1088, SKU-7788, SKU-9012, SKU-3301, SKU-5520, SKU-2045).
    """
    if not query_text:
        return None
    ql = query_text.lower().strip()

    # 1. Exact SKU pattern
    detected_sku = extract_sku_from_text(query_text)
    if detected_sku and detected_sku in CAMPUS_SKUS:
        return CAMPUS_SKUS[detected_sku]

    # 2. Alias matching (e.g. 'insulin', 'rf gun', 'semiconductor', 'lithium battery')
    for sku_code, sku_data in CAMPUS_SKUS.items():
        for alias in sku_data.get("aliases", []):
            pattern = r"\b" + re.escape(alias) + r"\b"
            if re.search(pattern, ql):
                return sku_data

    return None


def is_campus_overview_query(query_text: str) -> bool:
    """Checks if user is asking for general campus layout, facilities list, or site plan."""
    if not query_text:
        return False
    ql = query_text.lower().strip()
    overview_patterns = [
        r"\b(campus layout|campus map|site plan|campus plan|warehouse site plan|warehouse layout|warehouse map)\b",
        r"\b(list|all|what|which|how many)\s+(buildings|facilities|warehouses)\b",
        r"\b(how many buildings|how many facilities)\b",
        r"\bbuildings?\s+(this|the|our)\s+warehouse\s+(got|has|have)\b",
        r"\b(tell me about (the )?(campus|warehouse complex)|overview of (the )?(campus|warehouse)|campus overview|warehouse overview)\b",
        r"\bwhat.*stored.*(campus|complex|warehouse)\b"
    ]
    return any(re.search(p, ql) for p in overview_patterns)


def get_location_by_sku(sku: str, db: Optional[Session] = None) -> Optional[Dict[str, Any]]:
    """
    Look up a product's location by its exact SKU across Campus Registry and SQL Database.
    """
    clean_sku = sku.strip().upper()

    # 1. First check rich Campus SKUs registry
    if clean_sku in CAMPUS_SKUS:
        c_item = CAMPUS_SKUS[clean_sku]
        return {
            "sku": c_item["sku"],
            "name": c_item["name"],
            "location": c_item["location"],
            "quantity": c_item["quantity"],
            "building_id": c_item.get("building_id"),
            "building_name": c_item.get("building_name"),
            "category": c_item.get("category"),
            "temperature": c_item.get("temperature"),
            "is_hazardous": c_item.get("is_hazardous", False),
            "found": True
        }

    # 2. Check SQL Product database
    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True

    try:
        product = db.query(Product).filter(Product.sku.ilike(clean_sku)).first()
        if not product:
            return None

        return {
            "sku": product.sku,
            "name": product.name,
            "location": product.location or "Location not assigned",
            "quantity": product.quantity,
            "category": getattr(product, "category", None),
            "found": True
        }
    finally:
        if own_session:
            db.close()


def search_locations_by_name(query_term: str, db: Optional[Session] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Searches products by matching against their names or descriptions.
    """
    search_limit = limit or knowledge_config.LOCATION_SEARCH_LIMIT
    results: List[Dict[str, Any]] = []
    term = query_term.strip().lower()

    # 1. Search Campus SKUs registry
    for sku_code, c_item in CAMPUS_SKUS.items():
        if term in c_item["name"].lower() or any(term in a.lower() for a in c_item.get("aliases", [])):
            results.append({
                "sku": c_item["sku"],
                "name": c_item["name"],
                "location": c_item["location"],
                "quantity": c_item["quantity"],
                "building_id": c_item.get("building_id"),
                "found": True
            })

    # 2. Search SQL Database
    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True

    try:
        products = (
            db.query(Product)
            .filter(Product.name.ilike(f"%{term}%"))
            .limit(search_limit)
            .all()
        )
        for p in products:
            if not any(r["sku"] == p.sku for r in results):
                results.append({
                    "sku": p.sku,
                    "name": p.name,
                    "location": p.location or "Location not assigned",
                    "quantity": p.quantity,
                    "found": True
                })
        return results[:search_limit]
    finally:
        if own_session:
            db.close()


def resolve_location(query: str, db: Optional[Session] = None) -> Dict[str, Any]:
    """
    Main location resolution entrypoint for the Knowledge Agent.
    Handles Campus Facilities, Fleet Vehicles, Static Infrastructure, and Products.
    
    Returns:
        Dict containing resolved status, entity metadata, and formatted operational response.
    """
    if not query or not query.strip():
        return {
            "found": False,
            "message": "Please specify a campus facility, vehicle, equipment, product name, or SKU."
        }

    raw_query = query.strip()

    # ── CASE 1: CAMPUS OVERVIEW / ALL BUILDINGS INQUIRY ──────────────────────
    if is_campus_overview_query(raw_query):
        bld_summary = "\n".join([
            f"• {b['name']} ({b['id']}): {b['category']} — Capacity: {b['capacity']}, Status: {b['status']}"
            for b in CAMPUS_BUILDINGS.values()
        ])
        msg = (
            f"**{CAMPUS_OVERVIEW['name']} ({CAMPUS_OVERVIEW['hub_code']})**\n\n"
            f"{CAMPUS_OVERVIEW['description']}\n\n"
            f"**Campus Facilities Breakdown (7 Buildings):**\n"
            f"{bld_summary}\n\n"
            f"Gate Origin: Gate 1 at South-West perimeter."
        )
        return {
            "found": True,
            "entity_type": "campus_overview",
            "complex_id": CAMPUS_OVERVIEW["complex_id"],
            "total_buildings": CAMPUS_OVERVIEW["total_buildings"],
            "buildings": list(CAMPUS_BUILDINGS.values()),
            "formatted_message": msg
        }

    # ── CASE 2: STATIC INFRASTRUCTURE / CAMPUS OBJECT RESOLUTION ─────────────
    obj = resolve_static_object(raw_query)
    if obj:
        coords = obj.get("coords", {})
        msg = (
            f"**{obj['name']} ({obj['id']})**\n"
            f"• **Facility:** {obj['building_name']}\n"
            f"• **Location Coordinates:** X:{coords.get('x')}, Y:{coords.get('y')}\n"
            f"• **Specifications:** {obj['specifications']}\n"
            f"• **Operational Summary:** {obj['description']}"
        )
        logger.log_event("KNOWLEDGE_OBJECT_LOCATED", {"object_id": obj["id"], "name": obj["name"]})
        return {
            "found": True,
            "entity_type": "campus_infrastructure",
            "object_id": obj["id"],
            "name": obj["name"],
            "building_id": obj.get("building_id"),
            "building_name": obj["building_name"],
            "coords": coords,
            "formatted_message": msg
        }

    # ── CASE 3: CAMPUS FLEET VEHICLE RESOLUTION ──────────────────────────────
    vehicle = resolve_vehicle(raw_query)
    if vehicle:
        coords = vehicle.get("coords", {})
        msg = (
            f"**{vehicle['name']} ({vehicle['id']})**\n"
            f"• **Type:** {vehicle['type']}\n"
            f"• **Current Location:** {vehicle['nearest_facility']} (Map Coords: X:{coords.get('x')}, Y:{coords.get('y')})\n"
            f"• **Status:** {vehicle['status']}\n"
            f"• **Battery SoC:** {vehicle['battery_soc']}\n"
            f"• **Operator:** {vehicle['operator']}\n"
            f"• **Speed Limit:** {vehicle['speed_limit']}\n"
            f"• **Operational Details:** {vehicle['description']}"
        )
        logger.log_event("KNOWLEDGE_VEHICLE_LOCATED", {"vehicle_id": vehicle["id"], "name": vehicle["name"]})
        return {
            "found": True,
            "entity_type": "campus_vehicle",
            "vehicle_id": vehicle["id"],
            "name": vehicle["name"],
            "type": vehicle["type"],
            "status": vehicle["status"],
            "nearest_facility": vehicle["nearest_facility"],
            "battery_soc": vehicle["battery_soc"],
            "coords": coords,
            "formatted_message": msg
        }

    # ── CASE 4: CAMPUS BUILDING / FACILITY RESOLUTION ────────────────────────
    facility = resolve_facility(raw_query)
    if facility:
        dock = facility.get("dock_coords", {})
        rect = facility.get("rect", {})
        msg = (
            f"**{facility['name']} ({facility['id']})**\n"
            f"• **Category:** {facility['category']}\n"
            f"• **Status:** {facility['status']}\n"
            f"• **Capacity:** {facility['capacity']} ({facility['lots']})\n"
            f"• **MHE & Handling:** {facility['mhe_active']}\n"
            f"• **Loading Docks:** {facility['dock_doors']} (Coordinates: X:{dock.get('x')}, Y:{dock.get('y')})\n"
            f"• **Stored Inventory:** {', '.join(facility.get('key_skus', []))}\n"
            f"• **Safety Note:** {facility['safety_notes']}"
        )
        logger.log_event("KNOWLEDGE_FACILITY_LOCATED", {"building_id": facility["id"], "name": facility["name"]})
        return {
            "found": True,
            "entity_type": "campus_facility",
            "building_id": facility["id"],
            "name": facility["name"],
            "category": facility["category"],
            "status": facility["status"],
            "capacity": facility["capacity"],
            "lots": facility["lots"],
            "mhe_active": facility["mhe_active"],
            "dock_coords": dock,
            "rect": rect,
            "formatted_message": msg
        }

    # ── CASE 5: CAMPUS & SQL PRODUCT SKU RESOLUTION ──────────────────────────
    campus_sku = resolve_campus_sku(raw_query)
    if campus_sku:
        msg = (
            f"{campus_sku['name']} ({campus_sku['sku']}) is stored in **{campus_sku['building_name']}** at {campus_sku['location']}. "
            f"Current stock: {campus_sku['quantity']} units ({campus_sku.get('temperature', 'Standard Monitored')})."
        )
        logger.log_event("KNOWLEDGE_CAMPUS_SKU_FOUND", {"sku": campus_sku["sku"], "building": campus_sku["building_name"]})
        return {
            "found": True,
            "entity_type": "product_sku",
            "sku": campus_sku["sku"],
            "name": campus_sku["name"],
            "building_id": campus_sku["building_id"],
            "building_name": campus_sku["building_name"],
            "location": campus_sku["location"],
            "quantity": campus_sku["quantity"],
            "category": campus_sku["category"],
            "temperature": campus_sku["temperature"],
            "formatted_message": msg
        }

    # ── CASE 6: DATABASE EXACT SKU RESOLUTION ────────────────────────────────
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
                "entity_type": "product_sku",
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

    # ── CASE 7: NATURAL LANGUAGE & SYNONYM SEARCH ────────────────────────────
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
            "formatted_message": (
                f"Could not find any campus facility, vehicle, or warehouse items matching '{search_term}'. "
                f"Please check the SKU, building name (e.g. Building 1 to 7, Cold Vault), or equipment ID."
            )
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
            "entity_type": "product_sku",
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
