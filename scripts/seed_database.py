import sys
import os

# Ensure project root is in Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.connection import engine, Base, SessionLocal, init_db
from database.models import User, Product, Order, OrderItem, WarehouseLocation, ShiftHandoff
from security.auth import auth_service

def seed_database():
    print("Initializing tables in database...")
    init_db()
    
    db = SessionLocal()
    try:
        # Clear existing test data safely
        db.query(OrderItem).delete()
        db.query(Order).delete()
        db.query(Product).delete()
        db.query(User).delete()
        db.query(WarehouseLocation).delete()
        db.query(ShiftHandoff).delete()
        
        # Sample Users with properly salted hashes
        users = [
            User(
                username="john_staff",
                name="John Davis",
                email="john.davis@intelliwms.local",
                hashed_password=auth_service._hash_password("pass123"),
                role="staff"
            ),
            User(
                username="sarah_manager",
                name="Sarah Miller",
                email="sarah.miller@intelliwms.local",
                hashed_password=auth_service._hash_password("pass456"),
                role="manager"
            ),
            User(
                username="admin_user",
                name="Alex Vance",
                email="admin@intelliwms.local",
                hashed_password=auth_service._hash_password("admin123"),
                role="admin"
            ),
        ]
        db.add_all(users)
        
        # Sample Locations
        locations = [
            WarehouseLocation(location_code="Zone-A-Aisle-01-Shelf-A1", zone="Zone A", aisle="Aisle 01", shelf="Shelf A1", max_capacity=100, current_occupancy=45),
            WarehouseLocation(location_code="Zone-A-Aisle-02-Shelf-B1", zone="Zone A", aisle="Aisle 02", shelf="Shelf B1", max_capacity=120, current_occupancy=15),
            WarehouseLocation(location_code="Zone-B-Aisle-05-Shelf-C1", zone="Zone B", aisle="Aisle 05", shelf="Shelf C1", max_capacity=200, current_occupancy=110),
            WarehouseLocation(location_code="Zone-C-Aisle-09-Shelf-D1", zone="Zone C", aisle="Aisle 09", shelf="Shelf D1", max_capacity=50, current_occupancy=20),
        ]
        db.add_all(locations)
        
        # Sample Warehouse Inventory
        products = [
            Product(sku="SKU-4521", name="Wireless Barcode Scanner XT-90", category="Electronics", quantity=340, unit_price=129.99, location="Zone-A-Aisle-01-Shelf-A1"),
            Product(sku="SKU-7788", name="Industrial Thermal Label Printer", category="Hardware", quantity=15, unit_price=349.50, location="Zone-A-Aisle-02-Shelf-B1"),
            Product(sku="SKU-9012", name="Heavy Duty Pallet Stretch Wrap", category="Packaging", quantity=85, unit_price=45.00, location="Zone-B-Aisle-05-Shelf-C1"),
            Product(sku="SKU-1104", name="Lithium-Ion Power Cell 48V", category="Hazardous Materials", quantity=28, unit_price=580.00, location="Zone-C-Aisle-09-Shelf-D1", is_hazardous=True),
        ]
        db.add_all(products)
        
        # Sample Orders
        orders = [
            Order(order_id="ORD-1001", customer_name="Acme Logistics Inc.", customer_email="procurement@acmelogistics.com", status="processing", priority="rush", total_amount=2599.80),
            Order(order_id="ORD-1002", customer_name="Global Express Supply", customer_email="orders@globalexpress.com", status="pending", priority="standard", total_amount=1747.50),
            Order(order_id="ORD-1003", customer_name="Apex Freight Systems", customer_email="shipping@apexfreight.com", status="shipped", priority="standard", total_amount=900.00),
        ]
        db.add_all(orders)
        
        # Sample Order Items
        order_items = [
            OrderItem(order_id="ORD-1001", sku="SKU-4521", product_name="Wireless Barcode Scanner XT-90", quantity=20, unit_price=129.99, picked_quantity=20, status="picked"),
            OrderItem(order_id="ORD-1002", sku="SKU-7788", product_name="Industrial Thermal Label Printer", quantity=5, unit_price=349.50, picked_quantity=0, status="pending"),
            OrderItem(order_id="ORD-1003", sku="SKU-9012", product_name="Heavy Duty Pallet Stretch Wrap", quantity=20, unit_price=45.00, picked_quantity=20, status="picked"),
        ]
        db.add_all(order_items)
        
        # Sample Shift Handoff
        handoffs = [
            ShiftHandoff(shift_type="morning", supervisor="Sarah Miller", summary="Morning inbound volume was heavy. 3 containers processed.", incidents="Minor pallet wrap spill in Aisle 04 (cleaned).", pending_tasks="ORD-1005 awaiting supplier restock on SKU-7788.")
        ]
        db.add_all(handoffs)
        
        db.commit()
        print(" SUCCESS: Database initialized and seeded with complete sample dataset!")
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
