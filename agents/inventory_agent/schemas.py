from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class StockItemInfo(BaseModel):
    """Detailed stock and location information for a specific SKU."""
    sku: str = Field(..., description="Unique product SKU identifier (e.g. SKU-4521)")
    name: str = Field(..., description="Product name")
    category: Optional[str] = Field("General", description="Product category")
    location: str = Field(..., description="Physical coordinates in warehouse (e.g. Aisle 12, Shelf B3)")
    quantity_on_hand: int = Field(0, ge=0, description="Total physical inventory in warehouse")
    reserved_quantity: int = Field(0, ge=0, description="Quantity allocated to pending customer orders")
    available_quantity: int = Field(0, ge=0, description="Immediately pickable inventory (on_hand - reserved)")
    safety_stock: int = Field(10, ge=0, description="Minimum safe threshold before emergency restock")
    reorder_point: int = Field(25, ge=0, description="Stock level triggering automatic reorder")
    reorder_quantity: int = Field(100, gt=0, description="Standard replenishment batch quantity")
    unit: str = Field("units", description="Unit of measure (units, rolls, boxes)")
    status: str = Field("IN_STOCK", description="'IN_STOCK' | 'LOW_STOCK' | 'OUT_OF_STOCK' | 'OVERSTOCKED'")

class InventoryQueryRequest(BaseModel):
    """User query sent to the Inventory Agent from Coordinator or UI."""
    query: str = Field(..., min_length=1, description="Natural language inventory question or SKU query")
    sku: Optional[str] = Field(None, description="Direct SKU if already extracted by coordinator NER")
    user_role: str = Field("staff", description="Caller role ('staff', 'manager', 'admin')")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Session and conversation context")

class InventoryQueryResponse(BaseModel):
    """Standardized response from the Inventory Specialist Agent."""
    agent: str = Field("inventory_agent", description="Specialist agent identifier")
    query: str = Field(..., description="Original user query")
    response: str = Field(..., description="Conversational, natural language answer for staff")
    source: str = Field(..., description="'database' | 'seed_fallback' | 'replenishment_engine' | 'llm_reasoning'")
    items: List[StockItemInfo] = Field(default_factory=list, description="Structured stock items matching the query")
    needs_reorder: bool = Field(False, description="True if any queried item has breached reorder point")
    execution_time_ms: Optional[float] = Field(None, description="Total execution time in milliseconds")

class ReorderCheckRequest(BaseModel):
    """Request payload to scan SKUs for low-stock and replenishment needs."""
    sku: Optional[str] = Field(None, description="Optional specific SKU to evaluate, or None to evaluate all")
    user_role: str = Field("manager", description="Caller's role")

class ReorderItemAlert(BaseModel):
    """Alert details for an item requiring replenishment."""
    sku: str
    name: str
    location: str
    current_stock: int
    reorder_point: int
    safety_stock: int
    recommended_order_quantity: int
    urgency: str = Field(..., description="'NORMAL' | 'URGENT' | 'CRITICAL'")

class ReorderCheckResponse(BaseModel):
    """Summary of items currently requiring reordering."""
    total_items_checked: int
    items_needing_reorder: int
    alerts: List[ReorderItemAlert]
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
