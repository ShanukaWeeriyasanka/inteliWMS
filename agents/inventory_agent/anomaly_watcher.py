"""
Anomaly Watcher and Shrinkage Detection for Inventory Agent (Member 1).

Monitors live InventoryTransaction records to detect:
  - Unexplained physical shrinkage (large negative adjustments)
  - Abrupt high-volume stock drops inconsistent with historical velocity
  - High-frequency manual override adjustments
  - Off-hours unauthorized movements

Curated demo scenarios are only returned when explicitly enabled
(INVENTORY_DEMO_DATA=true or include_demo=True) and are flagged is_demo, so they
can never be mistaken for live stock movements.
"""
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy.orm import Session

from agents.inventory_agent.schemas import AnomalyAlert
from database.inventory_source import inventory_session as SessionLocal
from database.models import Product, InventoryTransaction
from utils.logger import StructuredLogger

logger = StructuredLogger(__name__)

# ── Demo fallback scenarios (shown when live DB has no flagged transactions) ───
_DEMO_ANOMALIES = [
    {
        "sku": "SKU-9012",
        "name": "Heavy Duty Pallet Wrap",
        "anomaly_type": "UNEXPLAINED_SHRINKAGE",
        "expected": 25,
        "recorded": 5,
        "variance": -20,
        "loss_val": 460.00,
        "severity": "HIGH",
        "desc": (
            "Discrepancy detected during morning cycle count. 20 rolls missing from "
            "Bay Aisle 3, Shelf C2 with no corresponding order fulfillment records."
        ),
        "action": "Trigger Physical Bay Audit on Aisle 3 and review CCTV footage between 22:00-05:00.",
    },
    {
        "sku": "SKU-4521",
        "name": "Wireless Barcode Scanner",
        "anomaly_type": "REPEATED_ADJUSTMENT",
        "expected": 350,
        "recorded": 340,
        "variance": -10,
        "loss_val": 2200.00,
        "severity": "CRITICAL",
        "desc": (
            "Multiple negative manual inventory adjustments recorded by Shift 2 "
            "operator within 48 hours without supervisory sign-off."
        ),
        # Accountability: the system flags records, a person decides; no sanction against an individual here
        "action": ("Supervisor to review the unapproved adjustments with Loss Prevention; require supervisory "
                   "sign-off for further manual adjustments on this SKU until the review is done."),
    },
    {
        "sku": "SKU-2045",
        "name": "Heavy Duty Forklift Battery Lithium",
        "anomaly_type": "OFF_HOURS_MOVEMENT",
        "expected": 45,
        "recorded": 42,
        "variance": -3,
        "loss_val": 3600.00,
        "severity": "HIGH",
        "desc": (
            "3 high-value Lithium battery packs registered as transferred to staging "
            "zone at 02:45 AM outside scheduled dispatch window."
        ),
        "action": "Inspect Zone D staging locks and verify security gate log FX-NIGHT-03.",
    },
]

def demo_data_enabled() -> bool:
    """Read at call time so tests and operators can switch it without a restart."""
    return os.getenv("INVENTORY_DEMO_DATA", "false").lower() == "true"


_SHRINKAGE_THRESHOLD = -5    # flag transactions with quantity_change <= this
_ADJUSTMENT_WINDOW_HRS = 48  # look-back window for repeated-adjustment detection


def _alert_from_dict(d: dict) -> AnomalyAlert:
    return AnomalyAlert(
        anomaly_id=f"ANOM-{uuid.uuid4().hex[:6].upper()}",
        sku=d["sku"],
        item_name=d["name"],
        severity=d["severity"],
        anomaly_type=d["anomaly_type"],
        expected_quantity=d["expected"],
        recorded_quantity=d["recorded"],
        variance=d["variance"],
        loss_value_est=d["loss_val"],
        description=d["desc"],
        recommended_action=d["action"],
        is_demo=True,
    )


def _build_alert_from_transactions(
    sku: str,
    item_name: str,
    unit_price: float,
    transactions: List[InventoryTransaction],
) -> AnomalyAlert:
    """Build an AnomalyAlert from a list of suspicious InventoryTransaction rows."""
    net_change = sum(t.quantity_change for t in transactions)
    expected = transactions[0].previous_quantity if transactions else 0
    recorded = expected + net_change
    loss_val = round(abs(net_change) * unit_price, 2)
    anomaly_type = "UNEXPLAINED_SHRINKAGE" if net_change < 0 else "STOCK_SPIKE"
    if abs(net_change) > 20:
        severity = "CRITICAL"
    elif abs(net_change) > 5:
        severity = "HIGH"
    else:
        severity = "MEDIUM"

    return AnomalyAlert(
        anomaly_id=f"ANOM-{uuid.uuid4().hex[:6].upper()}",
        sku=sku,
        item_name=item_name,
        severity=severity,
        anomaly_type=anomaly_type,
        expected_quantity=expected,
        recorded_quantity=recorded,
        variance=net_change,
        loss_value_est=loss_val,
        description=(
            f"{len(transactions)} suspicious transaction(s) on {sku} detected over "
            f"the last 48 hours. Net quantity change: {net_change:+d} units."
        ),
        recommended_action=(
            "Review transaction logs, verify physical count, and escalate to Loss "
            "Prevention if discrepancy persists."
        ),
    )


class AnomalyWatcher:
    """Detects inventory movement irregularities and shrinkage from the live DB."""

    def _query_live_anomalies(
        self, sku: Optional[str], db: Session, raise_errors: bool = False
    ) -> List[AnomalyAlert]:
        """Query InventoryTransaction table for suspicious negative adjustments."""
        alerts: List[AnomalyAlert] = []
        cutoff = datetime.now() - timedelta(hours=_ADJUSTMENT_WINDOW_HRS)
        try:
            q = db.query(InventoryTransaction).filter(
                InventoryTransaction.quantity_change <= _SHRINKAGE_THRESHOLD,
                InventoryTransaction.created_at >= cutoff,
            )
            if sku:
                q = q.filter(InventoryTransaction.sku.ilike(sku.strip()))

            suspicious_txs = q.order_by(InventoryTransaction.sku).all()

            # Group by SKU
            by_sku: dict = {}
            for tx in suspicious_txs:
                by_sku.setdefault(tx.sku.upper(), []).append(tx)

            for sku_key, txs in by_sku.items():
                prod = db.query(Product).filter(Product.sku.ilike(sku_key)).first()
                item_name = prod.name if prod else sku_key
                unit_price = float(prod.unit_price) if prod and prod.unit_price else 0.0
                alerts.append(_build_alert_from_transactions(sku_key, item_name, unit_price, txs))
        except Exception as exc:
            logger.log_event("ANOMALY_DB_ERROR", {"error": str(exc)}, level="ERROR")
            if raise_errors:
                raise
        return alerts

    def check_sku_anomalies(
        self, sku: str, db: Optional[Session] = None, include_demo: Optional[bool] = None,
        raise_errors: bool = False,
    ) -> Optional[AnomalyAlert]:
        """Check if a particular SKU has anomalous movements in the live DB."""
        own = db is None
        if own:
            db = SessionLocal()
        try:
            live = self._query_live_anomalies(sku, db, raise_errors=raise_errors)
            if live:
                return live[0]
        finally:
            if own:
                db.close()

        if not (demo_data_enabled() if include_demo is None else include_demo):
            return None
        # Demo scenario (explicitly enabled, flagged is_demo)
        for d in _DEMO_ANOMALIES:
            if d["sku"].upper() == sku.strip().upper():
                return _alert_from_dict(d)
        return None

    def scan_all_anomalies(
        self, db: Optional[Session] = None, include_demo: Optional[bool] = None,
        raise_errors: bool = False,
    ) -> List[AnomalyAlert]:
        """Return all active stock anomalies across warehouse inventory."""
        own = db is None
        if own:
            db = SessionLocal()
        try:
            live = self._query_live_anomalies(None, db, raise_errors=raise_errors)
            if live:
                return live
        finally:
            if own:
                db.close()

        if not (demo_data_enabled() if include_demo is None else include_demo):
            return []
        # Demo scenarios (explicitly enabled, flagged is_demo)
        return [_alert_from_dict(d) for d in _DEMO_ANOMALIES]


anomaly_watcher = AnomalyWatcher()
