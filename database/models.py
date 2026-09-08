from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from database.connection import Base

class User(Base):
    """Warehouse staff / users."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String, default="staff")  # "staff" or "manager"
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Product(Base):
    """Warehouse stock / SKUs."""
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String, unique=True, index=True)
    name = Column(String)
    quantity = Column(Integer, default=0)
    location = Column(String)  # e.g., "Aisle 12, Shelf B3"
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Order(Base):
    """Customer orders / dispatch."""
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String, unique=True, index=True)
    customer_name = Column(String)
    sku = Column(String, index=True)
    quantity = Column(Integer)
    status = Column(String, default="pending")  # "pending", "shipped", "delayed"
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ConversationLog(Base):
    """Audit log of user queries and agent responses."""
    __tablename__ = "conversation_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String)
    message = Column(String)
    agent_routed_to = Column(String)
    response = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
