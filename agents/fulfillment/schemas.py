from pydantic import BaseModel
from typing import Optional
from enum import Enum

class FulfillmentIntent(str, Enum):
    ORDER_STATUS = "ORDER_STATUS"
    ORDER_DELAY = "ORDER_DELAY"
    ORDER_DETAILS = "ORDER_DETAILS"
    SHIPPING_STATUS = "SHIPPING_STATUS"
    FULFILLMENT_PROGRESS = "FULFILLMENT_PROGRESS"
    UNKNOWN_FULFILLMENT = "UNKNOWN_FULFILLMENT"

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
