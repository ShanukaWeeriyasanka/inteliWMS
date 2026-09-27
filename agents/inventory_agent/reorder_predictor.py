"""
Reorder Predictor for Inventory Agent (Member 1).

Watches stock-depletion trends and daily burn rates to proactively flag
items about to run out before a physical stockout occurs.
Cross-checks compliance requirements (e.g. hazardous material battery storage).
All burn-rate and lead-time data is read from the live Product database record.
"""
import math
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from agents.inventory_agent.schemas import DepletionPrediction
from database.connection import SessionLocal
from database.models import Product
from utils.logger import StructuredLogger

logger = StructuredLogger(__name__)

# Default fallback values used only when the DB row has no burn_rate / lead_time
_DEFAULT_BURN_RATE = 12.0
_DEFAULT_LEAD_TIME = 3


class ReorderPredictor:
    """Predictive stock depletion analysis engine — fully DB-driven."""

    def predict_depletion(
        self,
        sku: str,
        current_stock: int,
        item_name: str,
        db: Optional[Session] = None,
    ) -> DepletionPrediction:
        """
        Predict stock depletion for a SKU.
        Reads daily_burn_rate and lead_time_days from the live DB Product row.
        """
        own = db is None
        if own:
            db = SessionLocal()

        burn_rate = _DEFAULT_BURN_RATE
        lead_time_days = _DEFAULT_LEAD_TIME
        is_hazardous = False

        try:
            prod = db.query(Product).filter(Product.sku.ilike(sku.strip())).first()
            if prod:
                if prod.daily_burn_rate is not None:
                    burn_rate = float(prod.daily_burn_rate)
                if prod.lead_time_days is not None:
                    lead_time_days = int(prod.lead_time_days)
                is_hazardous = bool(prod.is_hazardous)
        except Exception as exc:
            logger.log_event("REORDER_DB_ERROR", {"sku": sku, "error": str(exc)})
        finally:
            if own:
                db.close()

        if current_stock <= 0:
            days_left = 0.0
            urgency = "CRITICAL"
        else:
            days_left = round(current_stock / burn_rate, 1)
            if days_left <= lead_time_days:
                urgency = "CRITICAL"
            elif days_left <= lead_time_days * 2:
                urgency = "HIGH"
            elif days_left <= lead_time_days * 4:
                urgency = "MEDIUM"
            else:
                urgency = "NORMAL"

        target_date = datetime.now() + timedelta(days=max(0.5, days_left))
        date_str = target_date.strftime("%Y-%m-%d")

        # Economic order quantity: 2-week buffer
        recommended_qty = max(50, int(burn_rate * 14))

        is_regulated = is_hazardous or "battery" in item_name.lower() or "lithium" in item_name.lower()

        logger.log_event("REORDER_PREDICTION_CALCULATED", {
            "sku": sku,
            "stock": current_stock,
            "burn_rate": burn_rate,
            "lead_time_days": lead_time_days,
            "days_until_stockout": days_left,
            "urgency": urgency,
        })

        return DepletionPrediction(
            sku=sku,
            item_name=item_name,
            current_stock=current_stock,
            daily_burn_rate=burn_rate,
            days_until_stockout=days_left,
            projected_stockout_date=date_str,
            lead_time_days=lead_time_days,
            urgency=urgency,
            recommended_reorder_qty=recommended_qty,
            compliance_check_required=is_regulated,
        )

    def scan_all_predictions(self, db: Optional[Session] = None) -> List[DepletionPrediction]:
        """Scans all warehouse products and generates depletion forecasts."""
        own = db is None
        if own:
            db = SessionLocal()
        try:
            products = db.query(Product).all()
            predictions: List[DepletionPrediction] = []
            for p in products:
                # Pass db=None so each call opens its own connection cleanly
                pred = self.predict_depletion(p.sku, p.quantity or 0, p.name, db=db)
                predictions.append(pred)
            return sorted(predictions, key=lambda x: x.days_until_stockout)
        finally:
            if own:
                db.close()


reorder_predictor = ReorderPredictor()

