"""
Pydantic schemas and data contracts for the Knowledge Agent.
Ensures strong typing, request validation, and predictable API responses.
"""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

# ==================== Core Agent Query Schemas ====================

class KnowledgeQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Warehouse question, SKU lookup, or SOP enquiry")
    user_role: str = Field("staff", description="Querying user role: 'staff', 'manager', or 'admin'")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Session and Coordinator context")

class LocationItem(BaseModel):
    sku: str
    name: str
    location: str
    quantity: int
    found: bool = True

class LocationResult(BaseModel):
    found: bool
    sku: Optional[str] = None
    name: Optional[str] = None
    location: Optional[str] = None
    quantity: Optional[int] = None
    multiple: Optional[bool] = False
    matches: Optional[List[Dict[str, Any]]] = None
    formatted_message: Optional[str] = None
    message: Optional[str] = None

class RAGHit(BaseModel):
    title: str = Field(..., description="Document or SOP title")
    category: str = Field(..., description="Category tag (e.g. Safety, Storage, Returns)")
    doc_id: str = Field(..., description="Unique document ID (e.g. SOP-SAF-001)")
    content: str = Field(..., description="Matching text paragraph or SOP guideline")
    distance: Optional[float] = Field(None, description="Vector distance if ChromaDB was used")

class ExtractedQuantity(BaseModel):
    value: int
    text: str

class ExtractedProduct(BaseModel):
    matched_text: str
    canonical_name: str

class ExtractedEntities(BaseModel):
    skus: List[str] = Field(default_factory=list)
    locations: List[str] = Field(default_factory=list)
    products: List[ExtractedProduct] = Field(default_factory=list)
    quantities: List[ExtractedQuantity] = Field(default_factory=list)
    dates: List[str] = Field(default_factory=list)
    intent_hint: str = Field("general_query")
    raw_query: Optional[str] = None

class KnowledgeQueryResponse(BaseModel):
    agent: str = Field("knowledge_agent")
    query: str
    response: str
    entities: Dict[str, Any] = Field(default_factory=dict)
    source: str = Field(..., description="'database_location' | 'vector_rag' | 'general_knowledge' | 'none'")
    data: Optional[Dict[str, Any]] = None
    rag_sources: Optional[List[Dict[str, Any]]] = None

# ==================== Tool & Endpoint Specific Schemas ====================

class LocationLookupRequest(BaseModel):
    query_or_sku: str = Field(..., min_length=1, description="Product SKU (e.g., 'SKU-4521') or product name")

class RAGQueryRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Question regarding warehouse procedures or safety rules")
    n_results: int = Field(2, ge=1, le=5, description="Number of excerpts to retrieve")
    category: Optional[str] = Field(None, description="Optional category filter (e.g., 'Safety', 'Storage', 'Returns')")


class ExtractEntitiesRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Unstructured warehouse text or order note")

class IndexDocumentRequest(BaseModel):
    doc_id: str = Field(..., min_length=1, description="Unique document ID (e.g., 'SOP-LOG-004')")
    title: str = Field(..., min_length=1, description="Document title")
    content: str = Field(..., min_length=1, description="Full text content to index into ChromaDB")
    category: str = Field("SOP", description="Category tag (e.g. Safety, Receiving, Storage)")

class HealthResponse(BaseModel):
    status: str = "healthy"
    service: str = "knowledge_agent"
    port: int
    indexed_chunks: int


class ShiftHandoffCreate(BaseModel):
    shift_type: str = Field(..., description="'morning', 'afternoon', or 'night'")
    supervisor: str = Field(..., description="Name or ID of outgoing supervisor")
    summary: str = Field(..., description="Operational summary of the completed shift")
    incidents: Optional[str] = Field(None, description="Any safety incidents, breakdowns, or delays")
    pending_tasks: Optional[str] = Field(None, description="Tasks left incomplete for next shift")


class ShiftHandoffRecord(BaseModel):
    id: int
    shift_type: str
    supervisor: str
    summary: str
    incidents: Optional[str] = None
    pending_tasks: Optional[str] = None
    created_at: str
    formatted_message: str


class ComplianceCheckRequest(BaseModel):
    category: str = Field("stacking", description="'stacking', 'speed', 'hazard', or 'storage'")
    zone: Optional[str] = Field(None, description="Warehouse zone (e.g. 'Zone A', 'Zone C')")
    value: Optional[float] = Field(None, description="Numeric value to check (e.g. tier count 4, speed 7 mph)")
    pallet_condition: Optional[str] = Field(None, description="'good', 'cracked', 'missing_boards'")
    has_ppe: Optional[bool] = Field(True, description="Whether required safety PPE is equipped")

class ComplianceCheckResponse(BaseModel):
    compliant: Optional[bool] = Field(None, description="None when no SOP rule decides it")
    severity: str = Field(..., description="'COMPLIANT', 'WARNING', or 'CRITICAL'")
    sop_id: str
    rule_title: str
    limit_description: str
    violation_reason: Optional[str] = None
    recommended_action: str
    formatted_message: str

class ReturnTriageRequest(BaseModel):
    rma_number: Optional[str] = Field(None, description="Return Merchandise Authorization ID (e.g. 'RMA-4521')")
    sku: Optional[str] = Field(None, description="Product SKU (e.g. 'SKU-4521')")
    condition: str = Field("unopened", description="'unopened', 'opened_complete', 'damaged', 'defective'")
    package_sealed: bool = Field(True, description="Whether original factory seals are intact")
    has_accessories: bool = Field(True, description="Whether all original cables/accessories are present")


class ReturnTriageResponse(BaseModel):
    approved_for_intake: bool
    grade: str = Field(..., description="'Grade A', 'Grade B', 'Grade C (Quarantine)', or 'Rejected'")
    destination: str = Field(..., description="Target floor location (e.g. 'Zone B', 'Bay 11 Quarantine')")
    sop_id: str = "SOP-RET-004"
    reasoning: str
    recommended_action: str
    formatted_message: str
