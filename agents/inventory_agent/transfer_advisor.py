"""
Transfer Advisor for Inventory Agent (Member 1).

Checks sibling distribution centers / warehouses for surplus inventory
before authorizing an external supplier purchase order.
Calculates transfer cost, transit lead-times, and net financial savings.
Vendor cost and lead-time data is read from the live Product DB row.
"""
import json
from pathlib import Path
from typing import Optional, Dict, Any, List

from sqlalchemy.orm import Session

from agents.inventory_agent.schemas import (
    TransferRecommendation,
    SiblingWarehouseOption,
)
from database.connection import SessionLocal
from database.models import Product
from utils.logger import StructuredLogger

logger = StructuredLogger(__name__)

SIBLING_DATA_PATH = Path(__file__).resolve().parent / "data" / "sibling_warehouses.json"

# Fallback vendor profile when DB has no data for a SKU
_DEFAULT_VENDOR_PROFILE = {"unit_cost": 85.00, "lead_days": 5, "name": "Warehouse Inventory Item"}


class TransferAdvisor:
    """Evaluates inter-warehouse inventory transfers against external vendor POs."""

    def __init__(self):
        self._data_cache = None

    def _load_sibling_data(self) -> List[Dict[str, Any]]:
        if self._data_cache is not None:
            return self._data_cache
        try:
            with open(SIBLING_DATA_PATH, "r", encoding="utf-8") as f:
                content = json.load(f)
                self._data_cache = content.get("sibling_warehouses", [])
        except Exception as e:
            logger.log_event("SIBLING_DATA_LOAD_FAIL", {"error": str(e)})
            self._data_cache = []
        return self._data_cache

    def evaluate_transfer(
        self, sku: str, needed_quantity: int = 50, db: Optional[Session] = None
    ) -> TransferRecommendation:
        logger.log_event("TRANSFER_ADVISOR_EVALUATION", {"sku": sku, "needed_qty": needed_quantity})

        sku_clean = sku.strip().upper()

        # Read vendor info from live DB Product row
        item_name = _DEFAULT_VENDOR_PROFILE["name"]
        ext_cost_per_unit = _DEFAULT_VENDOR_PROFILE["unit_cost"]
        ext_lead_days = _DEFAULT_VENDOR_PROFILE["lead_days"]
        own = db is None
        if own:
            db = SessionLocal()
        try:
            prod = db.query(Product).filter(Product.sku.ilike(sku_clean)).first()
            if prod:
                item_name = prod.name
                if prod.unit_price is not None:
                    ext_cost_per_unit = float(prod.unit_price)
                if prod.lead_time_days is not None:
                    ext_lead_days = int(prod.lead_time_days)
        except Exception as exc:
            logger.log_event("TRANSFER_DB_ERROR", {"sku": sku_clean, "error": str(exc)})
        finally:
            if own and db:
                db.close()

        sibling_hubs = self._load_sibling_data()
        options: List[SiblingWarehouseOption] = []
        best_option: Optional[SiblingWarehouseOption] = None

        for hub in sibling_hubs:
            inv = hub.get("inventory", {}).get(sku_clean)
            if inv:
                surplus = inv.get("surplus", 0)
                transit_days = hub.get("transit_days", 2)
                transfer_cost = hub.get("transfer_cost_per_unit", 3.00)
                total_cost = round(transfer_cost * min(needed_quantity, surplus), 2)

                opt = SiblingWarehouseOption(
                    warehouse_id=hub.get("warehouse_id", "WH-UNKNOWN"),
                    warehouse_name=hub.get("name", "Sibling DC"),
                    location=hub.get("location", "US"),
                    available_surplus=surplus,
                    transit_days=transit_days,
                    transfer_cost_per_unit=transfer_cost,
                    total_transfer_cost=total_cost,
                    is_recommended=False
                )
                options.append(opt)

        # Sort options: highest surplus with lowest transit days
        surplus_options = [o for o in options if o.available_surplus > 0]
        surplus_options.sort(key=lambda x: (x.transit_days, -x.available_surplus))

        savings = 0.0
        rec_hub = None

        if surplus_options:
            best = surplus_options[0]
            best.is_recommended = True
            rec_hub = f"{best.warehouse_name} ({best.warehouse_id})"
            
            # External purchase total vs Transfer freight total
            transferable_qty = min(needed_quantity, best.available_surplus)
            ext_total = transferable_qty * ext_cost_per_unit
            freight_total = transferable_qty * best.transfer_cost_per_unit
            savings = round(ext_total - freight_total, 2)
            
            verdict = (
                f"🚚 **Recommended Action**: Transfer **{transferable_qty} units** of `{sku_clean}` from "
                f"**{best.warehouse_name}** ({best.location}).\n"
                f"• Transit Lead Time: **{best.transit_days} day(s)** (vs {ext_lead_days} days external vendor)\n"
                f"• Inter-facility Freight: **${freight_total:,.2f}** (${best.transfer_cost_per_unit}/unit)\n"
                f"• External Purchase Avoidance: **${ext_total:,.2f}**\n"
                f"💰 **Net Logistics Savings: ${savings:,.2f}**"
            )
            if transferable_qty < needed_quantity:
                # The sibling can't cover the whole request: say how much is left to buy
                verdict += (f"\nℹ️ {best.warehouse_name} has only **{best.available_surplus}** spare of the "
                            f"**{needed_quantity}** requested — order the remaining **{needed_quantity - transferable_qty}** "
                            f"from the external vendor ({ext_lead_days} days, ${ext_cost_per_unit:.2f}/unit).")
        else:
            verdict = (
                f"ℹ️ No sibling warehouse currently has surplus stock of `{sku_clean}` above safety thresholds. "
                f"Proceed with external vendor purchase order ({ext_lead_days} days lead time, ${ext_cost_per_unit:.2f}/unit)."
            )

        return TransferRecommendation(
            sku=sku_clean,
            item_name=item_name,
            required_quantity=needed_quantity,
            external_vendor_cost_per_unit=ext_cost_per_unit,
            external_vendor_lead_days=ext_lead_days,
            sibling_options=options,
            recommended_source_warehouse=rec_hub,
            cost_savings_est=max(0.0, savings),
            advisory_verdict=verdict
        )


transfer_advisor = TransferAdvisor()
