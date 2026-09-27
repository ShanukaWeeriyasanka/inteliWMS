"""
Inventory Specialist Agent for IntelliWMS (Member 1).

Complete Multi-Component Autonomous Specialist:
  1. Document Parser: Inbound supplier emails & PDFs (NER SKU, Qty, Date, PO).
  2. Reorder Predictor: Daily consumption burn rate & depletion forecasting.
  3. Anomaly Watcher: Stock movement shrinkage & variance detection.
  4. Transfer Advisor: Sibling warehouse surplus evaluation vs external vendor POs.
  5. Equipment Health: Informal complaint logs NLP for predictive maintenance.
  6. Real-time Warehouse Floor Locator: High-bay rack coordinates, tiers, & live layout.
"""
import re
import time
from typing import Dict, Any, Optional, List

from sqlalchemy.orm import Session

from agents.inventory_agent.config import inventory_config
from agents.inventory_agent.schemas import (
    InventoryQueryRequest,
    InventoryQueryResponse,
    StockItemInfo,
)
from agents.inventory_agent.document_parser import document_parser
from agents.inventory_agent.reorder_predictor import reorder_predictor
from agents.inventory_agent.anomaly_watcher import anomaly_watcher
from agents.inventory_agent.transfer_advisor import transfer_advisor
from agents.inventory_agent.equipment_health import equipment_health_analyzer
from agents.inventory_agent.warehouse_map import (
    get_sku_map_coordinates,
    get_full_warehouse_layout,
)

from database.connection import SessionLocal
from database.models import Product
from utils.logger import StructuredLogger

logger = StructuredLogger(__name__)

_SKU_PATTERN = re.compile(r"\b(SKU-?\d{3,6})\b", re.IGNORECASE)


# ── DB helpers ────────────────────────────────────────────────────────────────

def _extract_sku(text: str) -> Optional[str]:
    match = _SKU_PATTERN.search(text)
    return match.group(1).upper() if match else None


def _get_product_by_sku(sku: str, db: Optional[Session] = None) -> Optional[Product]:
    """Fetch a single product by SKU from the live database (no seed fallback)."""
    own = db is None
    if own:
        db = SessionLocal()
    try:
        return db.query(Product).filter(Product.sku.ilike(sku.strip())).first()
    except Exception as exc:
        logger.log_event("INVENTORY_DB_ERROR", {"op": "get_by_sku", "error": str(exc)})
        return None
    finally:
        if own:
            db.close()


def _resolve_sku_from_db(query: str, db: Optional[Session] = None) -> Optional[str]:
    """Try to match query text against product names / SKUs in the DB."""
    own = db is None
    if own:
        db = SessionLocal()
    try:
        q_lower = query.lower()
        products = db.query(Product.sku, Product.name).all()
        for sku, name in products:
            if name and name.lower() in q_lower:
                return sku
            if sku and sku.lower() in q_lower:
                return sku
    except Exception:
        pass
    finally:
        if own:
            db.close()
    return None


def _search_products_by_name(term: str, db: Optional[Session] = None, limit: int = 5) -> List[Product]:
    """Search products by name ILIKE from the live database (no seed fallback)."""
    own = db is None
    if own:
        db = SessionLocal()
    try:
        return db.query(Product).filter(Product.name.ilike(f"%{term}%")).limit(limit).all()
    except Exception as exc:
        logger.log_event("INVENTORY_DB_ERROR", {"op": "search_by_name", "error": str(exc)})
        return []
    finally:
        if own:
            db.close()


def _get_all_products(db: Optional[Session] = None) -> List[Product]:
    own = db is None
    if own:
        db = SessionLocal()
    try:
        return db.query(Product).all()
    except Exception:
        return []
    finally:
        if own:
            db.close()


def _compute_status(qty: int, safety_stock: int, reorder_point: int) -> str:
    if qty == 0:
        return "OUT_OF_STOCK"
    if qty <= safety_stock:
        return "LOW_STOCK"
    if qty > reorder_point * 3:
        return "OVERSTOCKED"
    return "IN_STOCK"


def _product_to_stock_item(p: Product) -> StockItemInfo:
    """Convert a live DB Product row to a StockItemInfo — no seed data used."""
    qty = p.quantity or 0
    safety_stock = p.safety_stock or inventory_config.DEFAULT_SAFETY_STOCK
    reorder_point = p.reorder_point or inventory_config.DEFAULT_REORDER_POINT
    reorder_qty = p.reorder_quantity or inventory_config.DEFAULT_REORDER_QUANTITY
    reserved = p.reserved_quantity or 0
    available = max(0, qty - reserved)
    status = _compute_status(qty, safety_stock, reorder_point)

    # Prefer DB spatial columns; fall back to static map only if DB cols are NULL
    aisle = p.aisle
    shelf = p.shelf
    tier = p.tier
    bay = p.bay
    occupancy = float(p.occupancy_pct) if p.occupancy_pct is not None else 50.0
    weight = float(p.weight_kg) if p.weight_kg is not None else 1.0
    temp = p.temperature or "20.0 °C Ambient"

    if not (aisle and shelf):
        # Last-resort: static map (only for SKUs not yet fully migrated)
        map_meta = get_sku_map_coordinates(p.sku) or {}
        aisle = aisle or map_meta.get("aisle")
        shelf = shelf or map_meta.get("shelf")
        tier = tier or map_meta.get("tier")
        bay = bay or map_meta.get("bay")
        occupancy = occupancy if p.occupancy_pct is not None else map_meta.get("occupancy_pct", 50.0)
        weight = weight if p.weight_kg is not None else map_meta.get("weight_kg", 1.0)
        temp = temp if p.temperature else map_meta.get("temperature", "20.0 °C Ambient")

    return StockItemInfo(
        sku=p.sku,
        name=p.name,
        category=p.category or "General",
        location=p.location or "Location not assigned",
        aisle=aisle,
        shelf=shelf,
        tier=tier,
        bay=bay,
        quantity_on_hand=qty,
        reserved_quantity=reserved,
        available_quantity=available,
        safety_stock=safety_stock,
        reorder_point=reorder_point,
        reorder_quantity=reorder_qty,
        unit=p.unit or "units",
        status=status,
        occupancy_pct=occupancy,
        weight_kg=weight,
        temperature=temp,
    )


# ── Sub-intent classifier ─────────────────────────────────────────────────────

def _detect_sub_intent(query: str) -> str:
    """Classifies user query into one of the 5 Member-1 capabilities or stock check."""
    q = query.lower()

    # 1. Document parser signals
    if any(k in q for k in ["supplier email", "supplier pdf", "parse email", "inbound invoice",
                             "shipping manifest", "delivery confirmation", "from apex", "from zebra",
                             "subject:", "attached document"]):
        return "document_parser"

    # 2. Equipment health signals
    if any(k in q for k in ["forklift", "grinding", "squeal", "hydraulic leak", "breakdown",
                             "complaint log", "agv stopped", "sensor fault", "equipment issue",
                             "equipment health", "conveyor"]):
        return "equipment_health"

    # 3. Anomaly / shrinkage signals
    if any(k in q for k in ["anomaly", "shrinkage", "stolen", "loss prevention", "discrepancy",
                             "missing stock", "unauthorized adjustment", "unexplained drop"]):
        return "anomaly_watcher"

    # 4. Sibling warehouse transfer signals
    if any(k in q for k in ["transfer", "sibling warehouse", "other warehouse", "inter-warehouse",
                             "wh-beta", "wh-gamma", "wh-delta", "surplus stock", "surplus in other"]):
        return "transfer_advisor"

    # 5. Reorder predictor (depletion trend) signals
    if any(k in q for k in ["burn rate", "depletion", "velocity", "days until stockout", "run out",
                             "when will", "predict reorder", "consumption trend"]):
        return "reorder_predictor"

    # 6. General reorder check
    if any(k in q for k in ["reorder", "replenish", "restock", "need to order",
                             "running low", "low stock", "out of stock"]):
        return "reorder_check"

    # 7. Location lookup
    if any(k in q for k in ["where is", "location", "aisle", "shelf", "bin", "bay", "find", "locate"]):
        return "location_lookup"

    return "stock_check"


# ── Agent class ───────────────────────────────────────────────────────────────

class InventoryAgent:
    """
    Inventory Specialist Agent (Member 1).
    Full suite: Document Parser, Reorder Predictor, Anomaly Watcher,
    Transfer Advisor, and Equipment Health — all driven by live DB data.
    """

    def handle_query(self, request: InventoryQueryRequest, db: Optional[Session] = None) -> InventoryQueryResponse:
        start_ms = time.time() * 1000
        query = request.query.strip()
        sub_intent = _detect_sub_intent(query)
        sku = request.sku or _extract_sku(query) or _resolve_sku_from_db(query, db)

        logger.log_event("INVENTORY_AGENT_QUERY", {
            "query": query[:80],
            "sub_intent": sub_intent,
            "sku": sku,
            "user_role": request.user_role,
        })

        # ─── 1. DOCUMENT PARSER ───
        if sub_intent == "document_parser":
            doc_result = document_parser.parse_document(query)
            items = []
            if doc_result.extracted_sku:
                p = _get_product_by_sku(doc_result.extracted_sku, db)
                if p:
                    items.append(_product_to_stock_item(p))
            elapsed = round(time.time() * 1000 - start_ms, 2)
            return InventoryQueryResponse(
                agent="inventory_agent", query=query, sub_intent="document_parser",
                response=doc_result.raw_summary, source="document_parser",
                items=items, needs_reorder=False, document_result=doc_result,
                execution_time_ms=elapsed,
            )

        # ─── 2. EQUIPMENT HEALTH ───
        if sub_intent == "equipment_health":
            health_report = equipment_health_analyzer.analyze_log(query)
            risk_emoji = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🟠", "IMMINENT": "🚨"}.get(
                health_report.breakdown_risk, "⚠️")
            resp_text = (
                f"🔧 **Equipment Health Diagnostics (Predictive NLP)**\n"
                f"• Target Unit: **{health_report.equipment_id}** ({health_report.equipment_type})\n"
                f"• Identified Symptom: *\"{health_report.reported_symptom}\"*\n"
                f"• Root Cause: **{health_report.detected_failure_mode}**\n"
                f"• Breakdown Risk: {risk_emoji} **{health_report.breakdown_risk}** "
                f"(Recurrence: {health_report.recurrence_count}x in complaint logs)\n"
                f"🛠️ **Prescribed Work Order**: {health_report.action_required}\n"
                f"⏱️ **Target Window**: {health_report.scheduled_maintenance_window} "
                f"— *Preventative action dispatched before hardware failure.*"
            )
            elapsed = round(time.time() * 1000 - start_ms, 2)
            return InventoryQueryResponse(
                agent="inventory_agent", query=query, sub_intent="equipment_health",
                response=resp_text, source="equipment_health",
                items=[], needs_reorder=False, equipment_health_result=health_report,
                execution_time_ms=elapsed,
            )

        # ─── 3. ANOMALY WATCHER ───
        if sub_intent == "anomaly_watcher":
            target_sku = sku or "SKU-9012"
            alert = anomaly_watcher.check_sku_anomalies(target_sku, db)
            if not alert:
                all_alerts = anomaly_watcher.scan_all_anomalies(db)
                alert = all_alerts[0] if all_alerts else None

            p = _get_product_by_sku(alert.sku if alert else target_sku, db)
            items = [_product_to_stock_item(p)] if p else []

            if alert:
                resp_text = (
                    f"🚨 **Inventory Movement Anomaly Flagged** (`{alert.anomaly_id}`)\n"
                    f"• Flagged SKU: **{alert.item_name}** (`{alert.sku}`)\n"
                    f"• Anomaly Classification: **{alert.anomaly_type.replace('_', ' ')}** "
                    f"(Severity: **{alert.severity}**)\n"
                    f"• Book Count vs Physical: Expected **{alert.expected_quantity}**, "
                    f"Actual **{alert.recorded_quantity}** (Discrepancy: `{alert.variance}` units)\n"
                    f"• Estimated Financial Exposure: **${alert.loss_value_est:,.2f}**\n"
                    f"🔍 **Details**: {alert.description}\n"
                    f"🛡️ **Loss Prevention Directive**: {alert.recommended_action}"
                )
            else:
                resp_text = "✅ No anomalous stock movements or shrinkage patterns detected."

            elapsed = round(time.time() * 1000 - start_ms, 2)
            return InventoryQueryResponse(
                agent="inventory_agent", query=query, sub_intent="anomaly_watcher",
                response=resp_text, source="anomaly_watcher",
                items=items,
                needs_reorder=bool(alert and alert.severity in ("HIGH", "CRITICAL")),
                anomaly_result=alert, execution_time_ms=elapsed,
            )

        # ─── 4. TRANSFER ADVISOR ───
        if sub_intent == "transfer_advisor":
            target_sku = sku or "SKU-4521"
            transfer_rec = transfer_advisor.evaluate_transfer(target_sku, needed_quantity=50, db=db)
            p = _get_product_by_sku(target_sku, db)
            items = [_product_to_stock_item(p)] if p else []
            elapsed = round(time.time() * 1000 - start_ms, 2)
            return InventoryQueryResponse(
                agent="inventory_agent", query=query, sub_intent="transfer_advisor",
                response=transfer_rec.advisory_verdict, source="transfer_advisor",
                items=items, needs_reorder=False, transfer_result=transfer_rec,
                execution_time_ms=elapsed,
            )

        # ─── 5. REORDER PREDICTOR ───
        if sub_intent == "reorder_predictor":
            target_sku = sku or "SKU-9012"
            p = _get_product_by_sku(target_sku, db)
            stock_qty = p.quantity if p else 5
            item_name = p.name if p else "Inventory Item"
            pred = reorder_predictor.predict_depletion(target_sku, stock_qty, item_name, db=db)
            items = [_product_to_stock_item(p)] if p else []

            compliance_note = (
                "\n⚠️ *Regulated / Hazmat item: Knowledge Agent compliance sign-off required prior to PO approval.*"
                if pred.compliance_check_required else ""
            )
            resp_text = (
                f"📉 **Stock Depletion & Reorder Forecast** (`{pred.sku}`)\n"
                f"• Item: **{pred.item_name}**\n"
                f"• Current Stock: **{pred.current_stock} units**\n"
                f"• Average Burn Rate: **{pred.daily_burn_rate} units/day**\n"
                f"• Estimated Days Until Stockout: **{pred.days_until_stockout} days** "
                f"(Projected: {pred.projected_stockout_date})\n"
                f"• Depletion Urgency: **{pred.urgency}**\n"
                f"📦 **Recommended Replenishment**: Order **{pred.recommended_reorder_qty} units** "
                f"to cover lead time ({pred.lead_time_days} days).{compliance_note}"
            )
            elapsed = round(time.time() * 1000 - start_ms, 2)
            return InventoryQueryResponse(
                agent="inventory_agent", query=query, sub_intent="reorder_predictor",
                response=resp_text, source="reorder_predictor",
                items=items,
                needs_reorder=pred.urgency in ("CRITICAL", "HIGH"),
                prediction_result=pred, execution_time_ms=elapsed,
            )

        # ─── 6. EXPLICIT REORDER SCAN ───
        if sub_intent == "reorder_check" and not sku:
            return self._handle_reorder_scan(request, db, start_ms)

        # ─── 7. SKU-SPECIFIC LOOKUP ───
        if sku:
            product = _get_product_by_sku(sku, db)
            if product:
                item = _product_to_stock_item(product)
                status_emoji = {
                    "IN_STOCK": "✅", "LOW_STOCK": "⚠️", "OUT_OF_STOCK": "❌", "OVERSTOCKED": "📦"
                }.get(item.status, "ℹ️")

                response_text = (
                    f"{status_emoji} **{item.name}** (`{item.sku}`)\n"
                    f"📍 **Location**: `{item.location}` ({item.category})\n"
                    f"📦 **Stock**: **{item.quantity_on_hand} {item.unit}** on hand "
                    f"({item.available_quantity} available, {item.reserved_quantity} reserved)\n"
                    f"📊 **Bay Volumetric**: {item.occupancy_pct}% full • Ambient: {item.temperature}"
                )
                if item.status == "OUT_OF_STOCK":
                    response_text += (
                        f"\n🚨 **URGENT**: Physical stock depleted. "
                        f"Reorder {item.reorder_quantity} {item.unit} or check sibling transfer."
                    )
                elif item.status == "LOW_STOCK":
                    response_text += (
                        f"\n⚠️ **LOW STOCK**: {item.quantity_on_hand}/{item.reorder_point} "
                        f"{item.unit}. Below safety buffer."
                    )

                elapsed = round(time.time() * 1000 - start_ms, 2)
                return InventoryQueryResponse(
                    agent="inventory_agent", query=query, sub_intent=sub_intent,
                    response=response_text, source="database",
                    items=[item], needs_reorder=item.status in ("OUT_OF_STOCK", "LOW_STOCK"),
                    execution_time_ms=elapsed,
                )

            elapsed = round(time.time() * 1000 - start_ms, 2)
            return InventoryQueryResponse(
                agent="inventory_agent", query=query, sub_intent="stock_check",
                response=f"❌ SKU **{sku}** was not found in the warehouse database. Please verify the SKU code.",
                source="database", items=[], needs_reorder=False, execution_time_ms=elapsed,
            )

        # ─── 8. FUZZY NAME SEARCH ───
        stopwords = {"the", "a", "an", "is", "are", "for", "in", "at", "of",
                     "where", "what", "how", "many"}
        keywords = [w for w in query.lower().split() if len(w) > 3 and w not in stopwords]

        matched_products: List[Product] = []
        for kw in keywords:
            results = _search_products_by_name(kw, db)
            for p in results:
                if not any(m.sku == p.sku for m in matched_products):
                    matched_products.append(p)
            if matched_products:
                break

        if matched_products:
            items = [_product_to_stock_item(p) for p in matched_products]
            lines = [f"Found {len(items)} matching warehouse item(s):"]
            for item in items:
                status_emoji = {"IN_STOCK": "✅", "LOW_STOCK": "⚠️", "OUT_OF_STOCK": "❌"}.get(
                    item.status, "ℹ️")
                lines.append(
                    f"  {status_emoji} **{item.name}** (`{item.sku}`) "
                    f"— {item.location} — **{item.quantity_on_hand} {item.unit}**"
                )
            elapsed = round(time.time() * 1000 - start_ms, 2)
            return InventoryQueryResponse(
                agent="inventory_agent", query=query, sub_intent="stock_check",
                response="\n".join(lines), source="database",
                items=items,
                needs_reorder=any(i.status in ("OUT_OF_STOCK", "LOW_STOCK") for i in items),
                execution_time_ms=elapsed,
            )

        # ─── 9. FALLBACK ───
        elapsed = round(time.time() * 1000 - start_ms, 2)
        return InventoryQueryResponse(
            agent="inventory_agent", query=query, sub_intent="stock_check",
            response=(
                "I could not find a matching SKU or product in the warehouse inventory. "
                "Please specify a SKU (e.g., `SKU-4521`) or query supplier documents, "
                "reorder forecasts, transfers, or equipment health."
            ),
            source="database", items=[], needs_reorder=False, execution_time_ms=elapsed,
        )

    def _handle_reorder_scan(
        self, request: InventoryQueryRequest, db: Optional[Session], start_ms: float
    ) -> InventoryQueryResponse:
        products = _get_all_products(db)
        alerts: List[StockItemInfo] = []
        for p in products:
            item = _product_to_stock_item(p)
            if item.status in ("OUT_OF_STOCK", "LOW_STOCK"):
                alerts.append(item)

        if not alerts:
            elapsed = round(time.time() * 1000 - start_ms, 2)
            return InventoryQueryResponse(
                agent="inventory_agent", query=request.query, sub_intent="reorder_check",
                response="✅ All warehouse items are above their reorder thresholds. No replenishment needed right now.",
                source="database", items=[], needs_reorder=False, execution_time_ms=elapsed,
            )

        lines = [f"⚠️ **{len(alerts)} item(s) below reorder threshold:**"]
        for item in alerts:
            emoji = "❌" if item.status == "OUT_OF_STOCK" else "⚠️"
            lines.append(
                f"  {emoji} **{item.name}** (`{item.sku}`) — "
                f"{item.quantity_on_hand}/{item.reorder_point} {item.unit} "
                f"at `{item.location}`. Suggested reorder: **{item.reorder_quantity} {item.unit}**."
            )
        elapsed = round(time.time() * 1000 - start_ms, 2)
        return InventoryQueryResponse(
            agent="inventory_agent", query=request.query, sub_intent="reorder_check",
            response="\n".join(lines), source="database",
            items=alerts, needs_reorder=True, execution_time_ms=elapsed,
        )


inventory_agent = InventoryAgent()


def handle_inventory_query(
    query: str, sku: Optional[str] = None, user_role: str = "staff", db: Optional[Session] = None
) -> Dict[str, Any]:
    req = InventoryQueryRequest(query=query, sku=sku, user_role=user_role)
    resp = inventory_agent.handle_query(req, db=db)

    return {
        "agent": resp.agent,
        "query": resp.query,
        "sub_intent": resp.sub_intent,
        "response": resp.response,
        "source": resp.source,
        "items": [i.model_dump() for i in resp.items],
        "needs_reorder": resp.needs_reorder,
        "document_result": resp.document_result.model_dump() if resp.document_result else None,
        "prediction_result": resp.prediction_result.model_dump() if resp.prediction_result else None,
        "anomaly_result": resp.anomaly_result.model_dump() if resp.anomaly_result else None,
        "transfer_result": resp.transfer_result.model_dump() if resp.transfer_result else None,
        "equipment_health_result": resp.equipment_health_result.model_dump() if resp.equipment_health_result else None,
        "warehouse_layout": get_full_warehouse_layout(),
        "execution_time_ms": resp.execution_time_ms,
    }
