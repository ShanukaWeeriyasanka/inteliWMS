from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, Numeric, ForeignKey, JSON, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database.connection import Base

class User(Base):
    """Warehouse staff / users with role-based access control."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(150), nullable=True)
    email = Column(String(255), unique=True, index=True, nullable=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), default="staff", index=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class SecurityAuditLog(Base):
    """Persistent audit log of security incidents, injection blocks, and access denials."""
    __tablename__ = "security_audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String(100), index=True)
    event_type = Column(String(100), index=True)
    severity = Column(String(20))
    user_id = Column(String(100), index=True)
    role = Column(String(50))
    ip_address = Column(String(45), nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

class WarehouseLocation(Base):
    """Warehouse layout storage locations."""
    __tablename__ = "warehouse_locations"
    
    id = Column(Integer, primary_key=True, index=True)
    location_code = Column(String(100), unique=True, index=True, nullable=False)
    zone = Column(String(50), index=True, nullable=False)
    aisle = Column(String(20), nullable=True)
    shelf = Column(String(20), nullable=True)
    tier = Column(Integer, default=1)
    max_capacity = Column(Integer, default=100)
    current_occupancy = Column(Integer, default=0)
    status = Column(String(30), default="available")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Product(Base):
    """Warehouse stock / SKUs."""
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    category = Column(String(100), index=True, nullable=True)
    quantity = Column(Integer, default=0, index=True)
    safety_stock = Column(Integer, default=10)
    reorder_point = Column(Integer, default=20)
    reorder_quantity = Column(Integer, default=100)
    reserved_quantity = Column(Integer, default=0)
    unit = Column(String(50), default="units")
    daily_burn_rate = Column(Numeric(8, 2), default=10.0)
    lead_time_days = Column(Integer, default=3)
    unit_price = Column(Numeric(12, 2), default=0.00)
    weight_kg = Column(Numeric(8, 2), default=0.00)
    location = Column(String(100), nullable=True)
    aisle = Column(Integer, nullable=True)
    shelf = Column(String(20), nullable=True)
    tier = Column(String(10), nullable=True)
    bay = Column(String(50), nullable=True)
    occupancy_pct = Column(Numeric(5, 2), default=50.0)
    temperature = Column(String(100), default="20.0 °C Ambient")
    is_hazardous = Column(Boolean, default=False)
    max_stack_tier = Column(Integer, default=4)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class InventoryTransaction(Base):
    """Audit log of inbound, outbound, transfer, and adjustment movements."""
    __tablename__ = "inventory_transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=True)
    sku = Column(String(100), index=True, nullable=False)
    transaction_type = Column(String(50), index=True, nullable=False)
    quantity_change = Column(Integer, nullable=False)
    previous_quantity = Column(Integer, nullable=False)
    new_quantity = Column(Integer, nullable=False)
    source_location = Column(String(100), nullable=True)
    destination_location = Column(String(100), nullable=True)
    reference_id = Column(String(100), nullable=True)
    performed_by = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

class Order(Base):
    """Customer orders / dispatch."""
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String(100), unique=True, index=True, nullable=False)
    customer_name = Column(String(255), nullable=False)
    customer_email = Column(String(255), nullable=True)
    status = Column(String(50), default="pending", index=True)
    priority = Column(String(30), default="standard")
    total_amount = Column(Numeric(12, 2), default=0.00)
    shipping_address = Column(Text, nullable=True)
    # --- Delay root-cause tracking fields ---
    delay_reason = Column(String(255), nullable=True)
    carrier_name = Column(String(150), nullable=True)
    revised_delivery_date = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    items = relationship("OrderItem", backref="order", lazy="selectin", cascade="all, delete-orphan")

    @property
    def sku(self):
        """Primary SKU (from first order item) for single-item order access."""
        if self.items and len(self.items) > 0:
            return self.items[0].sku
        return None

    @sku.setter
    def sku(self, val):
        if not val:
            return
        if self.items and len(self.items) > 0:
            self.items[0].sku = val
        else:
            self.items = [OrderItem(sku=val, quantity=1)]

    @property
    def quantity(self):
        """Total quantity ordered across items for single-item/total order access."""
        if self.items and len(self.items) > 0:
            return sum(item.quantity for item in self.items if item.quantity is not None)
        return None

    @quantity.setter
    def quantity(self, val):
        if val is None:
            return
        if self.items and len(self.items) > 0:
            self.items[0].quantity = val
        else:
            self.items = [OrderItem(sku="", quantity=val)]

class OrderItem(Base):
    """Line items for customer orders."""
    __tablename__ = "order_items"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String(100), ForeignKey("orders.order_id", ondelete="CASCADE"), index=True)
    sku = Column(String(100), index=True, nullable=False)
    product_name = Column(String(255), nullable=True)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(12, 2), default=0.00)
    picked_quantity = Column(Integer, default=0)
    status = Column(String(30), default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Shipment(Base):
    """Shipment and tracking records for dispatched orders."""
    __tablename__ = "shipments"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String(100), ForeignKey("orders.order_id", ondelete="CASCADE"), index=True)
    tracking_number = Column(String(100), unique=True, index=True, nullable=True)
    carrier = Column(String(100), nullable=True)
    status = Column(String(50), default="label_created")
    dispatched_at = Column(DateTime(timezone=True), nullable=True)
    estimated_delivery = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ShiftHandoff(Base):
    """Stores shift transition notes and operational handoffs between warehouse crews."""
    __tablename__ = "shift_handoffs"
    
    id = Column(Integer, primary_key=True, index=True)
    shift_type = Column(String(50), nullable=False)
    supervisor = Column(String(100), nullable=False)
    summary = Column(Text, nullable=False)
    incidents = Column(Text, nullable=True)
    pending_tasks = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

class ReturnLog(Base):
    """Reverse logistics and returns handling."""
    __tablename__ = "returns"
    
    id = Column(Integer, primary_key=True, index=True)
    return_id = Column(String(100), unique=True, index=True, nullable=False)
    order_id = Column(String(100), index=True, nullable=True)
    sku = Column(String(100), index=True, nullable=False)
    quantity = Column(Integer, nullable=False)
    reason = Column(Text, nullable=False)
    condition = Column(String(50), nullable=True)
    action_taken = Column(String(50), nullable=True)
    processed_by = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ComplianceIncident(Base):
    """Safety and compliance violations or alerts."""
    __tablename__ = "compliance_incidents"
    
    id = Column(Integer, primary_key=True, index=True)
    incident_type = Column(String(100), nullable=False)
    severity = Column(String(20), index=True, nullable=False)
    location = Column(String(100), nullable=True)
    description = Column(Text, nullable=False)
    reported_by = Column(String(100), nullable=True)
    status = Column(String(30), default="open", index=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ConversationLog(Base):
    """Audit log of user queries and agent responses."""
    __tablename__ = "conversation_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), index=True, nullable=True)
    user_id = Column(String(100), index=True, nullable=True)
    role = Column(String(50), nullable=True)
    message = Column(Text, nullable=False)
    agent_routed_to = Column(String(100), index=True, nullable=True)
    intent = Column(String(100), nullable=True)
    response = Column(Text, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ChatThread(Base):
    """One chat conversation, owned by one authenticated user (JWT user_id)."""
    __tablename__ = "chat_threads"

    id = Column(String(36), primary_key=True)  # canonical lowercase UUID4
    user_id = Column(String(100), nullable=False, index=True)
    title = Column(String(120), nullable=False, default="New conversation")
    last_agent = Column(String(100), nullable=True)
    # Conversation state the router / inventory agent reuse for follow-ups (see backend/threads/schemas.py)
    context_json = Column(JSON, nullable=True)
    message_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, index=True)

    __table_args__ = (Index("ix_chat_threads_user_updated", "user_id", "updated_at"),)


class ChatMessageRecord(Base):
    """A single user or assistant message inside a chat thread (ordered by id)."""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    thread_id = Column(String(36), ForeignKey("chat_threads.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(100), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # 'user' | 'assistant'
    content = Column(Text, nullable=False)
    agent_used = Column(String(100), nullable=True)
    status = Column(String(30), nullable=True)
    request_id = Column(String(64), nullable=True, index=True)
    meta_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
