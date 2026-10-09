"""
Inventory tool implementations served by the inventory MCP server.

Plain synchronous functions over a SQLAlchemy Session. They never swallow
database errors (the server turns those into MCP tool errors), never substitute
a different product, and never make up quantities: every number in a result
comes from a database row, and anything defaulted is flagged as such.
"""
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from agents.inventory_agent.anomaly_watcher import anomaly_watcher
from agents.inventory_agent.config import inventory_config
from agents.inventory_agent.document_parser import document_parser
from agents.inventory_agent.equipment_health import equipment_health_analyzer
from agents.inventory_agent.intents import meaningful_terms
from agents.inventory_agent.reorder_predictor import reorder_predictor
from agents.inventory_agent.tool_contracts import (
    AnomalyResult,
    DepletionResult,
    DocumentResult,
    EquipmentResult,
    LowStockResult,
    MovementsResult,
    ProductCandidate,
    ProductStockResult,
    PublishMapCommandResult,
    SearchProductsResult,
    StockMovement,
    TransferResult,
    TwinAnswerResult,
)
from agents.inventory_agent.schemas import StockItemInfo
from agents.inventory_agent.transfer_advisor import transfer_advisor
from agents.inventory_agent.warehouse_map import get_sku_map_coordinates
from database.models import InventoryTransaction, Product
from database import inventory_source as authority

# ── Stock status (one definition everywhere; matches the twin's v_product_totals) ──

def stock_status(quantity: int, reorder_point: int) -> str:
    if quantity <= 0:
        return "OUT_OF_STOCK"
    if quantity <= reorder_point:
        return "LOW_STOCK"
    if reorder_point > 0 and quantity > reorder_point * 3:
        return "OVERSTOCKED"
    return "IN_STOCK"


def _int_or(value: Any, default: int) -> Tuple[int, bool]:
    """(value, defaulted?) — a stored 0 is a real 0, only NULL falls back."""
    return (int(value), False) if value is not None else (default, True)


def product_to_item(p: Product) -> Tuple[StockItemInfo, bool]:
    """Product row → StockItemInfo. Returns (item, thresholds_defaulted)."""
    qty = int(p.quantity or 0)
    reserved = int(p.reserved_quantity or 0)
    safety, d1 = _int_or(p.safety_stock, inventory_config.DEFAULT_SAFETY_STOCK)
    reorder_point, d2 = _int_or(p.reorder_point, inventory_config.DEFAULT_REORDER_POINT)
    reorder_qty, d3 = _int_or(p.reorder_quantity, inventory_config.DEFAULT_REORDER_QUANTITY)

    aisle, shelf, tier, bay = p.aisle, p.shelf, p.tier, p.bay
    occupancy = float(p.occupancy_pct) if p.occupancy_pct is not None else None
    weight = float(p.weight_kg) if p.weight_kg is not None else None
    temperature = p.temperature
    if not (aisle and shelf):
        # Static rack map (warehouse configuration) for SKUs whose row has no coordinates yet
        meta = get_sku_map_coordinates(p.sku) or {}
        aisle, shelf = aisle or meta.get("aisle"), shelf or meta.get("shelf")
        tier, bay = tier or meta.get("tier"), bay or meta.get("bay")

    item = StockItemInfo(
        sku=p.sku,
        name=p.name,
        category=p.category or "General",
        location=p.location or "Location not assigned",
        aisle=aisle, shelf=shelf, tier=tier, bay=bay,
        quantity_on_hand=max(0, qty),
        reserved_quantity=max(0, reserved),
        available_quantity=max(0, qty - reserved),
        safety_stock=max(0, safety),
        reorder_point=max(0, reorder_point),
        reorder_quantity=max(0, reorder_qty),
        unit=p.unit or "units",
        status=stock_status(qty, reorder_point),
        below_safety_stock=qty <= safety,
        occupancy_pct=occupancy,
        weight_kg=weight,
        temperature=temperature,
    )
    return item, (d1 or d2 or d3)


def _find(db: Session, sku: str) -> Optional[Product]:
    if authority.uses_twin():
        snapshot = authority.snapshot()
        row = authority.find(sku, snapshot['products'])
        return authority.legacy_shape(row) if row else None
    return db.query(Product).filter(Product.sku.ilike(sku.strip())).first()


def canonical_item(row, placements):
    safety, d1 = _int_or(row.get('safety_stock'), inventory_config.DEFAULT_SAFETY_STOCK)
    reorder, d2 = _int_or(row.get('reorder_quantity'), inventory_config.DEFAULT_REORDER_QUANTITY)
    qty = row['total_quantity']
    item = StockItemInfo(
        product_id=row['product_id'], sku=row['sku'], name=row['name'], category=row.get('category'),
        location='; '.join(r['location_label'] for r in placements) or 'Location unassigned',
        placements=placements, quantity_on_hand=qty, reserved_quantity=row['reserved_quantity'],
        available_quantity=row['available_quantity'], quarantined_quantity=row['quarantined_quantity'],
        unplaced_quantity=row['unplaced_quantity'], updated_at=row['updated_at'], data_source=row['data_source'],
        safety_stock=safety, reorder_point=row['reorder_point'], reorder_quantity=reorder,
        unit=row['unit'], status=stock_status(qty, row['reorder_point']), below_safety_stock=qty <= safety,
        weight_kg=row.get('weight_kg'),
    )
    return item, d1 or d2


# ── Read tools ──────────────────────────────────────────────────────────────

def get_product_stock(db: Session, sku: str) -> ProductStockResult:
    if authority.uses_twin():
        snapshot = authority.snapshot()
        row = authority.find(sku, snapshot['products'])
        if row is None:
            return ProductStockResult(status='not_found', sku=sku.upper())
        item, defaulted = canonical_item(row, [r for r in snapshot['locations'] if r['product_id']==row['product_id']])
        return ProductStockResult(status='ok', sku=row['sku'], item=item, thresholds_defaulted=defaulted)
    p = _find(db, sku)
    if p is None:
        return ProductStockResult(status="not_found", sku=sku.upper())
    item, defaulted = product_to_item(p)
    return ProductStockResult(status="ok", sku=p.sku, item=item, thresholds_defaulted=defaulted)


_terms = meaningful_terms


def search_products(db: Session, text: str, limit: int = 5) -> SearchProductsResult:
    """
    Rank products by how much of their name the question mentions.
    One clear winner → ok; several close matches → ambiguous (ask which one).
    """
    if authority.uses_twin():
        import re
        snapshot = authority.snapshot()
        q = text.strip().casefold()
        scored = []
        for row in snapshot['products']:
            exact = any(re.search(r'(?<![\w-])' + re.escape(k.casefold()) + r'(?![\w-])', q)
                        for k in [row['product_id'], row['sku']])
            phrases = [row['name'], *(row.get('aliases') or [])]
            phrase_hit = any(re.search(r'(?<!\w)' + re.escape(k.casefold()) + r'(?!\w)', q) for k in phrases if k)
            terms = set(_terms(row['name']))
            hits = terms & set(_terms(text))
            score = 1.0 if exact else 0.95 if phrase_hit else len(hits) / max(1, len(terms)) * 0.8
            if score:
                scored.append((score, row))
        scored.sort(key=lambda x: (-x[0], x[1]['product_id']))
        if not scored:
            return SearchProductsResult(status='not_found')
        clear = len(scored) == 1 or scored[0][0] - scored[1][0] >= 0.25
        chosen = scored[:1] if clear else [s for s in scored if scored[0][0] - s[0] < 0.25][:limit]
        locations = snapshot['locations']
        items = [canonical_item(p, [r for r in locations if r['product_id'] == p['product_id']])[0] for _, p in chosen]
        return SearchProductsResult(status='ok' if clear else 'ambiguous', items=items,
            candidates=[ProductCandidate(sku=p['sku'], name=p['name'], score=score) for score,p in chosen])
    q_terms = set(_terms(text))
    if not q_terms:
        return SearchProductsResult(status="not_found")
    scored: List[Tuple[float, Product, List[str]]] = []
    for p in db.query(Product).all():
        name_terms = list(dict.fromkeys(_terms(p.name or "")))
        if not name_terms:
            continue
        hits = [t for t in name_terms
                if t in q_terms or any(len(q) >= 4 and len(t) >= 4 and (t.startswith(q) or q.startswith(t))
                                       for q in q_terms)]
        if not hits:
            continue
        score = round(len(hits) / len(name_terms), 3)
        scored.append((score, p, hits))
    if not scored:
        return SearchProductsResult(status="not_found")

    scored.sort(key=lambda x: (-x[0], x[1].sku))
    top = scored[:limit]
    best = top[0][0]
    clear_winner = len(top) == 1 or best - top[1][0] >= 0.25
    chosen = top[:1] if clear_winner else [s for s in top if best - s[0] < 0.25]
    items = [product_to_item(p)[0] for _, p, _ in chosen]
    candidates = [ProductCandidate(sku=p.sku, name=p.name, score=s) for s, p, _ in chosen]
    matched = sorted({h for _, _, hs in chosen for h in hs})
    return SearchProductsResult(status="ok" if clear_winner else "ambiguous", items=items,
                                candidates=candidates, matched_terms=matched)


def list_low_stock(db: Session, limit: int = 50) -> LowStockResult:
    if authority.uses_twin():
        snapshot = authority.snapshot()
        rows = snapshot['products']
        low = [p for p in rows if p['is_low_stock']]
        low.sort(key=lambda p: (not p['is_out_of_stock'], p['total_quantity'], p['product_id']))
        chosen = low[:limit]
        placements = snapshot['locations']
        return LowStockResult(status='ok' if chosen else 'empty', total_checked=len(rows), items=[
            canonical_item(p, [r for r in placements if r['product_id']==p['product_id']])[0] for p in chosen])
    products = db.query(Product).order_by(Product.sku).all()
    low = [item for item, _ in map(product_to_item, products) if item.status in ("OUT_OF_STOCK", "LOW_STOCK")]
    low.sort(key=lambda i: (i.status != "OUT_OF_STOCK", i.quantity_on_hand))
    return LowStockResult(status="ok" if low else "empty", items=low[:limit], total_checked=len(products))


def get_stock_movements(db: Session, sku: Optional[str] = None, product_id: Optional[str] = None,
                        limit: int = 20) -> MovementsResult:
    if authority.uses_twin() and sku:
        row = authority.find(sku)
        if row is None:
            return MovementsResult(status='not_found', subject_id=sku)
        product_id = row['product_id']
    if product_id:
        from database.twin import repository as twin_repo
        from database.twin.connection import is_enabled
        if not is_enabled():
            return MovementsResult(status="disabled", subject_id=product_id, source="digital_twin")
        known = {t["product_id"]: t["name"] for t in twin_repo.get_product_totals()}
        if product_id not in known:
            return MovementsResult(status="not_found", subject_id=product_id, source="digital_twin")
        rows = twin_repo.get_movements(product_id, limit)
        moves = [StockMovement(movement_type=r["type"], quantity_change=int(r["quantity"]),
                               from_location=r.get("from_bin_id"), to_location=r.get("to_bin_id"),
                               reference=r.get("note"), at=str(r.get("created_at"))) for r in rows]
        return MovementsResult(status="ok" if moves else "empty", subject_id=product_id,
                               item_name=known[product_id], source="digital_twin", movements=moves)

    p = _find(db, sku or "")
    if p is None:
        return MovementsResult(status="not_found", subject_id=(sku or "").upper())
    rows = (db.query(InventoryTransaction)
            .filter(InventoryTransaction.sku.ilike(p.sku))
            .order_by(InventoryTransaction.created_at.desc(), InventoryTransaction.id.desc())
            .limit(limit).all())
    moves = [StockMovement(movement_type=r.transaction_type, quantity_change=r.quantity_change,
                           previous_quantity=r.previous_quantity, new_quantity=r.new_quantity,
                           from_location=r.source_location, to_location=r.destination_location,
                           reference=r.reference_id, at=r.created_at.isoformat() if r.created_at else None)
             for r in rows]
    return MovementsResult(status="ok" if moves else "empty", subject_id=p.sku, item_name=p.name, movements=moves)


def predict_depletion(db: Session, sku: str) -> DepletionResult:
    p = _find(db, sku)
    if p is None:
        return DepletionResult(status="not_found", sku=sku.upper())
    pred = reorder_predictor.predict_depletion(p.sku, int(p.quantity or 0), p.name, db=db,
                                              **({'product':p} if authority.uses_twin() else {}))
    return DepletionResult(
        status="ok", sku=p.sku, prediction=pred,
        burn_rate_source="database" if p.daily_burn_rate is not None else "default",
        lead_time_source="database" if p.lead_time_days is not None else "default",
    )


def check_stock_anomalies(db: Session, sku: Optional[str] = None) -> AnomalyResult:
    if sku:
        p = _find(db, sku)
        if p is None:
            return AnomalyResult(status="not_found", sku=sku.upper())
        alert = anomaly_watcher.check_sku_anomalies(p.sku, db, raise_errors=True)
        alerts = [alert] if alert else []
        sku = p.sku
    else:
        alerts = anomaly_watcher.scan_all_anomalies(db, raise_errors=True)
    source = "demo" if any(a.is_demo for a in alerts) else "transactions"
    return AnomalyResult(status="ok" if alerts else "empty", sku=sku, alerts=alerts, source=source)


def evaluate_transfer(db: Session, sku: str, needed_quantity: Optional[int] = None) -> TransferResult:
    p = _find(db, sku)
    if p is None:
        return TransferResult(status="not_found", sku=sku.upper())
    if needed_quantity:
        qty, source = needed_quantity, "requested"
    elif p.reorder_quantity:
        qty, source = int(p.reorder_quantity), "reorder_quantity"
    else:
        qty, source = inventory_config.DEFAULT_REORDER_QUANTITY, "default_reorder_quantity"
    rec = transfer_advisor.evaluate_transfer(p.sku, needed_quantity=qty, db=db,
                                             **({'product':p} if authority.uses_twin() else {}))
    return TransferResult(status="ok", sku=p.sku, recommendation=rec, quantity_source=source)


def parse_supplier_document(text: str) -> DocumentResult:
    return DocumentResult(status="ok", result=document_parser.parse_document(text))


def analyze_equipment_log(text: str) -> EquipmentResult:
    return EquipmentResult(status="ok", report=equipment_health_analyzer.analyze_log(text))


def twin_answer(query: str) -> TwinAnswerResult:
    """Map answer from the Warehouse Digital Twin (built, not stored)."""
    from agents.inventory_agent.twin_navigator import build_twin_answer
    from database.twin.connection import is_enabled
    if not inventory_config.TWIN_ENABLED or not is_enabled():
        return TwinAnswerResult(status="disabled")
    answer = build_twin_answer(query)
    if answer is None:
        return TwinAnswerResult(status="not_found")
    return TwinAnswerResult(status="ok", command=answer.command, chat_text=answer.chat_text)


# ── Mutation tool ───────────────────────────────────────────────────────────

def publish_map_command(session_id: str, query_text: str, command: Dict[str, Any]) -> PublishMapCommandResult:
    """Store a validated map command for the browser session (twin.ui_commands)."""
    from agents.inventory_agent.schemas import UiCommand
    from database.twin import repository as twin_repo
    payload = UiCommand.model_validate(command).to_payload()
    # The full answer travels in chat. Keep the notification below PostgreSQL's payload limit.
    if payload.get('answer_text'):
        payload['answer_text'] = payload['answer_text'][:1200]
    row = twin_repo.insert_ui_command(session_id, query_text, payload)
    return PublishMapCommandResult(status="ok", command_id=row.get("id"))
