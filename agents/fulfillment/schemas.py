from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum

class FulfillmentIntent(str, Enum):
    ORDER_STATUS = "ORDER_STATUS"
    ORDER_DELAY = "ORDER_DELAY"
    ORDER_DETAILS = "ORDER_DETAILS"
    SHIPPING_STATUS = "SHIPPING_STATUS"
    FULFILLMENT_PROGRESS = "FULFILLMENT_PROGRESS"
    FULFILLMENT_PROCEDURE = "FULFILLMENT_PROCEDURE"
    UNKNOWN_FULFILLMENT = "UNKNOWN_FULFILLMENT"

class SOPSourceCitation(BaseModel):
    sop_id: str
    title: str
    section_id: str
    heading: str
    version: Optional[str] = "1.0-DEMO"
    source_file: Optional[str] = "fulfillment_sops.json"
    status: Optional[str] = "demonstration"
    disclaimer: Optional[str] = None
    similarity_score: Optional[float] = None
    raw_distance: Optional[float] = None

class FulfillmentRequest(BaseModel):
    query: str
    user_id: Optional[str] = None
    role: Optional[str] = None
    order_id: Optional[str] = None
    user_plan: Optional[str] = None

class FulfillmentIntentResult(BaseModel):
    intent: FulfillmentIntent
    confidence: float

class FulfillmentResponse(BaseModel):
    success: bool
    order_id: Optional[str] = None
    intent: Optional[FulfillmentIntent] = None
    message: str
    procedural_guidance: Optional[str] = None
    citations: list[SOPSourceCitation] = Field(default_factory=list)
    information_reliability: Optional[str] = "confirmed_facts"

