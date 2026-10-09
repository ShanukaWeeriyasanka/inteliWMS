"""Thread API models and the per-thread conversation state used for follow-up questions."""
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

MAX_ENTITIES = 5
_SKU = re.compile(r"^SKU-\d{3,6}$")
_PRD = re.compile(r"^PRD-\d{5}$")
_LOCATION = re.compile(r"^WH\d+(-F\d+(-Z\d{2}(-R\d{2}(-S\d{2}(-B\d{2})?)?)?)?)?$")


class PendingCandidate(BaseModel):
    """One option offered in an inventory clarification ("which one did you mean?")."""
    label: str = Field(..., max_length=200)
    sku: Optional[str] = None
    product_id: Optional[str] = None
    location_id: Optional[str] = Field(None, max_length=40, description="A map place (e.g. Rack 2 on Floor 2)")

    @field_validator("location_id")
    @classmethod
    def _location(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not _LOCATION.match(v):
            raise ValueError("not a warehouse location id")
        return v


class InventoryThreadContext(BaseModel):
    """What the inventory agent last talked about in this thread (canonical ids only)."""
    skus: List[str] = Field(default_factory=list)
    product_ids: List[str] = Field(default_factory=list)
    last_sub_intent: Optional[str] = Field(None, max_length=50)
    # Offered candidates; valid for the very next turn only
    pending_clarification: Optional[List[PendingCandidate]] = None
    # The question those candidates answer, so a pick ("2") re-asks it for the chosen option
    pending_query: Optional[str] = Field(None, max_length=300)

    @field_validator("skus")
    @classmethod
    def _skus(cls, v: List[str]) -> List[str]:
        return [s for s in dict.fromkeys(x.upper() for x in v) if _SKU.match(s)][:MAX_ENTITIES]

    @field_validator("product_ids")
    @classmethod
    def _prds(cls, v: List[str]) -> List[str]:
        return [p for p in dict.fromkeys(x.upper() for x in v) if _PRD.match(p)][:MAX_ENTITIES]


class ThreadContext(BaseModel):
    v: int = 1
    last_domain: Optional[str] = None
    last_agent: Optional[str] = None
    turn_count: int = 0
    inventory: InventoryThreadContext = Field(default_factory=InventoryThreadContext)

    def for_routing(self) -> Dict[str, Any]:
        """Small dict the coordinator's classifier and normalizer read."""
        return {
            "last_domain": self.last_domain,
            "last_agent": self.last_agent,
            "has_inventory_entities": bool(self.inventory.skus or self.inventory.product_ids),
            "pending_clarification": [c.label for c in (self.inventory.pending_clarification or [])],
        }


def iso_utc(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class ThreadSummary(BaseModel):
    id: str
    title: str
    last_agent: Optional[str] = None
    message_count: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    agent_used: Optional[str] = None
    status: Optional[str] = None
    request_id: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
