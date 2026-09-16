"""
Inventory Specialist Agent for IntelliWMS.

Handles:
  - SKU location lookups (DB-backed)
  - Stock level checks with LOW/OUT_OF_STOCK alerts
  - Reorder point evaluations
  - Alias / natural-language product lookups via seed data
  - Heuristic-first intent classification (no LLM dependency for common queries)

All data is sourced from the live Supabase database (Product table),
with a seed-data fallback for environments without a DB connection.
"""
import re
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional, List

from sqlalchemy.orm import Session

from agents.inventory_agent.config import inventory_config
from agents.inventory_agent.schemas import (
    InventoryQueryRequest,
    InventoryQueryResponse,
    StockItemInfo,
    ReorderCheckRequest,
    ReorderCheckResponse,
    ReorderItemAlert,
)
from database.connection import SessionLocal
from database.models import Product
from utils.logger import StructuredLogger

logger = StructuredLogger(__name__)

# ──────────────────────────────────────────────
# Seed data loader (used as alias index + fallback)
# ──────────────────────────────────────────────

_SEED_PATH = inventory_config.SEED_DATA_PATH
_seed_cache: Optional[Dict[str, Any]] = None


def _load_seed() -> Dict[str, Any]:
    global _seed_cache
    if _seed_cache is not None:
        return _seed_cache
    try:
        with open(_SEED_PATH, "r", encoding="utf-8") as f:
            _seed_cache = json.load(f)
    except Exception as e:
        logger.log_event("INVENTORY_SEED_LOAD_ERROR", {"error": str(e)})
        _seed_cache = {"products": [], "warehouse_zones": {}}
    return _seed_cache


def _build_alias_map() -> Dict[str, str]:
    """Returns lowercase alias → SKU mapping from seed data."""
    alias_map: Dict[str, str] = {}
    for p in _load_seed().get("products", []):
        sku = p.get("sku", "")
        for alias in p.get("aliases", []):
            alias_map[alias.lower()] = sku
        alias_map[p.get("name", "").lower()] = sku
        alias_map[sku.lower()] = sku
    return alias_map


_ALIAS_MAP: Dict[str, str] = {}  # lazy-loaded


def _resolve_sku_from_alias(query: str) -> Optional[str]:
    """Fuzzy resolves a natural-language product mention to a canonical SKU."""
    global _ALIAS_MAP
    if not _ALIAS_MAP:
        _ALIAS_MAP = _build_alias_map()
    q_lower = query.lower()
    for alias, sku in _ALIAS_MAP.items():
        if alias in q_lower:
            return sku
    return None


# ──────────────────────────────────────────────
# SKU pattern extractor
# ──────────────────────────────────────────────

_SKU_PATTERN = re.compile(r"\b(SKU-?\d{3,6})\b", re.IGNORECASE)


def _extract_sku(text: str) -> Optional[str]:
    match = _SKU_PATTERN.search(text)
    return match.group(1).upper() if match else None


# ──────────────────────────────────────────────
# Database helpers
# ──────────────────────────────────────────────

def _get_product_by_sku(sku: str, db: Optional[Session] = None) -> Optional[Product]:
    own = db is None
    if own:
        db = SessionLocal()
    try:
        return db.query(Product).filter(Product.sku.ilike(sku.strip())).first()
    finally:
        if own:
            db.close()


def _search_products_by_name(term: str, db: Optional[Session] = None, limit: int = 5) -> List[Product]:
    own = db is None
    if own:
        db = SessionLocal()
    try:
        return (
            db.query(Product)
            .filter(Product.name.ilike(f"%{term}%"))
            .limit(limit)
            .all()
        )
    finally:
        if own:
            db.close()


def _get_all_products(db: Optional[Session] = None) -> List[Product]:
    own = db is None
    if own:
        db = SessionLocal()
    try:
        return db.query(Product).all()
    finally:
        if own:
            db.close()


# ──────────────────────────────────────────────
# Stock status calculator
# ──────────────────────────────────────────────

def _compute_status(qty: int, safety_stock: int, reorder_point: int) -> str:
    if qty == 0:
        return "OUT_OF_STOCK"
    if qty <= safety_stock:
        return "LOW_STOCK"
    if qty > reorder_point * 3:
        return "OVERSTOCKED"
    return "IN_STOCK"


def _product_to_stock_item(p: Product) -> StockItemInfo:
    """Convert a DB Product row to a StockItemInfo schema."""
    qty = p.quantity or 0
    # Defaults from inventory_config
    safety_stock = inventory_config.DEFAULT_SAFETY_STOCK
    reorder_point = inventory_config.DEFAULT_REORDER_POINT
    reorder_qty = inventory_config.DEFAULT_REORDER_QUANTITY

    # Override with richer seed data if available
    seed_product = next(
        (s for s in _load_seed().get("products", []) if s.get("sku") == p.sku),
        None,
    )
    if seed_product:
        safety_stock = seed_product.get("safety_stock", safety_stock)
        reorder_point = seed_product.get("reorder_point", reorder_point)
        reorder_qty = seed_product.get("reorder_quantity", reorder_qty)

    available = max(0, qty - (seed_product.get("reserved_quantity", 0) if seed_product else 0))
    status = _compute_status(qty, safety_stock, reorder_point)

    return StockItemInfo(
        sku=p.sku,
        name=p.name,
        location=p.location or "Location not assigned",
        quantity_on_hand=qty,
        reserved_quantity=(seed_product.get("reserved_quantity", 0) if seed_product else 0),
        available_quantity=available,
        safety_stock=safety_stock,
        reorder_point=reorder_point,
        reorder_quantity=reorder_qty,
        unit=(seed_product.get("unit", "units") if seed_product else "units"),
        status=status,
    )


# ──────────────────────────────────────────────
# Natural-language response builder
# ──────────────────────────────────────────────

def _format_stock_response(item: StockItemInfo) -> str:
    status_emoji = {"IN_STOCK": "✅", "LOW_STOCK": "⚠️", "OUT_OF_STOCK": "❌", "OVERSTOCKED": "📦"}.get(item.status, "ℹ️")
    alert = ""
    if item.status == "OUT_OF_STOCK":
        alert = f"\n🚨 URGENT: Stock is depleted. Reorder {item.reorder_quantity} {item.unit} immediately."
    elif item.status == "LOW_STOCK":
        shortfall = item.reorder_point - item.quantity_on_hand
        alert = f"\n⚠️ LOW STOCK: Below reorder point by {shortfall} {item.unit}. Suggested reorder: {item.reorder_quantity} {item.unit}."

    return (
        f"{status_emoji} **{item.name}** ({item.sku})\n"
        f"📍 Location: {item.location}\n"
        f"📦 Stock: {item.quantity_on_hand} {item.unit} on hand "
        f"({item.available_quantity} available, {item.reserved_quantity} reserved){alert}"
    )


def _format_multi_response(items: List[StockItemInfo]) -> str:
    lines = [f"Found {len(items)} matching items:"]
    for item in items:
        status_emoji = {"IN_STOCK": "✅", "LOW_STOCK": "⚠️", "OUT_OF_STOCK": "❌", "OVERSTOCKED": "📦"}.get(item.status, "ℹ️")
        lines.append(
            f"  {status_emoji} {item.name} ({item.sku}) — {item.location} — "
            f"{item.quantity_on_hand} {item.unit}"
        )
    return "\n".join(lines)


# ──────────────────────────────────────────────
# Heuristic intent detector
# ──────────────────────────────────────────────

def _detect_intent(query: str) -> str:
    """Classify inventory query intent without calling LLM."""
    q = query.lower()
    if any(k in q for k in ["reorder", "replenish", "restock", "need to order", "running low", "low stock", "out of stock"]):
        return "reorder_check"
    if any(k in q for k in ["where is", "location", "aisle", "shelf", "bin", "bay", "find", "locate"]):
        return "location_lookup"
    if any(k in q for k in ["how many", "stock level", "quantity", "count", "available", "on hand", "in stock"]):
        return "stock_check"
    if any(k in q for k in ["status", "check", "update", "info", "details", "tell me about"]):
        return "stock_check"
    # Default to stock check for anything SKU-related
    return "stock_check"


# ──────────────────────────────────────────────
# Core Agent Handler
# ──────────────────────────────────────────────

class InventoryAgent:
    """
    Real Inventory Specialist Agent.
    Resolves stock queries via DB lookups + seed data aliases.
    No LLM calls for common queries — instant heuristic fast-path.
    """

    def handle_query(self, request: InventoryQueryRequest, db: Optional[Session] = None) -> InventoryQueryResponse:
        """
        Main entrypoint for inventory queries.

        Resolution order:
          1. Explicit SKU from request.sku or extracted from query text
          2. Alias/natural-language resolution via seed index
          3. DB fuzzy name search
          4. Fallback: list of reorder-needed items if no match found
        """
        start_ms = time.time() * 1000
        query = request.query.strip()
        intent = _detect_intent(query)

        logger.log_event("INVENTORY_AGENT_QUERY", {
            "query": query[:80],
            "intent": intent,
            "user_role": request.user_role
        })

        # ── 1. Explicit reorder scan ──────────────────────────────────────
        if intent == "reorder_check" and not request.sku and not _extract_sku(query):
            return self._handle_reorder_scan(request, db, start_ms)

        # ── 2. Resolve SKU ────────────────────────────────────────────────
        sku = request.sku or _extract_sku(query) or _resolve_sku_from_alias(query)

        # ── 3. SKU-specific lookup ────────────────────────────────────────
        if sku:
            product = _get_product_by_sku(sku, db)
            if product:
                item = _product_to_stock_item(product)
                response_text = _format_stock_response(item)
                if intent == "location_lookup":
                    response_text = (
                        f"📍 **{item.name}** ({item.sku}) is located at **{item.location}**.\n"
                        f"Current stock: {item.quantity_on_hand} {item.unit} on hand."
                    )
                elapsed = round(time.time() * 1000 - start_ms, 2)
                return InventoryQueryResponse(
                    agent="inventory_agent",
                    query=query,
                    response=response_text,
                    source="database",
                    items=[item],
                    needs_reorder=item.status in ("OUT_OF_STOCK", "LOW_STOCK"),
                    execution_time_ms=elapsed,
                )
            # SKU not in DB
            elapsed = round(time.time() * 1000 - start_ms, 2)
            return InventoryQueryResponse(
                agent="inventory_agent",
                query=query,
                response=f"❌ SKU **{sku}** was not found in the warehouse database. Please verify the SKU code.",
                source="database",
                items=[],
                needs_reorder=False,
                execution_time_ms=elapsed,
            )

        # ── 4. Fuzzy name search ──────────────────────────────────────────
        # Extract significant keywords (>3 chars, skip common words)
        stopwords = {"the", "a", "an", "is", "are", "for", "in", "at", "of", "where", "what", "how", "many"}
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
            response_text = _format_multi_response(items) if len(items) > 1 else _format_stock_response(items[0])
            needs_reorder = any(i.status in ("OUT_OF_STOCK", "LOW_STOCK") for i in items)
            elapsed = round(time.time() * 1000 - start_ms, 2)
            return InventoryQueryResponse(
                agent="inventory_agent",
                query=query,
                response=response_text,
                source="database",
                items=items,
                needs_reorder=needs_reorder,
                execution_time_ms=elapsed,
            )

        # ── 5. Nothing found ──────────────────────────────────────────────
        elapsed = round(time.time() * 1000 - start_ms, 2)
        return InventoryQueryResponse(
            agent="inventory_agent",
            query=query,
            response=(
                "I could not find a matching SKU or product in the warehouse inventory. "
                "Please specify a SKU (e.g., SKU-4521) or a product name."
            ),
            source="database",
            items=[],
            needs_reorder=False,
            execution_time_ms=elapsed,
        )

    def _handle_reorder_scan(
        self, request: InventoryQueryRequest, db: Optional[Session], start_ms: float
    ) -> InventoryQueryResponse:
        """Scans all products and reports those below reorder point."""
        products = _get_all_products(db)
        alerts: List[StockItemInfo] = []
        for p in products:
            item = _product_to_stock_item(p)
            if item.status in ("OUT_OF_STOCK", "LOW_STOCK"):
                alerts.append(item)

        if not alerts:
            elapsed = round(time.time() * 1000 - start_ms, 2)
            return InventoryQueryResponse(
                agent="inventory_agent",
                query=request.query,
                response="✅ All inventory items are above their reorder thresholds. No restocking needed right now.",
                source="database",
                items=[],
                needs_reorder=False,
                execution_time_ms=elapsed,
            )

        lines = [f"⚠️ **{len(alerts)} item(s) need restocking:**"]
        for item in alerts:
            emoji = "❌" if item.status == "OUT_OF_STOCK" else "⚠️"
            lines.append(
                f"  {emoji} {item.name} ({item.sku}) — {item.quantity_on_hand}/{item.reorder_point} {item.unit} "
                f"at {item.location}. Order {item.reorder_quantity} {item.unit}."
            )
        elapsed = round(time.time() * 1000 - start_ms, 2)
        return InventoryQueryResponse(
            agent="inventory_agent",
            query=request.query,
            response="\n".join(lines),
            source="database",
            items=alerts,
            needs_reorder=True,
            execution_time_ms=elapsed,
        )


# Singleton
inventory_agent = InventoryAgent()


def handle_inventory_query(query: str, sku: Optional[str] = None, user_role: str = "staff", db: Optional[Session] = None) -> Dict[str, Any]:
    """
    Public entrypoint for the MCP client / coordinator dispatcher.
    Returns a plain dict compatible with MCP response format.
    """
    req = InventoryQueryRequest(query=query, sku=sku, user_role=user_role)
    resp = inventory_agent.handle_query(req, db=db)
    return {
        "agent": resp.agent,
        "query": resp.query,
        "response": resp.response,
        "source": resp.source,
        "items": [i.model_dump() for i in resp.items],
        "needs_reorder": resp.needs_reorder,
        "execution_time_ms": resp.execution_time_ms,
    }
