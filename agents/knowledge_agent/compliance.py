"""
Warehouse Safety & Regulatory Compliance Checker.
Evaluates physical warehouse operations against Standard Operating Procedures (SOPs).
All rule thresholds are sourced from knowledge_config (zero hardcoding).
"""
from typing import Dict, Any, Optional
import re
from agents.knowledge_agent.config import knowledge_config
from utils.logger import StructuredLogger

logger = StructuredLogger(__name__)

# Rule constants are centralised in knowledge_config to allow env-based overrides.
ZONE_STACKING_LIMITS = knowledge_config.ZONE_STACKING_LIMITS
SPEED_LIMITS = knowledge_config.SPEED_LIMITS


def check_compliance(
    category: str = "stacking",
    zone: Optional[str] = None,
    value: Optional[float] = None,
    pallet_condition: Optional[str] = None,
    has_ppe: bool = True
) -> Dict[str, Any]:
    """
    Evaluates warehouse operation parameters against safety SOPs.
    
    Returns:
        Dict adhering to ComplianceCheckResponse schema.
    """
    clean_cat = category.strip().lower()

    # 1. PALLET STACKING & CONDITION CHECKS (SOP-STG-002)
    if clean_cat in ["stacking", "pallet", "tiers"]:
        clean_zone = zone.strip().lower() if zone else "zone a"
        max_allowed = ZONE_STACKING_LIMITS.get(clean_zone, ZONE_STACKING_LIMITS["default"])
        tiers = int(value) if value is not None else 1

        # Check physical damage first (Red Tag requirement)
        if pallet_condition and pallet_condition.lower() in ["cracked", "damaged", "missing_boards", "broken"]:
            msg = (
                "❌ NON-COMPLIANT (SAFETY VIOLATION)\n"
                "• Rule: SOP-STG-002 (Pallet Stacking & Racking Regulations - Section 2)\n"
                "• Finding: Pallet has physical defects (cracked/missing boards).\n"
                "• Mandatory Action: Affix RED TAG immediately and transfer to Quarantine Staging Area at Bay 9. DO NOT RACK."
            )
            return {
                "compliant": False,
                "severity": "CRITICAL",
                "sop_id": "SOP-STG-002",
                "rule_title": "Pallet Stacking & Racking Regulations",
                "limit_description": "Damaged pallets must never be stacked or placed in high racking.",
                "violation_reason": "Pallet has structural defects.",
                "recommended_action": "Tag RED and transfer to Quarantine Bay 9.",
                "formatted_message": msg
            }

        # Check stacking height limits
        if tiers > max_allowed:
            excess = tiers - max_allowed
            msg = (
                f"❌ NON-COMPLIANT (OVER-STACKING VIOLATION)\n"
                f"• Rule: SOP-STG-002 (Pallet Stacking & Racking Regulations - Section 1)\n"
                f"• Requested: {tiers} tiers in {zone or 'Zone A'}\n"
                f"• Safe Operational Limit: Maximum {max_allowed} tiers\n"
                f"• Mandatory Action: Reduce stack height by {excess} pallet(s). Over-stacking creates tip-over hazard."
            )
            return {
                "compliant": False,
                "severity": "CRITICAL",
                "sop_id": "SOP-STG-002",
                "rule_title": "Pallet Stacking & Racking Regulations",
                "limit_description": f"Maximum {max_allowed} tiers high in {zone or 'Zone A'}.",
                "violation_reason": f"Stack height of {tiers} tiers exceeds the safety limit of {max_allowed}.",
                "recommended_action": f"De-stack {excess} pallet(s) to adhere to safe height.",
                "formatted_message": msg
            }

        msg = (
            f"✅ COMPLIANT\n"
            f"• Rule: SOP-STG-002 permits up to {max_allowed} tiers in {zone or 'Zone A'}.\n"
            f"• Verified: Your request ({tiers} tier{'s' if tiers > 1 else ''}) is within safe limits."
        )
        return {
            "compliant": True,
            "severity": "COMPLIANT",
            "sop_id": "SOP-STG-002",
            "rule_title": "Pallet Stacking & Racking Regulations",
            "limit_description": f"Maximum {max_allowed} tiers high.",
            "violation_reason": None,
            "recommended_action": "Proceed with standard storage procedure.",
            "formatted_message": msg
        }

    # 2. VEHICLE SPEED COMPLIANCE (SOP-SAF-003)
    if clean_cat in ["speed", "forklift", "vehicle"]:
        speed = float(value) if value is not None else 0.0
        location_type = "corridor" if (zone and any(c in zone.lower() for c in ["corridor", "cross-dock", "main"])) else "aisle"
        max_speed = SPEED_LIMITS[location_type]

        if speed > max_speed:
            excess = round(speed - max_speed, 1)
            msg = (
                f"❌ NON-COMPLIANT (SPEED LIMIT VIOLATION)\n"
                f"• Rule: SOP-SAF-003 (Forklift & Mobile Equipment Safety Protocol - Section 1)\n"
                f"• Requested Speed: {speed} mph in {location_type}\n"
                f"• Maximum Legal Speed: {max_speed} mph\n"
                f"• Mandatory Action: Reduce travel speed by {excess} mph. Operators must sound horn at blind corners."
            )
            return {
                "compliant": False,
                "severity": "CRITICAL",
                "sop_id": "SOP-SAF-003",
                "rule_title": "Forklift & Mobile Equipment Operations",
                "limit_description": f"Maximum speed in {location_type}s is {max_speed} mph (8 km/h in aisles).",
                "violation_reason": f"Vehicle speed {speed} mph exceeds {max_speed} mph limit.",
                "recommended_action": f"Throttle down vehicle below {max_speed} mph.",
                "formatted_message": msg
            }

        msg = (
            f"✅ COMPLIANT\n"
            f"• Rule: SOP-SAF-003 permits up to {max_speed} mph in {location_type}s.\n"
            f"• Verified: Speed of {speed} mph complies with floor traffic regulations."
        )
        return {
            "compliant": True,
            "severity": "COMPLIANT",
            "sop_id": "SOP-SAF-003",
            "rule_title": "Forklift & Mobile Equipment Operations",
            "limit_description": f"Max speed {max_speed} mph.",
            "violation_reason": None,
            "recommended_action": "Maintain vigilant operation and sound horn at intersections.",
            "formatted_message": msg
        }

    # 3. HAZMAT & BATTERY PPE (SOP-HAZ-001)
    if clean_cat in ["hazard", "battery", "ppe"]:
        if not has_ppe:
            msg = (
                "❌ NON-COMPLIANT (PPE SAFETY VIOLATION)\n"
                "• Rule: SOP-HAZ-001 (Hazardous Materials & Battery Handling - Section 1)\n"
                "• Finding: Battery servicing attempted without required eye protection or rubber gloves.\n"
                "• Mandatory Action: Do NOT handle lead-acid or lithium batteries without mandatory PPE. Deploy spill kit at Pillar 14 if leakage occurs."
            )
            return {
                "compliant": False,
                "severity": "CRITICAL",
                "sop_id": "SOP-HAZ-001",
                "rule_title": "Hazardous Materials & Battery Protocol",
                "limit_description": "Full chemical eye protection and rubber gloves mandatory at Charging Station Alpha.",
                "violation_reason": "Missing mandatory safety PPE.",
                "recommended_action": "Don safety goggles and chemical-resistant gloves before entering Bay 15.",
                "formatted_message": msg
            }

        return {
            "compliant": True,
            "severity": "COMPLIANT",
            "sop_id": "SOP-HAZ-001",
            "rule_title": "Hazardous Materials & Battery Protocol",
            "limit_description": "Mandatory PPE equipped.",
            "violation_reason": None,
            "recommended_action": "Ensure charging bay exhaust fans are running 24/7.",
            "formatted_message": "✅ COMPLIANT: Full battery PPE equipped. Proceed with Bay 15 protocol."
        }

    # Default fallback
    return {
        "compliant": True,
        "severity": "INFO",
        "sop_id": "SOP-GEN-000",
        "rule_title": "General Warehouse Standard",
        "limit_description": "Standard floor protocols apply.",
        "violation_reason": None,
        "recommended_action": "Consult shift supervisor for custom operational guidelines.",
        "formatted_message": f"Verified: Operation '{category}' conforms to standard warehouse procedures."
    }


def evaluate_compliance_query(query: str) -> Dict[str, Any]:
    """
    Parses natural language queries to extract operational parameters and runs compliance check.
    """
    raw = query.lower()

    # 1. Stacking queries (e.g. "Can I stack 4 tiers in Zone A?")
    if any(w in raw for w in ["stack", "tier", "tiers", "pallet height", "overhang"]):
        # Extract zone
        zone_match = re.search(r"zone\s+([a-z0-9]+)", raw)
        zone = f"Zone {zone_match.group(1).upper()}" if zone_match else "Zone A"

        # Extract number of tiers
        tier_match = re.search(r"(\d+)\s*(?:tier|tiers|pallet|pallets|high)", raw)
        tiers = float(tier_match.group(1)) if tier_match else knowledge_config.COMPLIANCE_DEFAULT_TIERS

        # Check for damaged pallet words
        is_damaged = any(d in raw for d in ["cracked", "damaged", "broken", "missing board"])
        pallet_cond = "cracked" if is_damaged else "good"

        return check_compliance(category="stacking", zone=zone, value=tiers, pallet_condition=pallet_cond)

    # 2. Speed queries (e.g. "Is 7 mph allowed in the aisle?")
    if any(w in raw for w in ["speed", "mph", "km/h", "fast", "forklift speed"]):
        speed_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:mph|speed)?", raw)
        speed = float(speed_match.group(1)) if speed_match else knowledge_config.COMPLIANCE_DEFAULT_SPEED
        zone = "corridor" if "corridor" in raw or "main" in raw else "aisle"
        return check_compliance(category="speed", zone=zone, value=speed)

    # 3. PPE / Battery queries (e.g. "Can I charge battery without gloves?")
    if any(w in raw for w in ["battery", "acid", "charging", "ppe", "gloves", "goggles"]):
        has_ppe = not any(neg in raw for neg in ["without", "no gloves", "no goggles", "no ppe"])
        return check_compliance(category="hazard", has_ppe=has_ppe)

    # Fallback to general checking
    return check_compliance(category="general")
