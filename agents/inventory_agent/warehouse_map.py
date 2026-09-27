"""
Warehouse Spatial Map and Layout Engine for IntelliWMS Inventory Agent.

Models the 2D/2.5D physical layout of the warehouse:
- 14 High-Bay Rack Aisles (A1 to A14)
- 4 Vertical Storage Tiers (A=Floor, B=Mid-Low, C=Mid-High, D=Heavy High-Bay)
- Storage Zones (Zone A: Consumables, Zone B: Electronics, Zone C: Bulk Pallets, Zone D: Heavy Hazmat)
- Active AGV Fleet Runways and Charging Docks

Spatial coordinates (aisle, shelf, tier, bay, occupancy_pct, temperature) are read
from the live Product DB table. Static fallback data is kept for aisles not yet
populated in the database.
"""
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session

from agents.inventory_agent.schemas import StockItemInfo
from database.connection import SessionLocal
from database.models import Product

# ── Static fallback (used only for SKUs not in DB) ────────────────────────────
WAREHOUSE_LOCATIONS_MAP: Dict[str, Dict[str, Any]] = {
    "SKU-4521": {
        "name": "Wireless Barcode Scanner",
        "category": "Electronics & Tech",
        "aisle": 12, "shelf": "B3", "bay": "Bay 04", "tier": "B",
        "zone": "Zone B - Electronics & Tech",
        "location_full": "Aisle 12, Shelf B3, Bay 04",
        "occupancy_pct": 78.5, "weight_kg": 0.45,
        "temperature": "20.2 °C (Climate Monitored)",
        "cycle_count": "Tomorrow, 08:00 AM", "rack_color": "#f59e0b",
    },
    "SKU-7788": {
        "name": "Thermal Label Printer",
        "category": "Dispatch Equipment",
        "aisle": 5, "shelf": "A1", "bay": "Bay 02", "tier": "A",
        "zone": "Zone A - Dispatch Packing",
        "location_full": "Aisle 5, Shelf A1, Bay 02",
        "occupancy_pct": 45.0, "weight_kg": 3.80,
        "temperature": "21.0 °C (Ambient)",
        "cycle_count": "In 3 Days", "rack_color": "#3b82f6",
    },
    "SKU-9012": {
        "name": "Heavy Duty Pallet Wrap",
        "category": "Packaging Consumables",
        "aisle": 3, "shelf": "C2", "bay": "Bay 08", "tier": "C",
        "zone": "Zone C - Bulk Pallet Storage",
        "location_full": "Aisle 3, Shelf C2, Bay 08",
        "occupancy_pct": 12.0, "weight_kg": 22.0,
        "temperature": "18.5 °C (Standard)",
        "cycle_count": "Immediate Physical Audit", "rack_color": "#ef4444",
    },
    "SKU-1088": {
        "name": "Thermal Industrial Label Rolls",
        "category": "Consumables",
        "aisle": 1, "shelf": "A3", "bay": "Bay A-03", "tier": "A",
        "zone": "Zone A - High Turn Consumables",
        "location_full": "Aisle 1, Bay A-03, Shelf A3",
        "occupancy_pct": 85.0, "weight_kg": 1.20,
        "temperature": "20.5 °C (Climate Controlled)",
        "cycle_count": "Weekly, Friday", "rack_color": "#10b981",
    },
    "SKU-2045": {
        "name": "Heavy Duty Forklift Battery Lithium",
        "category": "Heavy Hazmat / Power",
        "aisle": 4, "shelf": "B12", "bay": "Bay B-12", "tier": "B",
        "zone": "Zone D - Heavy Machinery & Batteries",
        "location_full": "Aisle 4, Bay B-12, Shelf B12",
        "occupancy_pct": 68.0, "weight_kg": 420.0,
        "temperature": "19.0 °C (Hazmat Thermal Guarded)",
        "cycle_count": "Daily Shift Check", "rack_color": "#8b5cf6",
    },
}

# ── Static aisle layout metadata ─────────────────────────────────────────────
AISLES_METADATA = [
    {"aisle": 1,  "zone": "Zone A", "name": "Consumables & Labels",         "primary_sku": "SKU-1088", "occupancy": 85},
    {"aisle": 2,  "zone": "Zone A", "name": "Packing Cartons",              "primary_sku": None,        "occupancy": 64},
    {"aisle": 3,  "zone": "Zone C", "name": "Pallet Shrink Wrap",           "primary_sku": "SKU-9012", "occupancy": 12},
    {"aisle": 4,  "zone": "Zone D", "name": "Machinery Spares & Batteries", "primary_sku": "SKU-2045", "occupancy": 68},
    {"aisle": 5,  "zone": "Zone A", "name": "Printers & Enclosure Tech",    "primary_sku": "SKU-7788", "occupancy": 45},
    {"aisle": 6,  "zone": "Zone C", "name": "Bulk Storage North",           "primary_sku": None,        "occupancy": 72},
    {"aisle": 7,  "zone": "Zone C", "name": "Bulk Storage Central",         "primary_sku": None,        "occupancy": 58},
    {"aisle": 8,  "zone": "Zone C", "name": "Bulk Storage South",           "primary_sku": None,        "occupancy": 90},
    {"aisle": 9,  "zone": "Zone B", "name": "Staging Electronics",          "primary_sku": None,        "occupancy": 33},
    {"aisle": 10, "zone": "Zone B", "name": "Cabling & Peripherals",        "primary_sku": None,        "occupancy": 41},
    {"aisle": 11, "zone": "Zone B", "name": "RF Handheld Terminals",        "primary_sku": None,        "occupancy": 60},
    {"aisle": 12, "zone": "Zone B", "name": "Barcode Scanning Hardware",    "primary_sku": "SKU-4521", "occupancy": 79},
    {"aisle": 13, "zone": "Zone D", "name": "Maintenance Tools",            "primary_sku": None,        "occupancy": 50},
    {"aisle": 14, "zone": "Zone D", "name": "Overhead Heavy Racks",         "primary_sku": None,        "occupancy": 74},
]

# ── Active AGV Fleet (hardware state — not stored in products DB) ─────────────
AGV_FLEET = [
    {"id": "AGV-01", "name": "Haulix-NR5251", "status": "Available",           "battery": 72, "lane": "Runway 01", "assigned_sku": "SKU-1088"},
    {"id": "AGV-04", "name": "Haulix-NR9864", "status": "In Transit",          "battery": 34, "lane": "Runway 03", "assigned_sku": "SKU-4521"},
    {"id": "AGV-08", "name": "Haulix-NR5721", "status": "Warning/Maintenance", "battery": 19, "lane": "Runway 03", "assigned_sku": "SKU-2045"},
]


# ── Live DB query helpers ─────────────────────────────────────────────────────

def get_sku_map_coordinates(sku: str, db: Optional[Session] = None) -> Optional[Dict[str, Any]]:
    """
    Return spatial map data for a SKU — reads from the live DB Product row.
    Falls back to the static WAREHOUSE_LOCATIONS_MAP if the row is missing.
    """
    own = db is None
    if own:
        db = SessionLocal()
    try:
        prod = db.query(Product).filter(Product.sku.ilike(sku.strip())).first()
        if prod and prod.aisle is not None:
            return {
                "name": prod.name,
                "category": prod.category or "General",
                "aisle": prod.aisle,
                "shelf": prod.shelf,
                "bay": prod.bay,
                "tier": prod.tier,
                "location_full": prod.location or f"Aisle {prod.aisle}",
                "occupancy_pct": float(prod.occupancy_pct) if prod.occupancy_pct is not None else 50.0,
                "weight_kg": float(prod.weight_kg) if prod.weight_kg is not None else 1.0,
                "temperature": prod.temperature or "20.0 °C Ambient",
            }
    except Exception:
        pass
    finally:
        if own:
            db.close()
    # Static fallback
    return WAREHOUSE_LOCATIONS_MAP.get(sku.strip().upper())


def get_full_warehouse_layout(db: Optional[Session] = None) -> Dict[str, Any]:
    """
    Return the complete warehouse layout, merging live DB product spatial data
    into the static aisle/AGV structure.
    """
    own = db is None
    if own:
        db = SessionLocal()
    live_locations: Dict[str, Any] = {}
    avg_occupancy = 68.4
    try:
        products = db.query(Product).all()
        for p in products:
            if p.aisle is not None:
                live_locations[p.sku] = {
                    "name": p.name,
                    "category": p.category or "General",
                    "aisle": p.aisle,
                    "shelf": p.shelf,
                    "bay": p.bay,
                    "tier": p.tier,
                    "location_full": p.location or f"Aisle {p.aisle}",
                    "occupancy_pct": float(p.occupancy_pct) if p.occupancy_pct is not None else 50.0,
                    "weight_kg": float(p.weight_kg) if p.weight_kg is not None else 1.0,
                    "temperature": p.temperature or "20.0 °C Ambient",
                }
        if live_locations:
            avg_occupancy = round(
                sum(v["occupancy_pct"] for v in live_locations.values()) / len(live_locations), 1
            )
    except Exception:
        pass
    finally:
        if own:
            db.close()

    # Merge: DB data takes priority; static map fills any gaps
    merged_locations = {**WAREHOUSE_LOCATIONS_MAP, **live_locations}

    return {
        "aisles": AISLES_METADATA,
        "locations": merged_locations,
        "agv_fleet": AGV_FLEET,
        "metrics": {
            "total_aisles": 14,
            "overall_occupancy_pct": avg_occupancy,
            "active_robots": len(AGV_FLEET),
            "ambient_temp_avg": "20.1 °C",
            "daily_throughput_orders": 345,
        },
    }

