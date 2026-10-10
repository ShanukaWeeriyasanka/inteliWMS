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
    has_ppe: bool = True,
    value_label: Optional[str] = None
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
                "• Mandatory Action: Affix RED TAG immediately and transfer to the Quarantine Staging Area at Building 5 Bay 11. DO NOT RACK."
            )
            return {
                "compliant": False,
                "severity": "CRITICAL",
                "sop_id": "SOP-STG-002",
                "rule_title": "Pallet Stacking & Racking Regulations",
                "limit_description": "Damaged pallets must never be stacked or placed in high racking.",
                "violation_reason": "Pallet has structural defects.",
                "recommended_action": "Tag RED and transfer to the Quarantine Staging Area at Building 5 Bay 11.",
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
        # The speed as the user gave it ("7 km/h (≈4.3 mph)"); `value` itself is always mph
        shown = value_label or f"{speed:g} mph"

        if speed > max_speed:
            excess = round(speed - max_speed, 1)
            msg = (
                f"❌ NON-COMPLIANT (SPEED LIMIT VIOLATION)\n"
                f"• Rule: SOP-SAF-003 (Forklift & Mobile Equipment Safety Protocol - Section 1)\n"
                f"• Requested Speed: {shown} in {location_type}\n"
                f"• Maximum Legal Speed: {max_speed:g} mph\n"
                f"• Mandatory Action: Reduce travel speed by {excess:g} mph. Operators must sound horn at blind corners."
            )
            return {
                "compliant": False,
                "severity": "CRITICAL",
                "sop_id": "SOP-SAF-003",
                "rule_title": "Forklift & Mobile Equipment Operations",
                "limit_description": f"Maximum speed in {location_type}s is {max_speed} mph (8 km/h in aisles).",
                "violation_reason": f"Vehicle speed {shown} exceeds {max_speed:g} mph limit.",
                "recommended_action": f"Throttle down vehicle below {max_speed} mph.",
                "formatted_message": msg
            }

        msg = (
            f"✅ COMPLIANT\n"
            f"• Rule: SOP-SAF-003 permits up to {max_speed:g} mph in {location_type}s.\n"
            f"• Verified: Speed of {shown} complies with floor traffic regulations."
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

    # No rule covers it: say so. Never report an unchecked operation as verified.
    return _not_verified()


def _result(compliant: Optional[bool], severity: str, sop_id: str, title: str, limit: str, action: str,
            message: str, violation: Optional[str] = None) -> Dict[str, Any]:
    return {"compliant": compliant, "severity": severity, "sop_id": sop_id, "rule_title": title,
            "limit_description": limit, "violation_reason": violation, "recommended_action": action,
            "formatted_message": message}


def _not_verified() -> Dict[str, Any]:
    return _result(
        None, "UNKNOWN", "NONE", "No matching SOP rule", "No SOP rule in the library covers this operation.",
        "Check with your shift supervisor before going ahead.",
        "⚠️ **Not verified**: no SOP rule in the library covers this, so I can't confirm it's allowed. "
        "Check with your shift supervisor or safety officer before going ahead.")


# ── Natural-language parsing ─────────────────────────────────────────────────

KMH_PER_MPH = 1.609344
# A number that names a place ("aisle 4", "zone 2", "SKU-4521") is never a speed, tier count or duration
_PLACE_NUMBER = re.compile(r"\b(?:aisle|zone|bay|building|bld|gate|dock|lane|row|rack|shelf|pillar|level|floor|"
                           r"door|line|sku|station)[-\s#]*\d+(?:\.\d+)?\b", re.I)
_SPEED_WITH_UNIT = re.compile(r"(\d+(?:\.\d+)?)\s*(mph|miles?\s*(?:per|an|/)\s*h(?:ou)?r|km\s*/\s*h|kmh|kph|"
                              r"kilomet(?:er|re)s?\s*(?:per|an|/)\s*h(?:ou)?r)", re.I)
_NUMBER = re.compile(r"\b(\d+(?:\.\d+)?)\b")
_TIERS = re.compile(r"(\d+)\s*(?:tiers?|levels?|pallets?\s+high|high|pallets?)\b", re.I)
_MINUTES = re.compile(r"(\d+(?:\.\d+)?)\s*(?:min(?:ute)?s?)\b", re.I)
# The user repeats a limit they were told ("the new policy allows 12 mph"): answer from the SOP and say so
_PREMISE = re.compile(r"\b(?:new\s+(?:policy|rule)|polic(?:y|ies)\s+(?:now\s+)?(?:allows?|says|lets)|"
                      r"supervisor\s+(?:said|says|told)|was\s+told|told\s+me|i\s+heard|(?:has|was|been)\s+changed|"
                      r"now\s+allows?|lets\s+forklifts)\b", re.I)
PREMISE_NOTE = ("\nℹ️ This is the rule in the current SOP. If you were told something different, confirm it with the "
                "safety officer before acting on it — I won't change a safety limit on a claim alone.")
# Zones with a documented stacking limit (SOP-STG-002 §1); other zones have none on record
_DOCUMENTED_ZONES = {"zone a": "Zone A", "zone c": "Zone C"}


def _without_places(raw: str) -> str:
    return _PLACE_NUMBER.sub(" ", raw)


def parse_speed(raw: str) -> Optional[tuple]:
    """(speed in mph, the speed as the user gave it) or None when no speed is stated."""
    text = _without_places(raw)
    m = _SPEED_WITH_UNIT.search(text)
    if m:
        value, unit = float(m.group(1)), m.group(2).lower()
        if unit.startswith("k"):
            mph = value / KMH_PER_MPH
            return mph, f"{value:g} km/h (≈{mph:.1f} mph)"
        return value, f"{value:g} mph"
    m = _NUMBER.search(text)
    if m:
        value = float(m.group(1))
        return value, f"{value:g} mph (no unit given, read as mph)"
    return None


def _stacking_limits_message(zone_key: Optional[str]) -> Dict[str, Any]:
    """The documented limit when the user gave no tier count (nothing is assumed about their stack)."""
    a, c = ZONE_STACKING_LIMITS["zone a"], ZONE_STACKING_LIMITS["zone c"]
    if zone_key in _DOCUMENTED_ZONES:
        limit = ZONE_STACKING_LIMITS[zone_key]
        text = (f"ℹ️ SOP-STG-002 §1: in **{_DOCUMENTED_ZONES[zone_key]}** pallets may be stacked up to a maximum of "
                f"**{limit} tiers** high. Tell me how many tiers you plan and I'll check it.")
        return _result(None, "INFO", "SOP-STG-002", "Pallet Stacking & Racking Regulations",
                       f"Maximum {limit} tiers in {_DOCUMENTED_ZONES[zone_key]}.", "Stay within the limit.", text)
    return _result(None, "INFO", "SOP-STG-002", "Pallet Stacking & Racking Regulations",
                   f"Zone A maximum {a} tiers; Zone C maximum {c} tiers.", "Stay within the limit for your zone.",
                   f"ℹ️ SOP-STG-002 §1: **Zone A** — maximum **{a} tiers**; **Zone C** — maximum **{c} tiers** "
                   f"(double stacking is the absolute limit).")


def _undocumented_zone(zone_label: str) -> Dict[str, Any]:
    a, c = ZONE_STACKING_LIMITS["zone a"], ZONE_STACKING_LIMITS["zone c"]
    return _result(None, "UNKNOWN", "SOP-STG-002", "Pallet Stacking & Racking Regulations",
                   f"No documented limit for {zone_label}.", "Check with your shift supervisor.",
                   f"⚠️ SOP-STG-002 sets stacking limits only for Zone A ({a} tiers) and Zone C ({c} tiers). "
                   f"No limit is documented for **{zone_label}**, so I can't verify it — check with your shift "
                   f"supervisor.")


def _speed_limits_message() -> Dict[str, Any]:
    aisle, corridor = SPEED_LIMITS["aisle"], SPEED_LIMITS["corridor"]
    return _result(None, "INFO", "SOP-SAF-003", "Forklift & Mobile Equipment Operations",
                   f"Aisles {aisle:g} mph (8 km/h); main cross-dock corridor {corridor:g} mph.",
                   "Stay within the limit.",
                   f"ℹ️ SOP-SAF-003 §1: maximum **{aisle:g} mph (8 km/h)** inside aisles and **{corridor:g} mph** "
                   f"in the main cross-dock corridor. Tell me the speed and I'll check it.")


def _special_rules(raw: str) -> Optional[Dict[str, Any]]:
    """Specific prohibitions written in the SOPs that the keyword checks below would otherwise miss."""
    if re.search(r"\bdrains?\b", raw) and re.search(r"\b(?:acid|chemical|electrolyte|spill)", raw):
        return _result(False, "CRITICAL", "SOP-HAZ-001", "Hazardous Materials & Battery Protocol",
                       "Chemical spills must not be flushed down the drain.", "Use the Acid Neutralizing Spill Kit.",
                       "❌ NON-COMPLIANT\n• Rule: SOP-HAZ-001 §2 — do not flush chemical spills down the drain.\n"
                       "• Action: alert the Floor Supervisor and use the Acid Neutralizing Spill Kit (Pillar 14 or "
                       "Building 5 Quarantine Spill Berm).", "Flushing chemical spills down the drain is prohibited.")
    if re.search(r"\bcold\s*(?:vault|room|chain)|\bvault\b|\bbuilding\s*4\b", raw):
        minutes = _MINUTES.search(_without_places(raw))
        if re.search(r"\bdoors?\b", raw) and minutes:
            value = float(minutes.group(1))
            ok = value <= 3
            return _result(ok, "COMPLIANT" if ok else "CRITICAL", "SOP-COLD-005", "Cold-Chain Vault Storage",
                           "Door open time must never exceed 3 minutes.", "Keep door-open time under 3 minutes.",
                           (f"✅ COMPLIANT\n• Rule: SOP-COLD-005 §2 — door open time must never exceed 3 minutes; "
                            f"{value:g} minutes is within it." if ok else
                            f"❌ NON-COMPLIANT\n• Rule: SOP-COLD-005 §2 — door open duration must never exceed "
                            f"**3 minutes** under any circumstances. {value:g} minutes is over the limit.\n"
                            f"• Action: shut the outer airlock door before opening the inner door, and load in "
                            f"shorter cycles."),
                           None if ok else f"{value:g} minutes exceeds the 3-minute limit.")
        if re.search(r"\b(?:skip|ignore|stop|without|no\s+need|don'?t)\b[^.?!]{0,40}\b(?:log|logging|record|"
                     r"check|monitor\w*|reading|temperature)", raw):
            return _result(False, "CRITICAL", "SOP-COLD-005", "Cold-Chain Vault Storage",
                           "Products must be kept between 2.0 °C and 4.0 °C continuously.",
                           "Keep monitoring; report any excursion.",
                           "❌ Not permitted on the SOP's terms.\n• Rule: SOP-COLD-005 §1 — the vault must be "
                           "maintained **continuously** between 2.0 °C and 4.0 °C, and §3 requires supervisor "
                           "notification above 5.0 °C. Temperature checks must not be skipped.\n"
                           "• The SOP doesn't describe the log itself — ask your shift supervisor about the logging "
                           "procedure.", "Skipping temperature monitoring breaks the continuous-control rule.")
    return None


def evaluate_compliance_query(query: str) -> Dict[str, Any]:
    """
    Parses natural language queries to extract operational parameters and runs compliance check.
    Only values the user actually stated are checked: a missing tier count, speed or zone is never filled in
    with a default — the documented limit is stated instead.
    """
    raw = query.lower()
    result = _evaluate(raw)
    if _PREMISE.search(raw) and result.get("sop_id") not in (None, "NONE"):
        result = {**result, "formatted_message": result["formatted_message"] + PREMISE_NOTE}
    return result


def _evaluate(raw: str) -> Dict[str, Any]:
    special = _special_rules(raw)
    if special is not None:
        return special

    # 1. Stacking queries (e.g. "Can I stack 4 tiers in Zone A?")
    if any(w in raw for w in ["stack", "tier", "tiers", "pallet height", "overhang"]):
        zone_match = re.search(r"zone\s+([a-z0-9]+)\b", raw)
        zone_key = f"zone {zone_match.group(1)}" if zone_match else None
        zone_label = f"Zone {zone_match.group(1).upper()}" if zone_match else None
        is_damaged = any(d in raw for d in ["cracked", "damaged", "broken", "missing board"])
        if is_damaged:
            return check_compliance(category="stacking", zone=zone_label, pallet_condition="cracked")
        if zone_key is not None and zone_key not in _DOCUMENTED_ZONES:
            return _undocumented_zone(zone_label)
        tier_match = _TIERS.search(_without_places(raw))
        if tier_match is None:
            return _stacking_limits_message(zone_key)
        tiers = float(tier_match.group(1))
        if zone_key is None:
            # No zone given: check against both documented zones rather than assume one
            a, c = ZONE_STACKING_LIMITS["zone a"], ZONE_STACKING_LIMITS["zone c"]
            if tiers <= min(a, c):
                return check_compliance(category="stacking", zone="Zone C", value=tiers)
            if tiers > max(a, c):
                return check_compliance(category="stacking", zone="Zone A", value=tiers)
            return _result(None, "WARNING", "SOP-STG-002", "Pallet Stacking & Racking Regulations",
                           f"Zone A maximum {a} tiers; Zone C maximum {c} tiers.", "Tell me the zone.",
                           f"⚠️ It depends on the zone (SOP-STG-002 §1): {tiers:g} tiers is allowed in **Zone A** "
                           f"(max {a}) but **not** in **Zone C** (max {c}). Which zone is it?")
        return check_compliance(category="stacking", zone=zone_label, value=tiers)

    # 2. Speed queries (e.g. "Is 7 mph allowed in the aisle?")
    if any(w in raw for w in ["speed", "mph", "km/h", "kmh", "kph", "fast", "forklift speed"]):
        parsed = parse_speed(raw)
        if parsed is None:
            return _speed_limits_message()
        speed, shown = parsed
        zone = "corridor" if "corridor" in raw or "main" in raw else "aisle"
        return check_compliance(category="speed", zone=zone, value=speed, value_label=shown)

    # 3. PPE / Battery queries (e.g. "Can I charge battery without gloves?")
    if any(w in raw for w in ["battery", "acid", "charging", "ppe", "gloves", "goggles"]):
        has_ppe = not any(neg in raw for neg in ["without", "no gloves", "no goggles", "no ppe"])
        return check_compliance(category="hazard", has_ppe=has_ppe)

    return _not_verified()
