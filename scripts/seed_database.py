import sys
import os

# Ensure project root is in Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.connection import engine, Base, SessionLocal, init_db
from database.models import User, Product, Order
from security.auth import auth_service

def seed_database():
    print("Initializing tables in database...")
    init_db()
    
    db = SessionLocal()
    try:
        # Clear existing test data
        db.query(User).delete()
        db.query(Product).delete()
        db.query(Order).delete()
        
        # Sample Users with properly salted hashes
        users = [
            User(
                username="john_staff",
                name="John Davis",
                email="john@warehouse.com",
                hashed_password=auth_service._hash_password("pass123"),
                role="staff"
            ),
            User(
                username="sarah_manager",
                name="Sarah Miller",
                email="sarah@warehouse.com",
                hashed_password=auth_service._hash_password("pass456"),
                role="manager"
            ),
            User(
                username="admin_user",
                name="Alex Vance (Admin)",
                email="admin@warehouse.com",
                hashed_password=auth_service._hash_password("admin123"),
                role="admin"
            ),
        ]
        db.add_all(users)
        
        # Sample Warehouse Inventory
        products = [
            Product(sku="SKU-4521", name="Wireless Barcode Scanner", quantity=340, location="Aisle 12, Shelf B3"),
            Product(sku="SKU-7788", name="Thermal Label Printer", quantity=15, location="Aisle 5, Shelf A1"),
            Product(sku="SKU-9012", name="Heavy Duty Pallet Wrap", quantity=5, location="Aisle 3, Shelf C2"),
        ]
        db.add_all(products)
        
        # Sample Orders
        orders = [
            Order(order_id="ORD-1001", customer_name="Acme Logistics", sku="SKU-4521", quantity=25, status="delayed"),
            Order(order_id="ORD-1002", customer_name="Global Express", sku="SKU-7788", quantity=5, status="pending"),
            Order(order_id="ORD-1003", customer_name="Apex Freight", sku="SKU-9012", quantity=2, status="shipped"),
        ]
        db.add_all(orders)
        
        db.commit()
        print(" SUCCESS: Database initialized and seeded with sample users, products, and orders!")
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
