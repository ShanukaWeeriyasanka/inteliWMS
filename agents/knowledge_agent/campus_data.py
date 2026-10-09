"""
Campus Spatial Knowledge Registry for Knowledge Agent.
Authoritative multi-building campus facilities, MHE fleet vehicles, static infrastructure,
and campus inventory coordinates mirroring the Campus Digital Twin (CAMPUS_DATA).
"""
from typing import Dict, Any, List, Optional
import re

# ── 1. CAMPUS COMPLEX OVERVIEW ───────────────────────────────────────────────
CAMPUS_OVERVIEW = {
    "complex_id": "CMP-01",
    "name": "Colombo Logistics Complex",
    "hub_code": "NORTH-HUB",
    "gate_origin": {"x": 55, "y": 155, "name": "Gate 1 (Main Security Checkpoint & Weighbridge)"},
    "total_buildings": 7,
    "operational_status": "Fully Operational (24/7 Multi-Building Logistics Campus)",
    "description": (
        "Colombo Logistics Complex is a regional multi-building supply chain campus featuring "
        "7 specialized facilities: Automated High-Bay Hub (BLD-01), Bulk Distribution (BLD-02), "
        "Cleanroom Tech Mezzanine (BLD-03), Pharma Cold-Chain Vault (BLD-04), Quarantine Yard (BLD-05), "
        "MHE Fleet Depot (BLD-06), and Security Gatehouse & 60T Scale (BLD-07)."
    )
}

# ── 2. CAMPUS BUILDINGS / FACILITIES ──────────────────────────────────────────
CAMPUS_BUILDINGS: Dict[str, Dict[str, Any]] = {
    "BLD-01": {
        "id": "BLD-01",
        "number": "1",
        "name": "Building 1 — High-Bay Hub",
        "title": "1 · High-Bay Hub",
        "aliases": ["bld-01", "bld-1", "bld 1", "building 1", "high bay hub", "high bay", "high-bay", "automated high bay"],
        "category": "Automated Pallet High-Bay",
        "color": "#3B7BF6",
        "status": "94% Operational",
        "status_tone": "is-ok",
        "rect": {"x": 50, "y": 28, "w": 125, "h": 80},
        "dock_coords": {"x": 112, "y": 108},
        "capacity": "2,400 Pallet Bays",
        "capacity_value": 2400,
        "lots": "150 Stored Lots",
        "mhe_active": "2 Forklifts Active (FL-01, RT-01)",
        "assigned_mhe": ["FL-01", "RT-01"],
        "dock_doors": "Docks 1 to 4 (North Receiving & Automated Inbound)",
        "key_skus": ["SKU-4521 (Wireless Barcode Scanner, Aisle 12)", "SKU-1088 (Thermal Industrial Label Rolls, Aisle 1)"],
        "description": (
            "Building 1 (High-Bay Hub) is an automated narrow-aisle pallet high-bay facility with 2,400 pallet bays, "
            "150 active stored lots, and high-density racking. Operates FL-01 and RT-01 with automatic guide-wire "
            "retrieval and barcode scanning."
        ),
        "safety_notes": "Speed limit strictly 5 mph in aisles. Pedestrians must wear high-vis vests and keep to green marked walkways."
    },
    "BLD-02": {
        "id": "BLD-02",
        "number": "2",
        "name": "Building 2 — Bulk Distribution",
        "title": "2 · Bulk Distribution",
        "aliases": ["bld-02", "bld-2", "bld 2", "building 2", "bulk distribution", "bulk storage", "bulk", "outbound distribution"],
        "category": "Bulk Storage & Outbound",
        "color": "#8B5CF6",
        "status": "78% Operational",
        "status_tone": "is-ok",
        "rect": {"x": 195, "y": 28, "w": 115, "h": 80},
        "dock_coords": {"x": 252, "y": 108},
        "capacity": "1,600 Pallet Bays",
        "capacity_value": 1600,
        "lots": "95 Stored Lots",
        "mhe_active": "1 Shunt Truck, 1 Electric Pallet Jack (PJ-01)",
        "assigned_mhe": ["PJ-01", "Shunt Truck"],
        "dock_doors": "Docks 5 to 10 (Outbound Cross-Dock & Trailer Staging)",
        "key_skus": ["SKU-7788 (Thermal Label Printer, Aisle 5)", "SKU-9012 (Heavy Duty Pallet Wrap, Aisle 3)"],
        "description": (
            "Building 2 (Bulk Distribution) manages bulk palletized freight, cross-dock consolidation, and high-velocity "
            "trailer outbound dispatch with 1,600 pallet bays and 95 active lots. Equipped with 6 heavy-duty hydraulic dock levelers."
        ),
        "safety_notes": "Cross-dock corridor speed limit capped at 8 mph. Full trailer wheel chocks mandatory before loading."
    },
    "BLD-03": {
        "id": "BLD-03",
        "number": "3",
        "name": "Building 3 — Tech Mezzanine",
        "title": "3 · Tech Mezzanine",
        "aliases": ["bld-03", "bld-3", "bld 3", "building 3", "tech mezzanine", "mezzanine", "cleanroom", "esd", "electronics mezzanine"],
        "category": "Cleanroom ESD Electronics",
        "color": "#06B6D4",
        "status": "100% Regulated ESD",
        "status_tone": "is-ok",
        "rect": {"x": 145, "y": 130, "w": 115, "h": 70},
        "dock_coords": {"x": 202, "y": 130},
        "capacity": "950 Electronics Bins",
        "capacity_value": 950,
        "lots": "42 Stored Lots",
        "mhe_active": "2.5T Heavy Freight Lift (OBJ-LFT-01)",
        "assigned_mhe": ["OBJ-LFT-01"],
        "dock_doors": "Cleanroom Transfer Airlock Bay 3",
        "key_skus": ["SKU-3301 (Precision Semiconductor Wafers / IoT Sensor Modules, Cleanroom Bin CR-04)"],
        "description": (
            "Building 3 (Tech Mezzanine) is an ISO Class 7 cleanroom facility dedicated to micro-electronics, semiconductor components, "
            "and sensitive tech assemblies. Features conductive grounding floors and a dedicated 2.5-tonne vertical freight lift."
        ),
        "safety_notes": "Antistatic wrist straps, ESD heel grounders, and ESD coats mandatory. Strictly no unshielded cardboard inside cleanroom."
    },
    "BLD-04": {
        "id": "BLD-04",
        "number": "4",
        "name": "Building 4 — Cold Vault",
        "title": "4 · Cold Vault",
        "aliases": ["bld-04", "bld-4", "bld 4", "building 4", "cold vault", "cold storage", "pharma cold chain", "cold chain", "chilled vault", "freezer"],
        "category": "Pharma Cold-Chain (2°–4°C)",
        "color": "#0284C7",
        "status": "Chilled Vault Active (2°–4°C Monitored)",
        "status_tone": "is-ok",
        "rect": {"x": 280, "y": 130, "w": 80, "h": 70},
        "dock_coords": {"x": 320, "y": 130},
        "capacity": "320 Chilled Bays",
        "capacity_value": 320,
        "lots": "50 Vaccine Lots",
        "mhe_active": "Insulated Airlock Port (OBJ-AIR-01)",
        "assigned_mhe": ["OBJ-AIR-01"],
        "dock_doors": "Airlock Cold Dock Port 4",
        "key_skus": ["SKU-5520 (Insulin Glargine & Temperature-Sensitive Biologics, Chilled Rack C-02)"],
        "description": (
            "Building 4 (Cold Vault) provides temperature-controlled pharmaceutical cold-chain storage kept continuously at 2.0°C to 4.0°C. "
            "Equipped with dual-door interlocking airlocks, dual-redundant compressors, and real-time IoT temperature logging."
        ),
        "safety_notes": "Door open time cannot exceed 3 minutes. Any temperature excursion above 5.0°C triggers immediate alert and supervisor notification (SOP-COLD-005)."
    },
    "BLD-05": {
        "id": "BLD-05",
        "number": "5",
        "name": "Building 5 — Quarantine Yard",
        "title": "5 · Quarantine Yard",
        "aliases": ["bld-05", "bld-5", "bld 5", "building 5", "quarantine yard", "quarantine", "quarantine bay 11", "bay 11", "hazmat hold", "rma hold", "returns yard"],
        "category": "Hazmat & Returns Hold",
        "color": "#E5484D",
        "status": "Restricted Access Quarantine",
        "status_tone": "is-low",
        "rect": {"x": 380, "y": 130, "w": 55, "h": 70},
        "dock_coords": {"x": 407, "y": 130},
        "capacity": "80 RMA Lots",
        "capacity_value": 80,
        "lots": "14 Hold Lots",
        "mhe_active": "Spill Berm OK & Acid Neutralizer (OBJ-RMA-01)",
        "assigned_mhe": ["OBJ-RMA-01"],
        "dock_doors": "Bay 11 Quarantine Dock & Hazmat Inspection Gate",
        "key_skus": ["Bay 11 (Quarantine RMA Disputed Lots)", "SKU-2045 (Heavy Duty Forklift Battery Lithium, Hazmat Bay B-12)"],
        "description": (
            "Building 5 (Quarantine Yard) is a restricted-access containment compound for defective customer returns, damaged shipments, "
            "lithium battery quarantine, and RMA triage. Features secondary chemical spill berms and acid neutralizing containment."
        ),
        "safety_notes": "Restricted keycard access only. Level 2 PPE (chemical goggles, acid-resistant apron, nitrile gloves) required for hazardous inspection."
    },
    "BLD-06": {
        "id": "BLD-06",
        "number": "6",
        "name": "Building 6 — MHE Fleet Depot",
        "title": "6 · Fleet Depot",
        "aliases": ["bld-06", "bld-6", "bld 6", "building 6", "fleet depot", "mhe depot", "charging depot", "fleet maintenance", "maintenance depot"],
        "category": "Fleet Maintenance & Chargers",
        "color": "#FF7A1A",
        "status": "8 Charging Bays Online",
        "status_tone": "is-ok",
        "rect": {"x": 330, "y": 28, "w": 105, "h": 80},
        "dock_coords": {"x": 382, "y": 108},
        "capacity": "8 Fast Chargers (480V 3-Phase)",
        "capacity_value": 8,
        "lots": "4 Vehicles Parked",
        "mhe_active": "100% Fleet Ready (Charger Bay 2 with RT-02)",
        "assigned_mhe": ["RT-02 (Charging Bay 2)"],
        "dock_doors": "MHE Service Drive-In Ramp",
        "key_skus": ["Industrial Battery Charger Alpha", "Hydraulic Servicing Rigs", "MHE Replacement Spares"],
        "description": (
            "Building 6 (MHE Fleet Depot) handles preventive maintenance, hydraulic inspections, and rapid turnaround for all "
            "material handling equipment. Contains 8 three-phase 480V fast-charging bays with active forced-air ventilation."
        ),
        "safety_notes": "Continuous 24/7 exhaust fans must operate to prevent hydrogen gas accumulation during battery charging (SOP-MHE-008)."
    },
    "BLD-07": {
        "id": "BLD-07",
        "number": "7",
        "name": "Building 7 — Gatehouse & Scale",
        "title": "7 · Gatehouse & Scale",
        "aliases": ["bld-07", "bld-7", "bld 7", "building 7", "gatehouse & scale", "gatehouse", "weighbridge gatehouse", "security gatehouse"],
        "category": "Security & Weighbridge",
        "color": "#1E293B",
        "status": "Online 24/7 Security & Check-in",
        "status_tone": "is-ok",
        "rect": {"x": 50, "y": 130, "w": 75, "h": 70},
        "dock_coords": {"x": 87, "y": 130},
        "capacity": "60T Certified Weighbridge Scale",
        "capacity_value": 60,
        "lots": "Inbound / Outbound Carrier Staging",
        "mhe_active": "1 AGV Dispatch Station (AGV-01)",
        "assigned_mhe": ["AGV-01"],
        "dock_doors": "Gate 1 Main Security Barrier",
        "key_skus": ["Carrier Manifest Terminals", "Weighbridge Digital Display"],
        "description": (
            "Building 7 (Gatehouse & Scale) is the primary access control point at Gate 1. Features a certified 60-tonne electronic "
            "weighbridge platform, automated license plate recognition (ALPR), carrier document inspection, and AGV guide dispatch."
        ),
        "safety_notes": "All inbound trucks must stop on the weighbridge scale for gross tare weight logging before entering the campus (SOP-GATE-006)."
    }
}

# ── 3. CAMPUS FLEET VEHICLES ──────────────────────────────────────────────────
CAMPUS_VEHICLES: Dict[str, Dict[str, Any]] = {
    "FL-01": {
        "id": "FL-01",
        "name": "Forklift 1",
        "type": "Electric Counterbalance Forklift (Toyota 8FBE15)",
        "aliases": ["forklift 1", "fl-01", "fl 1", "forklift one", "forklift #1", "toyota forklift"],
        "coords": {"x": 70, "y": 96},
        "building_id": "BLD-01",
        "nearest_facility": "Building 1 — High-Bay Hub (Loading Dock)",
        "status": "Active / In Operation",
        "battery_soc": "89%",
        "operator": "Marcus V. (Shift 1)",
        "speed_limit": "5 mph inside aisles, 8 mph main corridor",
        "color": "#22C55E",
        "description": "Forklift 1 (FL-01) is active at Building 1 (High-Bay Hub) loading dock. Assigned to narrow-aisle pallet putaway."
    },
    "RT-01": {
        "id": "RT-01",
        "name": "Reach 1 (Reach Truck 1)",
        "type": "Crown RR 5700 High-Mast Reach Truck",
        "aliases": ["reach 1", "rt-01", "rt 1", "reach truck 1", "reach truck one", "crown reach truck"],
        "coords": {"x": 140, "y": 96},
        "building_id": "BLD-01",
        "nearest_facility": "Transit Avenue between Building 1 and Building 2",
        "status": "Active / In Transit",
        "battery_soc": "76%",
        "operator": "Elena R. (Shift 1)",
        "speed_limit": "5 mph inside aisles",
        "color": "#22C55E",
        "description": "Reach Truck 1 (RT-01) is operating in the transit avenue between Building 1 and Building 2, transporting high-bay pallets."
    },
    "PJ-01": {
        "id": "PJ-01",
        "name": "Pallet Jack",
        "type": "Raymond 8210 Electric Walkie Pallet Jack",
        "aliases": ["pallet jack", "pj-01", "pj 1", "electric pallet jack", "walkie pallet jack"],
        "coords": {"x": 215, "y": 96},
        "building_id": "BLD-02",
        "nearest_facility": "Building 2 — Bulk Distribution (Dock 7)",
        "status": "Active / Cross-Dock Staging",
        "battery_soc": "92%",
        "operator": "Devon S. (Shift 1)",
        "speed_limit": "3.5 mph walking pace",
        "color": "#22C55E",
        "description": "Electric Pallet Jack (PJ-01) is currently staged at Building 2 (Bulk Distribution) loading dock assisting with trailer cross-docking."
    },
    "AGV-01": {
        "id": "AGV-01",
        "name": "Tugger AGV",
        "type": "Automated Guided Tugger Vehicle (Dematic AGV-500)",
        "aliases": ["tugger agv", "agv-01", "agv 1", "agv", "automated guided vehicle", "autonomous tugger"],
        "coords": {"x": 325, "y": 120},
        "building_id": "BLD-07",
        "nearest_facility": "South Transit Corridor near Building 7 and Building 6",
        "status": "Autonomous Navigation (Waypoints 12 -> 14)",
        "battery_soc": "68%",
        "operator": "Autonomous / Tele-Monitored",
        "speed_limit": "4 mph automated path cap",
        "color": "#22C55E",
        "description": "Tugger AGV (AGV-01) is navigating autonomously along the South transit corridor between Gatehouse (BLD-07) and Fleet Depot (BLD-06)."
    },
    "RT-02": {
        "id": "RT-02",
        "name": "Charger Bay 2 (Reach Truck 2)",
        "type": "Crown RR 5700 Reach Truck (Charging)",
        "aliases": ["charger bay 2", "rt-02", "rt 2", "reach truck 2", "charger 2", "bay 2"],
        "coords": {"x": 370, "y": 65},
        "building_id": "BLD-06",
        "nearest_facility": "Building 6 — MHE Fleet Depot (Charger Bay 2)",
        "status": "Charging (Fast DC 480V)",
        "battery_soc": "82% (Full in ~18 min)",
        "operator": "Parked / Charging",
        "speed_limit": "Stationary",
        "color": "#F59E0B",
        "description": "Reach Truck 2 (RT-02) is parked and recharging at Charger Bay 2 inside Building 6 (Fleet Depot). Current battery is 82%."
    }
}

# ── 4. CAMPUS STATIC INFRASTRUCTURE & OBJECTS ────────────────────────────────
CAMPUS_OBJECTS: Dict[str, Dict[str, Any]] = {
    "OBJ-WGH-01": {
        "id": "OBJ-WGH-01",
        "name": "60T Weighbridge Scale",
        "aliases": ["60t scale", "weighbridge scale", "weighbridge", "truck scale", "scale", "60 tonne scale"],
        "building_id": "BLD-07",
        "building_name": "Building 7 — Gatehouse & Scale",
        "coords": {"x": 75, "y": 150},
        "specifications": "60-tonne gross capacity, digital load cells, ALPR integrated",
        "description": "The 60T Certified Weighbridge Scale is located at Building 7 (Gatehouse & Scale) directly at Gate 1 entrance."
    },
    "OBJ-CHG-01": {
        "id": "OBJ-CHG-01",
        "name": "8 Fast Chargers (480V 3-Phase)",
        "aliases": ["fast chargers", "chargers", "charging station", "charging bays", "8 fast chargers", "480v chargers"],
        "building_id": "BLD-06",
        "building_name": "Building 6 — MHE Fleet Depot",
        "coords": {"x": 380, "y": 50},
        "specifications": "8 x 480V 3-Phase rapid charging stations with continuous exhaust ventilation",
        "description": "The 8 Fast Chargers are located inside Building 6 (Fleet Depot) providing rapid replenishment for electric forklifts and reach trucks."
    },
    "OBJ-AIR-01": {
        "id": "OBJ-AIR-01",
        "name": "Airlock Port & Cold Seal",
        "aliases": ["airlock port", "airlock", "cold airlock", "sealed airlock"],
        "building_id": "BLD-04",
        "building_name": "Building 4 — Cold Vault",
        "coords": {"x": 320, "y": 130},
        "specifications": "Dual-door interlocking thermal curtain port maintaining 2°C–4°C internal envelope",
        "description": "The Airlock Port is located at Building 4 (Cold Vault) ensuring zero thermal loss during loading."
    },
    "OBJ-LFT-01": {
        "id": "OBJ-LFT-01",
        "name": "2.5T Heavy Freight Lift",
        "aliases": ["2.5t freight lift", "freight lift", "cargo lift", "mezzanine lift", "lift"],
        "building_id": "BLD-03",
        "building_name": "Building 3 — Tech Mezzanine",
        "coords": {"x": 202, "y": 130},
        "specifications": "2,500 kg hydraulic vertical freight elevator connecting ground level to cleanroom mezzanine",
        "description": "The 2.5T Heavy Freight Lift is located inside Building 3 (Tech Mezzanine) for transferring sensitive components to upper cleanroom floors."
    },
    "OBJ-RMA-01": {
        "id": "OBJ-RMA-01",
        "name": "Spill Berm & Chemical Containment",
        "aliases": ["spill berm", "chemical berm", "containment berm", "quarantine berm", "bay 11 berm"],
        "building_id": "BLD-05",
        "building_name": "Building 5 — Quarantine Yard",
        "coords": {"x": 407, "y": 130},
        "specifications": "Acid-resistant polyethylene spill barrier with 500-gallon containment and neutralizer kit",
        "description": "The Chemical Spill Berm is located at Building 5 (Quarantine Yard) adjacent to Bay 11 for hazardous and damaged returns isolation."
    },
    "OBJ-GATE-01": {
        "id": "OBJ-GATE-01",
        "name": "Gate 1 (Campus Main Gate)",
        "aliases": ["gate 1", "main gate", "entrance gate", "security gate", "gate origin"],
        "building_id": "BLD-07",
        "building_name": "Building 7 — Gatehouse & Scale",
        "coords": {"x": 55, "y": 155},
        "specifications": "Primary access barrier with boom arms, security booth, and biometric check-in",
        "description": "Gate 1 is the primary campus entry origin at the South-West perimeter, managed directly by Building 7 Security Gatehouse."
    }
}

# ── 5. CAMPUS SKUS & INVENTORY MAPPING ────────────────────────────────────────
CAMPUS_SKUS: Dict[str, Dict[str, Any]] = {
    "SKU-4521": {
        "sku": "SKU-4521",
        "name": "Wireless Barcode Scanner",
        "aliases": ["sku-4521", "barcode scanner", "rf gun", "wireless scanner", "handheld scanner"],
        "building_id": "BLD-01",
        "building_name": "Building 1 — High-Bay Hub",
        "location": "Aisle 12, Shelf B3, Bay 04 (Building 1 — High-Bay Hub)",
        "quantity": 340,
        "category": "Electronics & Tech",
        "temperature": "20.2 °C (Climate Monitored)",
        "is_hazardous": False,
        "description": "Wireless Barcode Scanner (SKU-4521) is stored in Building 1 (High-Bay Hub) at Aisle 12, Shelf B3, Bay 04. Current stock: 340 units."
    },
    "SKU-1088": {
        "sku": "SKU-1088",
        "name": "Thermal Industrial Label Rolls",
        "aliases": ["sku-1088", "thermal label rolls", "label rolls", "industrial label rolls"],
        "building_id": "BLD-01",
        "building_name": "Building 1 — High-Bay Hub",
        "location": "Aisle 1, Bay A-03, Shelf A3 (Building 1 — High-Bay Hub)",
        "quantity": 120,
        "category": "Consumables",
        "temperature": "20.5 °C (Climate Controlled)",
        "is_hazardous": False,
        "description": "Thermal Industrial Label Rolls (SKU-1088) are stored in Building 1 (High-Bay Hub) at Aisle 1, Bay A-03, Shelf A3. Current stock: 120 rolls."
    },
    "SKU-7788": {
        "sku": "SKU-7788",
        "name": "Thermal Label Printer",
        "aliases": ["sku-7788", "thermal label printer", "label printer", "zebra printer"],
        "building_id": "BLD-02",
        "building_name": "Building 2 — Bulk Distribution",
        "location": "Aisle 5, Shelf A1, Bay 02 (Building 2 — Bulk Distribution)",
        "quantity": 15,
        "category": "Dispatch Equipment",
        "temperature": "21.0 °C (Ambient)",
        "is_hazardous": False,
        "description": "Thermal Label Printer (SKU-7788) is stored in Building 2 (Bulk Distribution) at Aisle 5, Shelf A1, Bay 02. Current stock: 15 units."
    },
    "SKU-9012": {
        "sku": "SKU-9012",
        "name": "Heavy Duty Pallet Wrap",
        "aliases": ["sku-9012", "pallet wrap", "heavy duty pallet wrap", "stretch film"],
        "building_id": "BLD-02",
        "building_name": "Building 2 — Bulk Distribution",
        "location": "Aisle 3, Shelf C2, Bay 08 (Building 2 — Bulk Distribution)",
        "quantity": 5,
        "category": "Packaging Consumables",
        "temperature": "18.5 °C (Standard)",
        "is_hazardous": False,
        "description": "Heavy Duty Pallet Wrap (SKU-9012) is stored in Building 2 (Bulk Distribution) at Aisle 3, Shelf C2, Bay 08. Current stock: 5 rolls."
    },
    "SKU-3301": {
        "sku": "SKU-3301",
        "name": "Precision Semiconductor Wafers & Sensors",
        "aliases": ["sku-3301", "semiconductor wafers", "semiconductors", "sensor modules", "wafers"],
        "building_id": "BLD-03",
        "building_name": "Building 3 — Tech Mezzanine",
        "location": "Cleanroom Bin CR-04, Floor 2 (Building 3 — Tech Mezzanine)",
        "quantity": 950,
        "category": "Cleanroom ESD Electronics",
        "temperature": "21.0 °C (ESD Regulated Class 7)",
        "is_hazardous": False,
        "description": "Precision Semiconductor Wafers (SKU-3301) are stored in Building 3 (Tech Mezzanine) inside Cleanroom Bin CR-04. Current stock: 950 units. ESD protection required."
    },
    "SKU-5520": {
        "sku": "SKU-5520",
        "name": "Insulin Glargine & Temperature-Sensitive Biologics",
        "aliases": ["sku-5520", "insulin", "insulin glargine", "vaccines", "biologics", "pharma"],
        "building_id": "BLD-04",
        "building_name": "Building 4 — Cold Vault",
        "location": "Chilled Rack C-02, Chamber 1 (Building 4 — Cold Vault)",
        "quantity": 320,
        "category": "Pharma Cold-Chain (2°–4°C)",
        "temperature": "3.2 °C (Continuous IoT Datalogger Monitored)",
        "is_hazardous": False,
        "description": "Insulin Glargine Biologics (SKU-5520) are stored in Building 4 (Cold Vault) on Chilled Rack C-02 at 3.2°C. Current stock: 320 units. Cold-chain protocol SOP-COLD-005 applies."
    },
    "SKU-2045": {
        "sku": "SKU-2045",
        "name": "Heavy Duty Forklift Battery Lithium",
        "aliases": ["sku-2045", "forklift battery", "forklift batteries", "lithium battery", "lithium batteries", "battery lithium", "batteries lithium", "hazmat battery", "hazmat batteries"],
        "building_id": "BLD-05",
        "building_name": "Building 5 — Quarantine Yard",
        "location": "Aisle 4, Bay B-12 / Quarantine compound (Building 5 — Quarantine Yard)",
        "quantity": 42,
        "category": "Heavy Hazmat / Power",
        "temperature": "19.0 °C (Hazmat Thermal Guarded)",
        "is_hazardous": True,
        "description": "Heavy Duty Forklift Battery Lithium (SKU-2045) is stored in Building 5 (Quarantine Yard) at Hazmat Bay B-12. Current stock: 42 units. Hazardous material protocol SOP-HAZ-001 applies."
    }
}
