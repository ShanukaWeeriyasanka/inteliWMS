import sys
import os

# Ensure project root is in Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.connection import engine, Base, SessionLocal, init_db
from database.models import User, Product, Order, OrderItem
from security.auth import auth_service


def seed_database():
    print("Initializing tables in database...")
    init_db()

    db = SessionLocal()
    try:
        # Clear existing test data (order matters due to FK constraints)
        db.query(OrderItem).delete()
        db.query(Order).delete()
        db.query(Product).delete()
        db.query(User).delete()
        db.commit()

        # ── Users ────────────────────────────────────────────────────────────
        users = [
            User(
                username="john_staff",
                name="John Davis",
                email="john@warehouse.com",
                hashed_password=auth_service._hash_password("pass123"),
                role="staff",
                plan="starter",
            ),
            User(
                username="sarah_manager",
                name="Sarah Miller",
                email="sarah@warehouse.com",
                hashed_password=auth_service._hash_password("pass456"),
                role="manager",
                plan="professional",
            ),
            User(
                username="admin_user",
                name="Alex Vance (Admin)",
                email="admin@warehouse.com",
                hashed_password=auth_service._hash_password("admin123"),
                role="admin",
                plan="enterprise",
            ),
        ]
        db.add_all(users)

        # ── Products (all inventory-agent fields populated from DB) ──────────
        products = [
            Product(
                sku="SKU-4521",
                name="Wireless Barcode Scanner",
                category="Electronics & Tech",
                quantity=340,
                reserved_quantity=10,
                safety_stock=30,
                reorder_point=60,
                reorder_quantity=150,
                unit="units",
                daily_burn_rate=18.5,
                lead_time_days=5,
                unit_price=220.00,
                weight_kg=0.45,
                location="Aisle 12, Shelf B3, Bay 04",
                aisle=12,
                shelf="B3",
                tier="B",
                bay="Bay 04",
                occupancy_pct=78.5,
                temperature="20.2 °C (Climate Monitored)",
                is_hazardous=False,
                max_stack_tier=4,
            ),
            Product(
                sku="SKU-7788",
                name="Thermal Label Printer",
                category="Dispatch Equipment",
                quantity=15,
                reserved_quantity=2,
                safety_stock=10,
                reorder_point=20,
                reorder_quantity=50,
                unit="units",
                daily_burn_rate=6.2,
                lead_time_days=6,
                unit_price=310.00,
                weight_kg=3.80,
                location="Aisle 5, Shelf A1, Bay 02",
                aisle=5,
                shelf="A1",
                tier="A",
                bay="Bay 02",
                occupancy_pct=45.0,
                temperature="21.0 °C (Ambient)",
                is_hazardous=False,
                max_stack_tier=3,
            ),
            Product(
                sku="SKU-9012",
                name="Heavy Duty Pallet Wrap",
                category="Packaging Consumables",
                quantity=5,
                reserved_quantity=0,
                safety_stock=25,
                reorder_point=50,
                reorder_quantity=200,
                unit="rolls",
                daily_burn_rate=32.0,
                lead_time_days=4,
                unit_price=28.00,
                weight_kg=22.0,
                location="Aisle 3, Shelf C2, Bay 08",
                aisle=3,
                shelf="C2",
                tier="C",
                bay="Bay 08",
                occupancy_pct=12.0,
                temperature="18.5 °C (Standard)",
                is_hazardous=False,
                max_stack_tier=5,
            ),
            Product(
                sku="SKU-1088",
                name="Thermal Industrial Label Rolls",
                category="Consumables",
                quantity=120,
                reserved_quantity=20,
                safety_stock=50,
                reorder_point=100,
                reorder_quantity=500,
                unit="rolls",
                daily_burn_rate=45.0,
                lead_time_days=3,
                unit_price=14.50,
                weight_kg=1.20,
                location="Aisle 1, Bay A-03, Shelf A3",
                aisle=1,
                shelf="A3",
                tier="A",
                bay="Bay A-03",
                occupancy_pct=85.0,
                temperature="20.5 °C (Climate Controlled)",
                is_hazardous=False,
                max_stack_tier=6,
            ),
            Product(
                sku="SKU-2045",
                name="Heavy Duty Forklift Battery Lithium",
                category="Heavy Hazmat / Power",
                quantity=42,
                reserved_quantity=5,
                safety_stock=10,
                reorder_point=15,
                reorder_quantity=20,
                unit="units",
                daily_burn_rate=4.5,
                lead_time_days=10,
                unit_price=1250.00,
                weight_kg=420.0,
                location="Aisle 4, Bay B-12, Shelf B12",
                aisle=4,
                shelf="B12",
                tier="B",
                bay="Bay B-12",
                occupancy_pct=68.0,
                temperature="19.0 °C (Hazmat Thermal Guarded)",
                is_hazardous=True,
                max_stack_tier=2,
            ),
        ]
        db.add_all(products)

        # ── Orders & Order Items ─────────────────────────────────────────────
        orders = [
            Order(
                order_id="ORD-1001",
                customer_name="Acme Logistics",
                status="delayed",
                priority="standard",
                total_amount=5500.00,
            ),
            Order(
                order_id="ORD-1002",
                customer_name="Global Express",
                status="pending",
                priority="standard",
                total_amount=1550.00,
            ),
            Order(
                order_id="ORD-1003",
                customer_name="Apex Freight",
                status="shipped",
                priority="standard",
                total_amount=56.00,
            ),
        ]
        db.add_all(orders)

        order_items = [
            OrderItem(
                order_id="ORD-1001",
                sku="SKU-4521",
                product_name="Wireless Barcode Scanner",
                quantity=25,
                unit_price=220.00,
                status="pending",
            ),
            OrderItem(
                order_id="ORD-1002",
                sku="SKU-7788",
                product_name="Thermal Label Printer",
                quantity=5,
                unit_price=310.00,
                status="pending",
            ),
            OrderItem(
                order_id="ORD-1003",
                sku="SKU-9012",
                product_name="Heavy Duty Pallet Wrap",
                quantity=2,
                unit_price=28.00,
                status="pending",
            ),
        ]
        db.add_all(order_items)

        db.commit()
        print(
            "SUCCESS: Database seeded with full inventory fields, users, orders, and items!"
        )
    except Exception as e:
        db.rollback()
        print(f"ERROR during seeding: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
