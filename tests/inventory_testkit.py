"""
Shared helpers for the inventory / MCP / thread tests.

`seeded_inventory_db` builds a throwaway SQLite inventory with known values, so every
assertion about a quantity can be checked against the row it came from:

  SKU-1001  Thermal Label Printer           15 on hand, 2 reserved, reorder point 20  → LOW_STOCK
  SKU-1002  Thermal Industrial Label Rolls  120 on hand, 20 reserved, reorder point 100 → IN_STOCK
  SKU-1003  Stretch Pallet Wrap             0 on hand                                  → OUT_OF_STOCK
  SKU-1004  Wireless Barcode Scanner        340 on hand, 10 reserved, reorder point 60 → OVERSTOCKED
  SKU-1005  Hazmat Spill Kit                8 on hand, no thresholds in the DB          → defaults flagged
"""
import time
from typing import Dict

import jwt
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from config.settings import settings
from database.connection import Base
from database.models import InventoryTransaction, Product

PRODUCTS: Dict[str, dict] = {
    "SKU-1001": dict(name="Thermal Label Printer", quantity=15, reserved_quantity=2, safety_stock=10,
                     reorder_point=20, reorder_quantity=50, unit="units", location="Aisle 5, Shelf A1, Bay 02",
                     aisle=5, shelf="A1", tier="A", bay="Bay 02", category="Electronics", daily_burn_rate=6.2,
                     lead_time_days=6, unit_price=310, occupancy_pct=45, temperature="21.0 C (Ambient)"),
    "SKU-1002": dict(name="Thermal Industrial Label Rolls", quantity=120, reserved_quantity=20, safety_stock=50,
                     reorder_point=100, reorder_quantity=500, unit="rolls", location="Aisle 1, Bay A-03, Shelf A3",
                     aisle=1, shelf="A3", tier="A", bay="Bay A-03", category="Consumables", daily_burn_rate=45,
                     lead_time_days=3, unit_price=14.5),
    "SKU-1003": dict(name="Stretch Pallet Wrap", quantity=0, reserved_quantity=0, safety_stock=25, reorder_point=50,
                     reorder_quantity=200, unit="rolls", location="Aisle 3, Shelf C2, Bay 08", aisle=3, shelf="C2",
                     tier="C", bay="Bay 08", category="Packaging", daily_burn_rate=32, lead_time_days=4,
                     unit_price=28),
    "SKU-1004": dict(name="Wireless Barcode Scanner", quantity=340, reserved_quantity=10, safety_stock=30,
                     reorder_point=60, reorder_quantity=150, unit="units", location="Aisle 12, Shelf B3, Bay 04",
                     aisle=12, shelf="B3", tier="B", bay="Bay 04", category="Electronics", daily_burn_rate=18.5,
                     lead_time_days=5, unit_price=220),
    "SKU-1005": dict(name="Hazmat Spill Kit", quantity=8, reserved_quantity=0, safety_stock=None, reorder_point=None,
                     reorder_quantity=None, unit="kits", location="Aisle 9, Shelf D1", aisle=9, shelf="D1",
                     category="Safety", daily_burn_rate=None, lead_time_days=None, unit_price=95),
}


def seeded_inventory_db(path):
    """Returns (sessionmaker, engine) for a seeded SQLite file at `path`."""
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine, tables=[Product.__table__, InventoryTransaction.__table__])
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    with factory() as s:
        for sku, fields in PRODUCTS.items():
            s.add(Product(sku=sku, **fields))
        s.add(InventoryTransaction(sku="SKU-1004", transaction_type="outbound", quantity_change=-10,
                                   previous_quantity=350, new_quantity=340, source_location="Aisle 12",
                                   destination_location="Dock 4", reference_id="ORD-1001"))
        s.commit()
        # Column defaults fill in None on insert; SKU-1005 must really have no thresholds stored
        s.execute(text("update products set safety_stock = null, reorder_point = null, reorder_quantity = null, "
                       "daily_burn_rate = null, lead_time_days = null where sku = 'SKU-1005'"))
        s.commit()
    return factory, engine


def token_for(user_id: str, role: str = "staff", secret: str = None, expires_in: int = 3600) -> str:
    payload = {"user_id": user_id, "role": role, "exp": int(time.time()) + expires_in, "iat": int(time.time())}
    return jwt.encode(payload, secret or settings.JWT_SECRET, algorithm="HS256")


def auth(user_id: str) -> dict:
    return {"Authorization": f"Bearer {token_for(user_id)}"}
