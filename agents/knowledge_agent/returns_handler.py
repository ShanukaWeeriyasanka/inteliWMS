"""
Customer Returns & Reverse Logistics Triage Handler.
Evaluates inbound return conditions, assigns grades, and routes items per SOP-RET-004.
"""
from typing import Dict, Any, Optional
import re
from utils.logger import StructuredLogger

logger = StructuredLogger(__name__)

RMA_PATTERN = re.compile(r"\b(RMA-[A-Z0-9]+)\b", re.IGNORECASE)


def triage_returned_item(
    rma_number: Optional[str] = None,
    sku: Optional[str] = None,
    condition: str = "unopened",
    package_sealed: bool = True,
    has_accessories: bool = True
) -> Dict[str, Any]:
    """
    Evaluates return intake against SOP-RET-004 rules.
    
    Returns:
        Dict adhering to ReturnTriageResponse schema.
    """
    clean_cond = condition.strip().lower()

    # 1. RMA Verification Check (SOP-RET-004 Section 1)
    if not rma_number or not rma_number.strip():
        msg = (
            "⚠️ RETURN INTAKE HOLD (MISSING RMA)\n"
            "• Rule: SOP-RET-004 (Section 1 - RMA Verification)\n"
            "• Status: REJECTED FROM ACTIVE UNLOADING\n"
            "• Finding: Inbound package lacks an active Return Merchandise Authorization (RMA) number.\n"
            "• Action: Hold package at Receiving Dock 3 Staging. Do NOT unpack until customer RMA is verified in system."
        )
        logger.log_event("RETURN_HOLD_NO_RMA", {"sku": sku})
        return {
            "approved_for_intake": False,
            "grade": "Rejected",
            "destination": "Receiving Dock 3 (Hold Staging)",
            "sop_id": "SOP-RET-004",
            "reasoning": "Missing active RMA authorization number.",
            "recommended_action": "Contact customer support to locate valid RMA before intake.",
            "formatted_message": msg
        }

    clean_rma = rma_number.strip().upper()

    # 2. Defect & Quarantine Check (SOP-RET-004 Section 3)
    is_damaged = any(d in clean_cond for d in ["damaged", "broken", "cracked", "water", "leak", "burnt", "faulty", "defective"])
    if is_damaged or not has_accessories:
        reasons = []
        if is_damaged:
            reasons.append("Physical or electrical defect detected")
        if not has_accessories:
            reasons.append("Missing required cables/accessories")
        reason_str = ", ".join(reasons)

        msg = (
            f"📦 RETURN TRIAGE: GRADE C (QUARANTINE)\n"
            f"• RMA ID: {clean_rma}\n"
            f"• Product SKU: {sku or 'Unspecified'}\n"
            f"• Rule: SOP-RET-004 (Section 3 - Quarantine & Scrap)\n"
            f"• Condition: {reason_str}\n"
            f"• Destination: Bay 11 (Returns Quarantine Area)\n"
            f"• Mandatory Action: Affix Yellow Quarantine Tag. Segregate immediately from saleable inventory."
        )
        logger.log_event("RETURN_TRIAGE_QUARANTINE", {"rma": clean_rma, "reason": reason_str})
        return {
            "approved_for_intake": True,
            "grade": "Grade C (Quarantine)",
            "destination": "Bay 11 (Returns Quarantine Area)",
            "sop_id": "SOP-RET-004",
            "reasoning": reason_str,
            "recommended_action": "Affix Yellow Tag and transfer to Quarantine Bay 11.",
            "formatted_message": msg
        }

    # 3. Grade A: Unopened & Pristine Seals (SOP-RET-004 Section 2)
    if package_sealed and clean_cond in ["unopened", "pristine", "new", "mint"]:
        msg = (
            f"📦 RETURN TRIAGE: GRADE A (DIRECT RESTOCK)\n"
            f"• RMA ID: {clean_rma}\n"
            f"• Product SKU: {sku or 'Unspecified'}\n"
            f"• Rule: SOP-RET-004 (Section 2 - Active Restock)\n"
            f"• Condition: Unopened original packaging with intact factory seals.\n"
            f"• Destination: Zone B (Active Inventory Storage)\n"
            f"• Action: Scan barcode into active stock inventory and place in assigned bin."
        )
        logger.log_event("RETURN_TRIAGE_GRADE_A", {"rma": clean_rma, "sku": sku})
        return {
            "approved_for_intake": True,
            "grade": "Grade A",
            "destination": "Zone B (Active Inventory Storage)",
            "sop_id": "SOP-RET-004",
            "reasoning": "Unopened packaging with intact seals.",
            "recommended_action": "Restock to active bins in Zone B.",
            "formatted_message": msg
        }

    # 4. Grade B: Opened Box with Complete Accessories (SOP-RET-004 Section 2)
    msg = (
        f"📦 RETURN TRIAGE: GRADE B (REPACKAGING ROUTE)\n"
        f"• RMA ID: {clean_rma}\n"
        f"• Product SKU: {sku or 'Unspecified'}\n"
        f"• Rule: SOP-RET-004 (Section 2 - Repackaging Line)\n"
        f"• Condition: Opened packaging with all internal accessories verified intact.\n"
        f"• Destination: Repackaging Station 4\n"
        f"• Action: Route to repackaging for inspection wipe-down and resealing."
    )
    logger.log_event("RETURN_TRIAGE_GRADE_B", {"rma": clean_rma, "sku": sku})
    return {
        "approved_for_intake": True,
        "grade": "Grade B",
        "destination": "Repackaging Station 4",
        "sop_id": "SOP-RET-004",
        "reasoning": "Opened packaging but functional with complete accessories.",
        "recommended_action": "Transfer to Repackaging Station 4.",
        "formatted_message": msg
    }


def evaluate_return_query(query: str) -> Dict[str, Any]:
    """
    Parses natural language return inquiries and determines triage destination.
    """
    raw = query.lower()

    # Extract RMA number
    rma_match = RMA_PATTERN.search(query)
    rma = rma_match.group(1).upper() if rma_match else "RMA-GENERIC"

    # Extract SKU
    sku_match = re.search(r"\b(SKU-\d+)\b", query, re.IGNORECASE)
    sku = sku_match.group(1).upper() if sku_match else None

    # Check for missing RMA explicitly mentioned
    if any(m in raw for m in ["no rma", "without rma", "missing rma", "no authorization"]):
        rma = None

    # Detect damage / defects
    is_damaged = any(d in raw for d in ["damaged", "defect", "water", "broken", "faulty", "scratched"])
    cond = "damaged" if is_damaged else ("opened_complete" if "opened" in raw else "unopened")
    sealed = "opened" not in raw and not is_damaged
    has_acc = not any(a in raw for a in ["missing cable", "missing accessories", "missing parts"])

    return triage_returned_item(
        rma_number=rma,
        sku=sku,
        condition=cond,
        package_sealed=sealed,
        has_accessories=has_acc
    )
