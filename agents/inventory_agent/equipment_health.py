"""
Equipment Health & Informal Maintenance Log Analyzer for Inventory Agent (Member 1).
Starred Differentiator for Team Project Brief:
"Reads informal maintenance complaint logs ('forklift 3 grinding') to spot recurring
issues before a breakdown — no sensors needed."
"""
import re
from typing import Dict, Any, List, Optional
from agents.inventory_agent.schemas import EquipmentHealthReport
from utils.logger import StructuredLogger

logger = StructuredLogger(__name__)

# Symptom & failure knowledge base (NLP taxonomy without sensors)
SYMPTOM_TAXONOMY = [
    {
        "keywords": ["grind", "grinding", "crunching", "metal sound", "rough lifting"],
        "equipment_type": "Forklift",
        "failure_mode": "Mast Bearing / Pinion Gear Degradation",
        "risk": "HIGH",
        "action": "Immediate lubrication & bearing tolerance inspection. Do not lift loads > 1.5t.",
        "window": "Within 12 Hours"
    },
    {
        "keywords": ["hydraulic", "fluid leak", "oil dripping", "slow lift", "mast sinking"],
        "equipment_type": "Forklift",
        "failure_mode": "Hydraulic Cylinder Seal Rupture",
        "risk": "IMMINENT",
        "action": "Ground equipment immediately. Replace hydraulic high-pressure seal & bleed lines.",
        "window": "Immediate Lockout/Tagout"
    },
    {
        "keywords": ["conveyor", "slip", "slipping", "squeal", "squealing", "belt jerk"],
        "equipment_type": "Conveyor",
        "failure_mode": "Conveyor Drive Belt Tension Loss / Pulley Glaze",
        "risk": "MEDIUM",
        "action": "Adjust tensioner pulley assembly and clean rubber debris from drive drum.",
        "window": "End of Shift"
    },
    {
        "keywords": ["agv", "stopping", "shudder", "obstacle false alarm", "lost path", "guidance"],
        "equipment_type": "AGV",
        "failure_mode": "LiDAR / Optical Floor Sensor Drift & Wheel Motor Wear",
        "risk": "HIGH",
        "action": "Recalibrate floor optical scanner lens and inspect drive encoder wheel.",
        "window": "Within 24 Hours"
    },
    {
        "keywords": ["battery", "hot", "overheat", "thermal", "smell", "drain fast", "swollen"],
        "equipment_type": "Battery / Power Unit",
        "failure_mode": "Lithium Cell Thermal Runaway Risk / BMS Sensor Fault",
        "risk": "IMMINENT",
        "action": "Disconnect charging dock immediately. Move to Hazmat cooling bay in Zone D.",
        "window": "Immediate Emergency Hazmat Action"
    },
    {
        "keywords": ["steering", "wheel stuck", "drifting", "brake soft", "spongy brake"],
        "equipment_type": "Forklift",
        "failure_mode": "Brake Master Cylinder / Steering Linkage Play",
        "risk": "HIGH",
        "action": "Brake fluid flush and mechanical steering tie-rod adjustment.",
        "window": "Within 8 Hours"
    }
]

# Historical recurring log occurrences
HISTORICAL_LOG_ARCHIVE = [
    {"equipment_id": "Forklift 3", "note": "Shift 1: operator noted loud grinding noise on heavy lift"},
    {"equipment_id": "Forklift 3", "note": "Shift 2: mast vibrating when lifting pallet past tier 3"},
    {"equipment_id": "AGV-08", "note": "Night shift: AGV stopped 4 times on transit runway 03"},
    {"equipment_id": "Conveyor Line A-02", "note": "Operator heard high pitched squealing during parcel sort"}
]


class EquipmentHealthAnalyzer:
    """Parses informal chatter & operator shift notes to preemptively detect equipment failures."""

    def analyze_log(self, text: str, equipment_id: Optional[str] = None) -> EquipmentHealthReport:
        logger.log_event("EQUIPMENT_HEALTH_ANALYSIS", {"text_preview": text[:80], "eq_id": equipment_id})
        
        raw_lower = text.lower()

        # 1. Detect or infer Equipment ID
        if not equipment_id:
            # Check pattern like "forklift 3", "agv-08", "conveyor a"
            eq_match = re.search(r"\b(forklift\s*\d+|agv[-\s]*\d+|conveyor[-\s]*[a-z0-9-]+|scanner\s*\d+|pallet jack\s*\d+)\b", raw_lower)
            if eq_match:
                equipment_id = eq_match.group(0).title()
            else:
                equipment_id = "Forklift 3"  # default reference demonstration unit

        # 2. Match Symptom against Taxonomy
        matched_tax = None
        for tax in SYMPTOM_TAXONOMY:
            if any(k in raw_lower for k in tax["keywords"]):
                matched_tax = tax
                break

        if not matched_tax:
            # Default to mechanical wear check
            matched_tax = SYMPTOM_TAXONOMY[0]

        # 3. Check historical recurrence in shift logs
        recurrence = 1
        for log in HISTORICAL_LOG_ARCHIVE:
            if equipment_id.lower() in log["equipment_id"].lower():
                recurrence += 1

        # Adjust risk if recurring
        risk = matched_tax["risk"]
        if recurrence >= 3 and risk == "HIGH":
            risk = "IMMINENT"

        return EquipmentHealthReport(
            equipment_id=equipment_id,
            equipment_type=matched_tax["equipment_type"],
            reported_symptom=text.strip(),
            detected_failure_mode=matched_tax["failure_mode"],
            breakdown_risk=risk,
            recurrence_count=recurrence,
            action_required=matched_tax["action"],
            scheduled_maintenance_window=matched_tax["window"]
        )

    def scan_recent_equipment_alerts(self) -> List[EquipmentHealthReport]:
        """Returns proactive health alerts derived from recent shift complaint logs."""
        alerts = []
        alerts.append(self.analyze_log("Forklift 3 mast grinding and vibration when raising heavy battery pack", "Forklift 3"))
        alerts.append(self.analyze_log("AGV-08 repeatedly halting on Runway 03 with optical sensor warning", "AGV-08"))
        alerts.append(self.analyze_log("Conveyor Line A-02 drive belt squealing loudly during peak intake", "Conveyor A-02"))
        return alerts


equipment_health_analyzer = EquipmentHealthAnalyzer()
