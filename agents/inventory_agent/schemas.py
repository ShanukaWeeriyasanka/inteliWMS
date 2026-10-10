from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from typing import Annotated, Optional, List, Dict, Any, Literal
from datetime import datetime

class StockItemInfo(BaseModel):
    product_id: Optional[str] = None
    placements: List[Dict[str, Any]] = Field(default_factory=list)
    quarantined_quantity: int = Field(0, ge=0)
    unplaced_quantity: int = Field(0, ge=0)
    updated_at: Optional[str] = None
    data_source: str = 'unverified'
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
    reorder_quantity: int = Field(100, ge=0, description="Standard replenishment batch quantity")
    unit: str = Field("units", description="Unit of measure (units, rolls, boxes)")
    status: str = Field("IN_STOCK", description="'IN_STOCK' | 'LOW_STOCK' (at/below reorder point) | 'OUT_OF_STOCK' | 'OVERSTOCKED'")
    below_safety_stock: bool = Field(False, description="True when on-hand stock is at or below the safety stock")
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
    quantity_unit: Optional[str] = Field(None, description="Unit the document used ('cartons', 'rolls'); None = not stated")
    extracted_delivery_date: Optional[str] = None
    po_reference: Optional[str] = None
    confidence: float = Field(0.95, ge=0.0, le=1.0)
    entities: List[ParsedEntity] = Field(default_factory=list)
    draft_order: Optional[DraftRestockOrder] = None
    problems: List[str] = Field(default_factory=list, description="Why no restock request was drafted")
    raw_summary: str = Field(..., description="Executive summary of the parsed document")


# ─── 2. Reorder Predictor Schemas (Depletion Trends & Burn Rate) ───
class DepletionPrediction(BaseModel):
    """Predictive trend analysis for a SKU's stock depletion velocity."""
    sku: str
    item_name: str
    current_stock: int
    daily_burn_rate: float = Field(..., description="Average units consumed per operating day")
    days_until_stockout: Optional[float] = Field(
        ..., description="Estimated days before physical stock hits 0 (None: no consumption recorded, no stockout)")
    projected_stockout_date: Optional[str] = Field(..., description="ISO date of predicted runout (None: none projected)")
    lead_time_days: int = Field(3, description="Supplier transit and inbound intake lead time")
    urgency: str = Field("NORMAL", description="'CRITICAL' | 'HIGH' | 'MEDIUM' | 'NORMAL'")
    recommended_reorder_qty: int = Field(..., description="Units for the lead time plus the safety buffer (0 = none needed)")
    buffer_days: int = Field(14, description="Days of use the recommended quantity adds on top of the lead time")
    burn_rate_valid: bool = Field(True, description="False when the recorded burn rate is negative (bad data)")
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
    is_demo: bool = Field(False, description="True for curated demo scenarios (INVENTORY_DEMO_DATA), never live data")


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

    # Warehouse Digital Twin: command the map UI should play (see UiCommand)
    ui_command: Optional[Dict[str, Any]] = Field(None, description="Validated UiCommand payload for the twin map")
    ui_command_id: Optional[str] = Field(None, description="ui_commands row id when the command was stored")

    # How the request ended, so the coordinator can tell an answer from a failure
    outcome: Literal["answered", "not_found", "empty", "clarification_needed", "needs_product", "invalid_request",
                     "error", "missing_data"] = "answered"
    error_code: Optional[str] = Field(None, description="Tool / transport failure code when outcome == 'error'")
    context_update: Optional[Dict[str, Any]] = Field(None, description="Canonical product ids for the thread context")
    clarification_candidates: List[Dict[str, Any]] = Field(default_factory=list)

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


# ─── 6. Warehouse Digital Twin UI Command (mirrors database/twin/ui_command.schema.json) ───
ProductId = Annotated[str, StringConstraints(pattern=r"^PRD-\d{5}$")]
FloorId = Annotated[str, StringConstraints(pattern=r"^WH\d+-F\d+$")]
NavNodeId = Annotated[str, StringConstraints(pattern=r"^WH\d+-F\d+-N\d{3}$")]
LocationId = Annotated[str, StringConstraints(pattern=r"^WH\d+(-F\d+(-Z\d{2}(-R\d{2}(-S\d{2}(-B\d{2})?)?)?)?)?$")]
RouteEndpointId = Annotated[
    str,
    StringConstraints(pattern=r"^(PRD-\d{5}|WH\d+-F\d+-N\d{3}|WH\d+(-F\d+(-Z\d{2}(-R\d{2}(-S\d{2}(-B\d{2})?)?)?)?)?)$"),
]

UiAction = Literal["locate_product", "show_location", "navigate", "count", "heatmap",
                   "show_alerts", "clarify", "not_found", "clear"]


class UiScope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    level: Literal["warehouse", "floor", "zone", "rack", "shelf", "bin"]
    id: LocationId


class UiRoute(BaseModel):
    model_config = ConfigDict(extra="forbid")
    from_id: Optional[RouteEndpointId] = Field(None, description="Start; omitted = main entrance")
    to_id: Optional[RouteEndpointId] = Field(None, description="Destination; omitted = main target")
    prefer: Optional[Literal["lift", "stairs", "fastest"]] = None


class UiCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_id: Optional[ProductId] = None
    location_id: Optional[LocationId] = None
    label: str
    score: Optional[float] = None

    @model_validator(mode="after")
    def _exactly_one_target(self) -> "UiCandidate":
        if (self.product_id is None) == (self.location_id is None):
            raise ValueError("a candidate needs exactly one of product_id or location_id")
        return self


class UiCommand(BaseModel):
    """What the agents send to the twin map. IDs only — the UI fetches live numbers itself."""
    model_config = ConfigDict(extra="forbid")

    version: Literal["1.0", "1.1"]
    action: UiAction
    answer_text: str
    product_ids: Optional[List[ProductId]] = None
    location_ids: Optional[List[LocationId]] = None
    floor_id: Optional[FloorId] = None
    scope: Optional[UiScope] = None
    metric: Optional[Literal["fill_ratio", "total_units", "product_quantity", "distinct_products"]] = None
    route: Optional[UiRoute] = None
    alert_types: Optional[List[Literal["low_stock", "out_of_stock", "bin_over_capacity"]]] = None
    candidates: Optional[List[UiCandidate]] = None

    @model_validator(mode="after")
    def _action_requirements(self) -> "UiCommand":
        a = self.action
        if a == "locate_product" and not self.product_ids:
            raise ValueError("locate_product needs at least one product_id")
        if a == "count" and self.scope is None:
            raise ValueError("count needs a scope")
        if a == "heatmap" and self.floor_id is None:
            raise ValueError("heatmap needs a floor_id")
        if a == "show_location" and not self.location_ids:
            raise ValueError("show_location needs at least one location_id")
        if a == "clarify" and len(self.candidates or []) < 2:
            raise ValueError("clarify needs at least two candidates")
        if a == "navigate" and (self.route is None or self.route.to_id is None):
            raise ValueError("navigate needs route.to_id")
        return self

    def to_payload(self) -> Dict[str, Any]:
        return self.model_dump(exclude_none=True)


class UiCommandCreate(BaseModel):
    """POST /twin/commands body: an agent (or the UI) stores a command for a browser session."""
    session_id: str = Field(..., min_length=1, max_length=128)
    query_text: str = Field(..., min_length=1, max_length=2000)
    payload: UiCommand
