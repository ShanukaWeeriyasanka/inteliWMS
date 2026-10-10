"""
Inventory MCP tool contracts — the single source of truth shared by the MCP
server (mcp_servers/inventory_mcp_server.py) and the client gateway
(mcp_servers/mcp_tool_client.py).

Every result carries a `status` so callers can tell a real zero apart from
"no such product", "nothing recorded" and "several products match":
  ok         — data found (a quantity of 0 is still ok: it is a real zero)
  not_found  — the product / place does not exist
  empty      — the query is valid but there is nothing to report
  ambiguous  — several products match; ask the user which one
  disabled   — an optional backend (the Digital Twin) is not configured
Transport and server failures never appear here — the gateway reports those.
"""
import re
from typing import Any, Dict, List, Literal, Optional, Type

from pydantic import BaseModel, ConfigDict, Field
from agents.inventory_agent.report_queries import CollectionIntent

from agents.inventory_agent.schemas import (
    AnomalyAlert,
    DepletionPrediction,
    DocumentParseResult,
    EquipmentHealthReport,
    StockItemInfo,
    TransferRecommendation,
)

# ── Tool names ──────────────────────────────────────────────────────────────
GET_PRODUCT_STOCK = "get_product_stock"
SEARCH_PRODUCTS = "search_products"
LIST_LOW_STOCK = "list_low_stock"
QUERY_INVENTORY = "query_inventory"
GET_STOCK_MOVEMENTS = "get_stock_movements"
PREDICT_DEPLETION = "predict_depletion"
CHECK_STOCK_ANOMALIES = "check_stock_anomalies"
EVALUATE_TRANSFER = "evaluate_transfer"
PARSE_SUPPLIER_DOCUMENT = "parse_supplier_document"
ANALYZE_EQUIPMENT_LOG = "analyze_equipment_log"
TWIN_ANSWER = "twin_answer"
PUBLISH_MAP_COMMAND = "publish_map_command"

SKU_PATTERN = re.compile(r"^(?:SKU-\d{3,6}|(?!SKU-)[A-Z0-9]+(?:-[A-Z0-9]+)+)$")
PRD_PATTERN = r"^PRD-\d{5}$"
_SKU_LOOSE = re.compile(r"^\s*sku[-\s]?(\d{3,6})\s*$", re.I)


def canonical_sku(raw: Optional[str]) -> Optional[str]:
    """'sku7788' / 'SKU 7788' / 'SKU-7788' → 'SKU-7788'; anything else → None."""
    if not raw:
        return None
    m = _SKU_LOOSE.match(raw)
    if m:
        return f"SKU-{m.group(1)}"
    value = raw.strip().upper()
    return value if len(value) <= 100 and re.fullmatch(SKU_PATTERN, value) else None


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ── Arguments ───────────────────────────────────────────────────────────────
class ProductStockArgs(_Args):
    sku: str = Field(..., pattern=SKU_PATTERN)


class SearchProductsArgs(_Args):
    text: str = Field(..., min_length=1, max_length=300)
    limit: int = Field(5, ge=1, le=20)


class LowStockArgs(_Args):
    limit: int = Field(50, ge=1, le=200)
    selection: Literal["reorder", "lowest_on_hand"] = "reorder"


class InventoryReportArgs(_Args):
    query: str = Field(..., min_length=1, max_length=2000)
    selected_scope: Optional[str] = Field(None, pattern=r'^WH\d+(?:-F\d+)?(?:-Z\d{2})?(?:-R\d{2})?(?:-S\d{2})?(?:-B\d{2})?$')
    intent: Optional[CollectionIntent] = None


class InventoryReportResult(BaseModel):
    status: Literal['ok','empty','ambiguous','not_found','missing_data']
    response: str
    items: List[StockItemInfo] = Field(default_factory=list)
    as_of: Optional[str] = None
    matched_count: int = 0
    location_scope: Optional[str] = None
    operation: Optional[str] = None
    missing_product_ids: List[str] = Field(default_factory=list)
    source_updated_at: Optional[str] = None
    freshness: Literal['recorded','unknown','stale'] = 'unknown'


class MovementsArgs(_Args):
    sku: Optional[str] = Field(None, pattern=SKU_PATTERN)
    product_id: Optional[str] = Field(None, pattern=PRD_PATTERN)
    limit: int = Field(20, ge=1, le=100)


class SkuArgs(_Args):
    sku: str = Field(..., pattern=SKU_PATTERN)


class AnomalyArgs(_Args):
    sku: Optional[str] = Field(None, pattern=SKU_PATTERN)


class TransferArgs(_Args):
    sku: str = Field(..., pattern=SKU_PATTERN)
    needed_quantity: Optional[int] = Field(None, ge=1, le=100000)


class TextArgs(_Args):
    text: str = Field(..., min_length=1, max_length=5000)


class TwinAnswerArgs(_Args):
    query: str = Field(..., min_length=1, max_length=2000)


class PublishMapCommandArgs(_Args):
    session_id: str = Field(..., min_length=1, max_length=128)
    query_text: str = Field(..., min_length=1, max_length=2000)
    command: Dict[str, Any]


# ── Results ─────────────────────────────────────────────────────────────────
class _Result(BaseModel):
    model_config = ConfigDict(extra="ignore")


class ProductStockResult(_Result):
    status: Literal["ok", "not_found"]
    sku: str
    item: Optional[StockItemInfo] = None
    thresholds_defaulted: bool = False


class ProductCandidate(BaseModel):
    sku: str
    name: str
    score: float


class SearchProductsResult(_Result):
    status: Literal["ok", "not_found", "ambiguous"]
    items: List[StockItemInfo] = Field(default_factory=list)
    candidates: List[ProductCandidate] = Field(default_factory=list)
    matched_terms: List[str] = Field(default_factory=list)


class LowStockResult(_Result):
    status: Literal["ok", "empty"]
    items: List[StockItemInfo] = Field(default_factory=list)
    total_checked: int = 0


class StockMovement(BaseModel):
    movement_type: str
    quantity_change: int
    previous_quantity: Optional[int] = None
    new_quantity: Optional[int] = None
    from_location: Optional[str] = None
    to_location: Optional[str] = None
    reference: Optional[str] = None
    at: Optional[str] = None


class MovementsResult(_Result):
    status: Literal["ok", "empty", "not_found", "disabled"]
    subject_id: Optional[str] = None
    item_name: Optional[str] = None
    source: Literal["inventory_transactions", "digital_twin"] = "inventory_transactions"
    movements: List[StockMovement] = Field(default_factory=list)


class DepletionResult(_Result):
    status: Literal["ok", "not_found"]
    sku: str
    prediction: Optional[DepletionPrediction] = None
    burn_rate_source: Literal["database", "default"] = "database"
    lead_time_source: Literal["database", "default"] = "database"


class AnomalyResult(_Result):
    status: Literal["ok", "empty", "not_found"]
    sku: Optional[str] = None
    alerts: List[AnomalyAlert] = Field(default_factory=list)
    source: Literal["transactions", "demo"] = "transactions"


class TransferResult(_Result):
    status: Literal["ok", "not_found"]
    sku: str
    recommendation: Optional[TransferRecommendation] = None
    quantity_source: Literal["requested", "reorder_quantity", "default_reorder_quantity"] = "requested"
    sibling_data_source: str = 'local_snapshot'


class DocumentResult(_Result):
    status: Literal["ok"]
    result: DocumentParseResult


class EquipmentResult(_Result):
    status: Literal["ok"]
    report: EquipmentHealthReport


class TwinAnswerResult(_Result):
    status: Literal["ok", "not_found", "disabled"]
    command: Optional[Dict[str, Any]] = None
    chat_text: Optional[str] = None


class PublishMapCommandResult(_Result):
    status: Literal["ok"]
    command_id: Optional[str] = None


ARG_MODELS: Dict[str, Type[BaseModel]] = {
    QUERY_INVENTORY: InventoryReportArgs,
    GET_PRODUCT_STOCK: ProductStockArgs,
    SEARCH_PRODUCTS: SearchProductsArgs,
    LIST_LOW_STOCK: LowStockArgs,
    GET_STOCK_MOVEMENTS: MovementsArgs,
    PREDICT_DEPLETION: SkuArgs,
    CHECK_STOCK_ANOMALIES: AnomalyArgs,
    EVALUATE_TRANSFER: TransferArgs,
    PARSE_SUPPLIER_DOCUMENT: TextArgs,
    ANALYZE_EQUIPMENT_LOG: TextArgs,
    TWIN_ANSWER: TwinAnswerArgs,
    PUBLISH_MAP_COMMAND: PublishMapCommandArgs,
}

RESULT_MODELS: Dict[str, Type[BaseModel]] = {
    QUERY_INVENTORY: InventoryReportResult,
    GET_PRODUCT_STOCK: ProductStockResult,
    SEARCH_PRODUCTS: SearchProductsResult,
    LIST_LOW_STOCK: LowStockResult,
    GET_STOCK_MOVEMENTS: MovementsResult,
    PREDICT_DEPLETION: DepletionResult,
    CHECK_STOCK_ANOMALIES: AnomalyResult,
    EVALUATE_TRANSFER: TransferResult,
    PARSE_SUPPLIER_DOCUMENT: DocumentResult,
    ANALYZE_EQUIPMENT_LOG: EquipmentResult,
    TWIN_ANSWER: TwinAnswerResult,
    PUBLISH_MAP_COMMAND: PublishMapCommandResult,
}
