from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class StockItemInfo(BaseModel):
    """Detailed stock and location information for a specific SKU."""
    sku: str = Field(..., description="Unique product SKU identifier (e.g. SKU-4521)")
    name: str = Field(..., description="Product name")
    category: Optional[str] = Field("General", description="Product category")
    location: str = Field(..., description="Physical coordinates in warehouse (e.g. Aisle 12, Shelf B3)")
    aisle: Optional[int] = Field(None, description="Numeric aisle index for map visualizer (e.g. 12)")
    shelf: Optional[str] = Field(None, description="Shelf tier code (e.g. B3)")
    tier: Optional[str] = Field(None, description="Tier letter (e.g. A, B, C, D)")
    bay: Optional[str] = Field(None, description="Bay code (e.g. Bay 04)")
    quantity_on_hand: int = Field(0, ge=0, description="Total physical inventory in warehouse")
    reserved_quantity: int = Field(0, ge=0, description="Quantity allocated to pending customer orders")
    available_quantity: int = Field(0, ge=0, description="Immediately pickable inventory (on_hand - reserved)")
    safety_stock: int = Field(10, ge=0, description="Minimum safe threshold before emergency restock")
    reorder_point: int = Field(25, ge=0, description="Stock level triggering automatic reorder")
    reorder_quantity: int = Field(100, gt=0, description="Standard replenishment batch quantity")
    unit: str = Field("units", description="Unit of measure (units, rolls, boxes)")
    status: str = Field("IN_STOCK", description="'IN_STOCK' | 'LOW_STOCK' | 'OUT_OF_STOCK' | 'OVERSTOCKED'")
    occupancy_pct: Optional[float] = Field(None, description="Bay volumetric occupancy %")
    weight_kg: Optional[float] = Field(None, description="Unit or pallet weight in kg")
    temperature: Optional[str] = Field(None, description="Ambient storage condition")


# ─── 1. Document Parser Schemas (Supplier NER & Restock Draft) ───
class ParsedEntity(BaseModel):
    entity_type: str = Field(..., description="'SKU' | 'QUANTITY' | 'DELIVERY_DATE' | 'SUPPLIER' | 'PO_NUMBER'")
    value: Any = Field(..., description="Normalized value")
    raw_text: str = Field(..., description="Raw text snippet extracted from document")

class DraftRestockOrder(BaseModel):
    draft_id: str
    supplier_name: str
    sku: str
    item_name: Optional[str] = None
    quantity: int
    promised_delivery_date: str
    status: str = Field("DRAFT_PENDING_APPROVAL", description="Draft status")
    notes: Optional[str] = None

class DocumentParseResult(BaseModel):
    """Result of unstructured document parsing (Supplier emails, PDFs)."""
    document_type: str = Field(..., description="'supplier_email' | 'supplier_pdf' | 'inbound_manifest' | 'invoice'")
    supplier_name: Optional[str] = None
    extracted_sku: Optional[str] = None
    extracted_quantity: Optional[int] = None
    extracted_delivery_date: Optional[str] = None
    po_reference: Optional[str] = None
    confidence: float = Field(0.95, ge=0.0, le=1.0)
    entities: List[ParsedEntity] = Field(default_factory=list)
    draft_order: Optional[DraftRestockOrder] = None
    raw_summary: str = Field(..., description="Executive summary of the parsed document")


# ─── 2. Reorder Predictor Schemas (Depletion Trends & Burn Rate) ───
class DepletionPrediction(BaseModel):
    """Predictive trend analysis for a SKU's stock depletion velocity."""
    sku: str
    item_name: str
    current_stock: int
    daily_burn_rate: float = Field(..., description="Average units consumed per operating day")
    days_until_stockout: float = Field(..., description="Estimated days before physical stock hits 0")
    projected_stockout_date: str = Field(..., description="ISO date or readable timestamp of predicted runout")
    lead_time_days: int = Field(3, description="Supplier transit and inbound intake lead time")
    urgency: str = Field("NORMAL", description="'CRITICAL' | 'HIGH' | 'MEDIUM' | 'NORMAL'")
    recommended_reorder_qty: int
    compliance_check_required: bool = Field(False, description="Flagged if regulated/hazmat item requiring Knowledge SOP check")


# ─── 3. Anomaly Watcher Schemas (Shrinkage & Inconsistent Movements) ───
class AnomalyAlert(BaseModel):
    """Stock movement pattern inconsistent with normal operations."""
    anomaly_id: str
    sku: str
    item_name: str
    severity: str = Field("MEDIUM", description="'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'")
    anomaly_type: str = Field(..., description="'UNEXPLAINED_SHRINKAGE' | 'OFF_HOURS_MOVEMENT' | 'SPIKE_VARIANCE' | 'REPEATED_ADJUSTMENT'")
    expected_quantity: int
    recorded_quantity: int
    variance: int
    loss_value_est: float = Field(0.0, description="Estimated monetary loss ($)")
    detection_timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    description: str
    recommended_action: str


# ─── 4. Transfer Advisor Schemas (Sibling Warehouse Surplus) ───
class SiblingWarehouseOption(BaseModel):
    warehouse_id: str
    warehouse_name: str
    location: str
    available_surplus: int
    transit_days: int
    transfer_cost_per_unit: float
    total_transfer_cost: float
    is_recommended: bool = False

class TransferRecommendation(BaseModel):
    """Recommendation to transfer stock from sibling warehouse instead of external purchase."""
    sku: str
    item_name: str
    required_quantity: int
    external_vendor_cost_per_unit: float
    external_vendor_lead_days: int
    sibling_options: List[SiblingWarehouseOption] = Field(default_factory=list)
    recommended_source_warehouse: Optional[str] = None
    cost_savings_est: float = Field(0.0, description="Monetary savings transferring vs ordering external")
    advisory_verdict: str = Field(..., description="Recommendation explanation")


# ─── 5. Equipment Health Schemas (Informal Complaint Log NLP) ───
class EquipmentHealthReport(BaseModel):
    """Predictive maintenance report extracted from informal logs without hardware sensors."""
    equipment_id: str = Field(..., description="e.g. 'Forklift 3', 'Conveyor A-02', 'AGV-08'")
    equipment_type: str = Field("Forklift", description="'Forklift' | 'AGV' | 'Conveyor' | 'Scanner' | 'Pallet Jack'")
    reported_symptom: str = Field(..., description="e.g. 'grinding noise when lifting', 'hydraulic fluid leaking'")
    detected_failure_mode: str = Field(..., description="Identified root cause (e.g. Bearing wear, Hydraulic seal failure)")
    breakdown_risk: str = Field("HIGH", description="'LOW' | 'MEDIUM' | 'HIGH' | 'IMMINENT'")
    recurrence_count: int = Field(1, description="Number of times informal complaint appeared in past logs")
    action_required: str = Field(..., description="Maintenance work order recommendation")
    scheduled_maintenance_window: str = Field("Within 24 Hours", description="Suggested timeline")


# ─── Unified Inventory Query Request & Response ───
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
    sub_intent: str = Field("stock_check", description="'stock_check' | 'document_parser' | 'reorder_predictor' | 'anomaly_watcher' | 'transfer_advisor' | 'equipment_health'")
    response: str = Field(..., description="Conversational, natural language answer for staff")
    source: str = Field("database", description="'database' | 'seed_fallback' | 'reorder_predictor' | 'document_parser' | 'anomaly_watcher' | 'transfer_advisor' | 'equipment_health'")
    items: List[StockItemInfo] = Field(default_factory=list, description="Structured stock items matching the query")
    needs_reorder: bool = Field(False, description="True if any queried item has breached reorder point")
    
    # Member 1 specialist payload attachments
    document_result: Optional[DocumentParseResult] = None
    prediction_result: Optional[DepletionPrediction] = None
    anomaly_result: Optional[AnomalyAlert] = None
    transfer_result: Optional[TransferRecommendation] = None
    equipment_health_result: Optional[EquipmentHealthReport] = None
    
    execution_time_ms: Optional[float] = Field(None, description="Total execution time in milliseconds")

class ReorderCheckRequest(BaseModel):
    """Request payload to scan SKUs for low-stock and replenishment needs."""
    sku: Optional[str] = Field(None, description="Optional specific SKU to evaluate, or None to evaluate all")
    user_role: str = Field("manager", description="Caller's role")

class ReorderItemAlert(BaseModel):
    sku: str
    name: str
    location: str
    current_stock: int
    reorder_point: int
    safety_stock: int
    recommended_order_quantity: int
    urgency: str = Field(..., description="'NORMAL' | 'URGENT' | 'CRITICAL'")

class ReorderCheckResponse(BaseModel):
    total_items_checked: int
    items_needing_reorder: int
    alerts: List[ReorderItemAlert]
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
