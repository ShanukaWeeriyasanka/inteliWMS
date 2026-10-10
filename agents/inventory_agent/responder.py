"""
Inventory answer text, built only from validated tool results.

Every number shown comes from a field of a tool result model; anything that was
defaulted (missing thresholds, a default burn rate, demo anomaly data) is said so.

Wording rule for not-found / failure texts: the fulfillment agent reads the
inventory reply by keyword (agents/fulfillment/fulfillment_agent.py), so those
texts must not contain "available", "unavailable", "stock:", "units on hand",
"out of stock" or "<digit>0 units". Quantities are written "**340** units" for
the same reason ("340 units" contains "0 units").
"""
from typing import Dict, List, Optional

from agents.inventory_agent.schemas import AnomalyAlert, StockItemInfo
from agents.inventory_agent.tool_contracts import (
    AnomalyResult,
    DepletionResult,
    MovementsResult,
    ProductCandidate,
    TransferResult,
)

_STATUS_EMOJI = {"IN_STOCK": "✅", "LOW_STOCK": "⚠️", "OUT_OF_STOCK": "❌", "OVERSTOCKED": "📦"}

# ── Failures and gaps (see wording rule above) ───────────────────────────────

FAILURE_TEXT: Dict[str, str] = {
    "timeout": "⚠️ The inventory service took too long to respond, so I can't give stock figures right now. "
               "Please try again in a moment.",
    "unavailable": "⚠️ I couldn't reach the inventory service, so I can't give stock figures right now.",
    "config_error": "⚠️ The inventory service connection is not configured correctly, so I can't give stock "
                    "figures right now. An administrator needs to check the inventory MCP settings.",
    "tool_error": "⚠️ The inventory database could not be queried, so I can't give stock figures right now.",
    "invalid_response": "⚠️ The inventory service returned data I couldn't verify, so I won't show any figures.",
    "invalid_arguments": "⚠️ I couldn't turn that into a valid inventory lookup. Please rephrase or give a SKU.",
    "unauthorized": "⚠️ The inventory agent isn't permitted to run that lookup.",
}

_NEEDS_PRODUCT = {
    "transfer_advisor": "Which product should I check transfers for?",
    "reorder_predictor": "Which product should I forecast?",
    "stock_movements": "Which product's stock movements do you want?",
    "location_lookup": "Which product are you looking for?",
    "availability": "Which product do you want me to check?",
}


def failure(status: str) -> str:
    return FAILURE_TEXT.get(status, FAILURE_TEXT["unavailable"])


def not_found(product_ref: str) -> str:
    return f"❌ I couldn't find **{product_ref}** in the inventory records. Please check the SKU or product name."


def needs_product(sub_intent: str) -> str:
    lead = _NEEDS_PRODUCT.get(sub_intent, "Which product do you mean?")
    return f"{lead} Tell me a SKU (for example `SKU-4521`) or the product name."


def clarification(candidates: List[ProductCandidate]) -> str:
    lines = ["I found more than one product that matches:"]
    lines += [f"{i}. **{c.name}** (`{c.sku}`)" for i, c in enumerate(candidates, 1)]
    lines.append("Which one did you mean? Reply with the number, name or SKU.")
    return "\n".join(lines)


def map_unavailable() -> str:
    return "⚠️ The warehouse map isn't reachable right now, so I can't show that place. Please try again shortly."


def assumed_note(label: str) -> str:
    return f"↪️ Using **{label}** from earlier in this conversation.\n"


# ── Stock answers ───────────────────────────────────────────────────────────

def _qty(n: int, unit: str) -> str:
    return f"**{n}** {unit}"


def _status_line(item: StockItemInfo) -> str:
    if item.status == "OUT_OF_STOCK":
        return (f"\n🚨 **OUT OF STOCK**: nothing on hand. Reorder {_qty(item.reorder_quantity, item.unit)} "
                f"or check a sibling-warehouse transfer.")
    if item.status == "LOW_STOCK":
        line = (f"\n⚠️ **LOW STOCK**: {item.quantity_on_hand} on hand, reorder point {item.reorder_point} — "
                f"at or below the reorder point.")
        if item.below_safety_stock:
            line += f" Also at or below the safety stock of {item.safety_stock}."
        return line
    if item.status == "OVERSTOCKED":
        return f"\n📦 **OVERSTOCKED**: more than 3× the reorder point of {item.reorder_point}."
    return ""


def stock_card(item: StockItemInfo, thresholds_defaulted: bool = False) -> str:
    text = (
        f"{_STATUS_EMOJI.get(item.status, 'ℹ️')} **{item.name}** (`{item.sku}`)\n"
        f"📍 **Location**: `{item.location}` ({item.category})\n"
        f"📦 **Stock**: {_qty(item.quantity_on_hand, item.unit)} on hand "
        f"({item.available_quantity} available, {item.reserved_quantity} reserved)"
    )
    if item.product_id:
        text += f'\nProduct ID: `{item.product_id}`. Source: **{item.data_source}**.'
        if item.updated_at:
            text += f' Data updated: {item.updated_at}.'
        text += f' Quarantined: {item.quarantined_quantity}.'
        if item.unplaced_quantity:
            text += f'\n{item.unplaced_quantity} {item.unit} have no verified box assignment.'
        for row in item.placements:
            text += (f"\n• `{row['bin_id']}` — {row['location_label']}: {row['quantity']} {item.unit} "
                     f"({row['available_quantity']} available, {row['reserved_quantity']} reserved, "
                     f"{row['quarantined_quantity']} quarantined).")
    extras = []
    if item.occupancy_pct is not None:
        extras.append(f"{item.occupancy_pct:g}% full")
    if item.temperature:
        extras.append(f"Ambient: {item.temperature}")
    if extras:
        text += "\n📊 **Bay**: " + " • ".join(extras)
    text += _status_line(item)
    if thresholds_defaulted:
        text += "\nℹ️ Reorder thresholds for this item aren't set in the database; standard defaults were used."
    return text


def availability_answer(item: StockItemInfo, thresholds_defaulted: bool = False) -> str:
    if item.available_quantity > 0:
        lead = (f"✅ Yes — {_qty(item.available_quantity, item.unit)} of **{item.name}** (`{item.sku}`) "
                f"can be picked now ({item.quantity_on_hand} on hand, {item.reserved_quantity} reserved).")
    else:
        lead = (f"❌ No — **{item.name}** (`{item.sku}`) has none free to pick "
                f"({item.quantity_on_hand} on hand, {item.reserved_quantity} reserved).")
    return f"{lead}\n\n{stock_card(item, thresholds_defaulted)}"


def low_stock_list(items: List[StockItemInfo], total_checked: int) -> str:
    if not items:
        return (f"✅ All {total_checked} items are above their reorder points. "
                f"No replenishment needed right now.")
    lines = [f"⚠️ **{len(items)} item(s) at or below the reorder point** (of {total_checked} checked):"]
    for i in items:
        emoji = "❌" if i.status == "OUT_OF_STOCK" else "⚠️"
        lines.append(f"  {emoji} **{i.name}** (`{i.sku}`) — {i.quantity_on_hand} on hand, reorder point "
                     f"{i.reorder_point}, at `{i.location}`. Suggested reorder: {_qty(i.reorder_quantity, i.unit)}.")
    return "\n".join(lines)


def movements(result: MovementsResult) -> str:
    who = f"**{result.item_name}** (`{result.subject_id}`)" if result.item_name else f"`{result.subject_id}`"
    if result.status == "empty":
        return f"ℹ️ No stock movements are recorded for {who}."
    lines = [f"🔄 **Recent stock movements — {who}**"]
    for m in result.movements:
        when = (m.at or "")[:16].replace("T", " ")
        change = f"{m.quantity_change:+d}" if result.source == "inventory_transactions" else str(m.quantity_change)
        detail = f"{m.movement_type} {change}"
        if m.previous_quantity is not None and m.new_quantity is not None:
            detail += f" ({m.previous_quantity} → {m.new_quantity})"
        route = " → ".join(x for x in (m.from_location, m.to_location) if x)
        if route:
            detail += f" · {route}"
        if m.reference:
            detail += f" · ref {m.reference}"
        lines.append(f"• {when} — {detail}" if when else f"• {detail}")
    return "\n".join(lines)


# ── Specialist answers ──────────────────────────────────────────────────────

def depletion(result: DepletionResult) -> str:
    pred = result.prediction
    compliance = ("\n⚠️ *Regulated / hazmat item: Knowledge Agent compliance sign-off required before PO approval.*"
                  if pred.compliance_check_required else "")
    if pred.days_until_stockout is None:
        stockout = "• Estimated Days Until Stockout: no stockout projected — no consumption is recorded\n"
    else:
        stockout = (f"• Estimated Days Until Stockout: **{pred.days_until_stockout} days** "
                    f"(Projected: {pred.projected_stockout_date})\n")
    if pred.recommended_reorder_qty > 0:
        replenish = (f"📦 **Recommended Replenishment**: Order **{pred.recommended_reorder_qty}** units — enough for "
                     f"the {pred.lead_time_days}-day lead time plus {pred.buffer_days} days of use, "
                     f"minus what is on hand.")
    else:
        replenish = (f"📦 **Recommended Replenishment**: none needed — stock on hand covers the "
                     f"{pred.lead_time_days}-day lead time plus {pred.buffer_days} days of use.")
    text = (
        f"📉 **Stock Depletion & Reorder Forecast** (`{pred.sku}`)\n"
        f"• Item: **{pred.item_name}**\n"
        f"• Current Stock: **{pred.current_stock}** units\n"
        f"• Average Burn Rate: **{pred.daily_burn_rate}** units/day\n"
        f"{stockout}"
        f"• Depletion Urgency: **{pred.urgency}**\n"
        f"{replenish}{compliance}"
    )
    if not pred.burn_rate_valid:
        text += ("\n⚠️ The recorded burn rate is negative, which can't be right — no stockout was projected. "
                 "Please correct this item's consumption data.")
    defaults = [n for n, src in (("burn rate", result.burn_rate_source), ("lead time", result.lead_time_source))
                if src == "default"]
    if defaults:
        text += f"\nℹ️ No {' or '.join(defaults)} is recorded for this item; a standard default was used."
    return text


def anomaly(result: AnomalyResult) -> str:
    if result.status == "empty":
        scope = f" for `{result.sku}`" if result.sku else ""
        return f"✅ No anomalous stock movements or shrinkage found in the recorded inventory transactions{scope}."
    alert: AnomalyAlert = result.alerts[0]
    text = (
        f"🚨 **Inventory Movement Anomaly Flagged** (`{alert.anomaly_id}`)\n"
        f"• Flagged SKU: **{alert.item_name}** (`{alert.sku}`)\n"
        f"• Anomaly Classification: **{alert.anomaly_type.replace('_', ' ')}** (Severity: **{alert.severity}**)\n"
        f"• Book Count vs Physical: Expected **{alert.expected_quantity}**, "
        f"Actual **{alert.recorded_quantity}** (Discrepancy: `{alert.variance}` units)\n"
        f"• Estimated Financial Exposure: **${alert.loss_value_est:,.2f}**\n"
        f"🔍 **Details**: {alert.description}\n"
        f"🛡️ **Loss Prevention Directive**: {alert.recommended_action}"
    )
    if len(result.alerts) > 1:
        text += f"\n➕ {len(result.alerts) - 1} more anomaly alert(s) flagged."
    if result.source == "demo":
        text = "🧪 *Demo scenario (INVENTORY_DEMO_DATA is on) — not live inventory data.*\n" + text
    return text


def transfer(result: TransferResult, item: Optional[StockItemInfo] = None) -> str:
    text = result.recommendation.advisory_verdict
    if item is not None and item.status in ("IN_STOCK", "OVERSTOCKED"):
        # Above the reorder point: say so first, so the option below isn't read as a need
        state = "overstocked" if item.status == "OVERSTOCKED" else "above its reorder point"
        text = (f"ℹ️ **No transfer is needed**: **{item.name}** (`{item.sku}`) is {state} — "
                f"{item.quantity_on_hand} on hand vs reorder point {item.reorder_point}.\n"
                f"If you still want stock moved here, this is the best option:\n" + text)
    if result.quantity_source != "requested":
        text += (f"\nℹ️ No quantity was given, so the item's reorder quantity "
                 f"({result.recommendation.required_quantity}) was used.")
    text += '\nSibling warehouse figures come from a local snapshot; no external live warehouse feed is connected.'
    return text


def invalid_transfer_quantity(quantity: int, maximum: int) -> str:
    return (f"⚠️ A transfer needs a quantity from 1 to {maximum:,} — you asked for {quantity}. "
            f"Tell me how many you need, for example \"transfer 50 units of SKU-4521\".")


def skus_left_out(skus: List[str], limit: int) -> str:
    return (f"\n\nℹ️ I answer up to {limit} SKUs at a time, so these weren't checked: "
            + ", ".join(f"`{s}`" for s in skus) + ". Ask again for them.")


def low_stock_section(items: List[StockItemInfo], total_checked: int) -> str:
    """The SKU catalogue's low items, added under the map's alerts (the two catalogues are separate)."""
    if not items:
        return f"📋 **SKU catalogue**: all {total_checked} items are above their reorder points."
    lines = [f"📋 **SKU catalogue** — {len(items)} of {total_checked} item(s) at or below the reorder point:"]
    for i in items:
        emoji = "❌" if i.status == "OUT_OF_STOCK" else "⚠️"
        lines.append(f"• {emoji} **{i.name}** (`{i.sku}`): {i.quantity_on_hand} on hand, reorder point "
                     f"{i.reorder_point}" + (f", safety stock {i.safety_stock}" if i.below_safety_stock else ""))
    return "\n".join(lines)


def equipment(report) -> str:
    risk_emoji = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🟠", "IMMINENT": "🚨"}.get(report.breakdown_risk, "⚠️")
    return (
        f"🔧 **Equipment Health Diagnostics (Predictive NLP)**\n"
        f"• Target Unit: **{report.equipment_id}** ({report.equipment_type})\n"
        f"• Identified Symptom: *\"{report.reported_symptom}\"*\n"
        f"• Root Cause: **{report.detected_failure_mode}**\n"
        f"• Breakdown Risk: {risk_emoji} **{report.breakdown_risk}** "
        f"(Recurrence: {report.recurrence_count}x in complaint logs)\n"
        f"🛠️ **Prescribed Work Order**: {report.action_required}\n"
        f"⏱️ **Target Window**: {report.scheduled_maintenance_window} "
        f"— *Preventative action dispatched before hardware failure.*"
    )


def many_items(items: List[StockItemInfo]) -> Optional[str]:
    if not items:
        return None
    return "\n\n".join(stock_card(i) for i in items)
