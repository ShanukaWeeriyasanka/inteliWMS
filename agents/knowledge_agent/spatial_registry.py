"""
Warehouse Spatial Registry & 3D Digital Twin Layout for IntelliWMS.
Maintains hierarchical Universal Coordinate IDs (UCIDs), 3D Cartesian coordinates,
racks, MHE equipment parking spots, and wayfinding corridor graphs.
"""
from typing import Dict, Any, List, Optional
import math

FACILITY_ID = "WH-01"
FACILITY_NAME = "IntelliWMS Distribution Center"

# Origin Reference Points (Starting Anchors for Wayfinding)
ORIGIN_POINTS = {
    "DOCK-01": {
        "id": "DOCK-01",
        "name": "Receiving Dock Door 1",
        "floor": 1,
        "coordinates": {"x": -22, "y": 0, "z": -22},
        "description": "Inbound container unloading bay"
    },
    "DOCK-02": {
        "id": "DOCK-02",
        "name": "Receiving Dock Door 2",
        "floor": 1,
        "coordinates": {"x": -14, "y": 0, "z": -22},
        "description": "Inbound LTL freight dock"
    },
    "DOCK-04": {
        "id": "DOCK-04",
        "name": "Dispatch Dock Door 4",
        "floor": 1,
        "coordinates": {"x": 14, "y": 0, "z": -22},
        "description": "Outbound courier dispatch"
    },
    "DESK-MAIN": {
        "id": "DESK-MAIN",
        "name": "Main Dispatch Desk",
        "floor": 1,
        "coordinates": {"x": -18, "y": 0, "z": -12},
        "description": "Supervisor console and RF scanner pickup"
    },
    "LIFT-MEZZ": {
        "id": "LIFT-MEZZ",
        "name": "Mezzanine Freight Lift",
        "floor": 1,
        "coordinates": {"x": 0, "y": 0, "z": -8},
        "description": "Vertical access to Floor 2 Mezzanine"
    }
}

# Racks Registry
RACKS = {
    # Floor 1 — Zone A (High-Bay Heavy Pallets)
    "RACK-01": {"id": "RACK-01", "number": 1, "floor": 1, "zone": "Zone A (High-Bay)", "aisle": "Aisle 1", "x": -16, "y": 0, "z": -4, "w": 3, "h": 5, "d": 8},
    "RACK-02": {"id": "RACK-02", "number": 2, "floor": 1, "zone": "Zone A (High-Bay)", "aisle": "Aisle 1", "x": -11, "y": 0, "z": -4, "w": 3, "h": 5, "d": 8},
    "RACK-03": {"id": "RACK-03", "number": 3, "floor": 1, "zone": "Zone A (High-Bay)", "aisle": "Aisle 2", "x": -16, "y": 0, "z": 8, "w": 3, "h": 5, "d": 8},
    "RACK-04": {"id": "RACK-04", "number": 4, "floor": 1, "zone": "Zone A (High-Bay)", "aisle": "Aisle 2", "x": -11, "y": 0, "z": 8, "w": 3, "h": 5, "d": 8},
    "RACK-05": {"id": "RACK-05", "number": 5, "floor": 1, "zone": "Zone A (High-Bay)", "aisle": "Aisle 3", "x": -6, "y": 0, "z": -4, "w": 3, "h": 5, "d": 8},
    "RACK-06": {"id": "RACK-06", "number": 6, "floor": 1, "zone": "Zone A (High-Bay)", "aisle": "Aisle 3", "x": -1, "y": 0, "z": -4, "w": 3, "h": 5, "d": 8},
    "RACK-07": {"id": "RACK-07", "number": 7, "floor": 1, "zone": "Zone A (High-Bay)", "aisle": "Aisle 4", "x": -6, "y": 0, "z": 8, "w": 3, "h": 5, "d": 8},
    "RACK-08": {"id": "RACK-08", "number": 8, "floor": 1, "zone": "Zone A (High-Bay)", "aisle": "Aisle 4", "x": -1, "y": 0, "z": 8, "w": 3, "h": 5, "d": 8},

    # Floor 1 — Zone B (Bulk Pallets & Shipping Staging)
    "RACK-09": {"id": "RACK-09", "number": 9, "floor": 1, "zone": "Zone B (Bulk Storage)", "aisle": "Aisle 7", "x": 6, "y": 0, "z": -4, "w": 3, "h": 5, "d": 8},
    "RACK-10": {"id": "RACK-10", "number": 10, "floor": 1, "zone": "Zone B (Bulk Storage)", "aisle": "Aisle 8", "x": 11, "y": 0, "z": -4, "w": 3, "h": 5, "d": 8},
    "RACK-11": {"id": "RACK-11", "number": 11, "floor": 1, "zone": "Zone B (Bulk Storage)", "aisle": "Aisle 9", "x": 6, "y": 0, "z": 8, "w": 3, "h": 5, "d": 8},
    "RACK-12": {"id": "RACK-12", "number": 12, "floor": 1, "zone": "Zone B (Bulk Storage)", "aisle": "Aisle 10", "x": 11, "y": 0, "z": 8, "w": 3, "h": 5, "d": 8},

    # Floor 2 — Zone C (Mezzanine Electronics & Small Parts, elevation y=7)
    "RACK-13": {"id": "RACK-13", "number": 13, "floor": 2, "zone": "Zone C (Mezzanine Electronics)", "aisle": "Aisle 11", "x": -14, "y": 7, "z": -4, "w": 3, "h": 3.5, "d": 7},
    "RACK-14": {"id": "RACK-14", "number": 14, "floor": 2, "zone": "Zone C (Mezzanine Electronics)", "aisle": "Aisle 12", "x": -9, "y": 7, "z": -4, "w": 3, "h": 3.5, "d": 7},
    "RACK-15": {"id": "RACK-15", "number": 15, "floor": 2, "zone": "Zone C (Mezzanine Electronics)", "aisle": "Aisle 13", "x": -14, "y": 7, "z": 6, "w": 3, "h": 3.5, "d": 7},
    "RACK-16": {"id": "RACK-16", "number": 16, "floor": 2, "zone": "Zone C (Mezzanine Electronics)", "aisle": "Aisle 14", "x": -9, "y": 7, "z": 6, "w": 3, "h": 3.5, "d": 7},
    "RACK-17": {"id": "RACK-17", "number": 17, "floor": 2, "zone": "Zone C (Mezzanine Electronics)", "aisle": "Aisle 15", "x": -4, "y": 7, "z": -4, "w": 3, "h": 3.5, "d": 7},
    "RACK-18": {"id": "RACK-18", "number": 18, "floor": 2, "zone": "Zone C (Mezzanine Electronics)", "aisle": "Aisle 16", "x": -4, "y": 7, "z": 6, "w": 3, "h": 3.5, "d": 7},

    # Floor 2 — Zone Cold (Chilled Vault 2°C–4°C, elevation y=7)
    "RACK-19": {"id": "RACK-19", "number": 19, "floor": 2, "zone": "Zone Cold (Chilled Vault)", "aisle": "Cold Aisle 1", "x": 8, "y": 7, "z": -2, "w": 3.5, "h": 3.5, "d": 7},
    "RACK-20": {"id": "RACK-20", "number": 20, "floor": 2, "zone": "Zone Cold (Chilled Vault)", "aisle": "Cold Aisle 2", "x": 13, "y": 7, "z": -2, "w": 3.5, "h": 3.5, "d": 7},
}

# Add UCID to each rack
for rid, rdata in RACKS.items():
    z_letter = rdata["zone"].split()[1].upper()
    z_clean = f"ZN-{z_letter}"
    aisle_parts = rdata["aisle"].split()
    aisle_clean = f"AISLE-{int(aisle_parts[1]):02d}" if (len(aisle_parts) > 1 and aisle_parts[1].isdigit()) else rdata["aisle"].upper().replace(" ", "-")
    rdata["ucid"] = f"{FACILITY_ID}:FL-{rdata['floor']:02d}:{z_clean}:{aisle_clean}:BAY-{rdata['number']:02d}"


# Material Handling Equipment (MHE Forklifts & Reach Trucks)
EQUIPMENT_ASSETS = [
    {
        "id": "EQ-FL-01",
        "name": "Counterbalance Forklift #1",
        "type": "FORKLIFT",
        "floor": 1,
        "zone": "MHE Fleet Depot",
        "coordinates": {"x": 18, "y": 0, "z": -16},
        "status": "Available",
        "ucid": f"{FACILITY_ID}:FL-01:ZN-MHE:STATION-01"
    },
    {
        "id": "EQ-FL-02",
        "name": "Counterbalance Forklift #2",
        "type": "FORKLIFT",
        "floor": 1,
        "zone": "MHE Fleet Depot",
        "coordinates": {"x": 22, "y": 0, "z": -16},
        "status": "Available",
        "ucid": f"{FACILITY_ID}:FL-01:ZN-MHE:STATION-02"
    },
    {
        "id": "EQ-RT-01",
        "name": "High-Reach Narrow Truck #1",
        "type": "REACH_TRUCK",
        "floor": 1,
        "zone": "MHE Fleet Depot",
        "coordinates": {"x": 18, "y": 0, "z": -10},
        "status": "Available",
        "ucid": f"{FACILITY_ID}:FL-01:ZN-MHE:STATION-03"
    },
    {
        "id": "EQ-RT-02",
        "name": "High-Reach Narrow Truck #2",
        "type": "REACH_TRUCK",
        "floor": 1,
        "zone": "MHE Fleet Depot",
        "coordinates": {"x": 22, "y": 0, "z": -10},
        "status": "Available",
        "ucid": f"{FACILITY_ID}:FL-01:ZN-MHE:STATION-04"
    },
    {
        "id": "EQ-PJ-01",
        "name": "Electric Pallet Jack #1",
        "type": "PALLET_JACK",
        "floor": 1,
        "zone": "Aisle 4 Staging Bay",
        "coordinates": {"x": -3, "y": 0, "z": 15},
        "status": "Available",
        "ucid": f"{FACILITY_ID}:FL-01:ZN-A:STAGING-PJ1"
    }
]

# Specialized Key Logistics Zones
SPECIAL_ZONES = {
    "BAY-11": {
        "id": "BAY-11",
        "name": "Quarantine Staging Bay 11",
        "category": "QUARANTINE",
        "floor": 1,
        "coordinates": {"x": 20, "y": 0, "z": 12},
        "w": 7, "h": 4, "d": 7,
        "description": "RMA customer returns & damaged pallet hold per SOP-RET-004",
        "ucid": f"{FACILITY_ID}:FL-01:ZN-RET:BAY-11"
    },
    "MHE-DEPOT": {
        "id": "MHE-DEPOT",
        "name": "MHE Fleet Depot & Battery Station",
        "category": "FLEET_DEPOT",
        "floor": 1,
        "coordinates": {"x": 20, "y": 0, "z": -13},
        "w": 8, "h": 4, "d": 10,
        "description": "Forklift and reach truck parking, chargers, and PPE inspection per SOP-SAF-003",
        "ucid": f"{FACILITY_ID}:FL-01:ZN-MHE:DEPOT"
    },
    "COLD-VAULT": {
        "id": "COLD-VAULT",
        "name": "Chilled Storage Vault",
        "category": "COLD_CHAIN",
        "floor": 2,
        "coordinates": {"x": 10.5, "y": 7, "z": -2},
        "w": 10, "h": 4, "d": 9,
        "description": "Perishables maintained strictly at 2°C–4°C",
        "ucid": f"{FACILITY_ID}:FL-02:ZN-COLD:VAULT"
    }
}

# Product Catalog to Rack Map
PRODUCT_SPATIAL_MAP = {
    "SKU-4521": {
        "sku": "SKU-4521",
        "name": "Industrial Barcode Scanner",
        "category": "Electronics",
        "rack_id": "RACK-16",
        "shelf": "Shelf B",
        "bin": "Bin 2",
        "quantity": 42
    },
    "SKU-1088": {
        "sku": "SKU-1088",
        "name": "Thermal Label Printer",
        "category": "Electronics",
        "rack_id": "RACK-10",
        "shelf": "Shelf A",
        "bin": "Bin 1",
        "quantity": 18
    },
    "SKU-2045": {
        "sku": "SKU-2045",
        "name": "Heavy Pallet Racking Pins",
        "category": "Hardware",
        "rack_id": "RACK-04",
        "shelf": "Shelf C",
        "bin": "Bin 3",
        "quantity": 150
    },
    "SKU-3090": {
        "sku": "SKU-3090",
        "name": "Refrigerated Cold Chain Totes",
        "category": "Perishables",
        "rack_id": "RACK-19",
        "shelf": "Chiller Shelf 1",
        "bin": "Slot 4",
        "quantity": 25
    },
    "SKU-9011": {
        "sku": "SKU-9011",
        "name": "Damaged Inbound Return",
        "category": "RMA",
        "special_zone_id": "BAY-11",
        "quantity": 5
    }
}


def compute_waypoint_route(
    start_point: Dict[str, Any],
    dest_coords: Dict[str, float],
    dest_floor: int = 1
) -> List[List[float]]:
    """
    Computes a clean, non-intersecting 3D corridor wayfinding path
    from start_point to dest_coords, traversing freight lift if cross-floor.
    """
    start_x = start_point["coordinates"]["x"]
    start_y = start_point["coordinates"]["y"]
    start_z = start_point["coordinates"]["z"]
    start_floor = start_point.get("floor", 1)

    dest_x = dest_coords["x"]
    dest_y = dest_coords["y"]
    dest_z = dest_coords["z"]

    path: List[List[float]] = [[start_x, start_y, start_z]]

    # Same floor navigation
    if start_floor == dest_floor:
        # Move out to main transverse corridor (z = -12 or z = 0)
        corridor_z = -12 if (start_z < -5 and dest_z < -5) else 0
        path.append([start_x, start_y, corridor_z])
        # Move laterally along corridor to destination X
        path.append([dest_x, start_y, corridor_z])
        # Move down aisle to destination rack Z
        path.append([dest_x, dest_y, dest_z])
    else:
        # Cross-floor navigation via Mezzanine Lift (0, 0, -8) -> (0, 7, -8)
        lift_f1 = [0.0, 0.0, -8.0]
        lift_f2 = [0.0, 7.0, -8.0]

        # 1. Start to Lift F1
        path.append([start_x, start_y, -12.0])
        path.append([0.0, 0.0, -12.0])
        path.append(lift_f1)

        # 2. Lift Elevation Transition
        path.append(lift_f2)

        # 3. Lift F2 to Dest on Mezzanine
        path.append([0.0, 7.0, 0.0])
        path.append([dest_x, 7.0, 0.0])
        path.append([dest_x, dest_y, dest_z])

    return path


def get_all_spatial_data() -> Dict[str, Any]:
    """Returns the complete static warehouse layout for the 3D viewer."""
    return {
        "facility_id": FACILITY_ID,
        "facility_name": FACILITY_NAME,
        "origin_points": list(ORIGIN_POINTS.values()),
        "racks": list(RACKS.values()),
        "equipment": EQUIPMENT_ASSETS,
        "special_zones": list(SPECIAL_ZONES.values())
    }
