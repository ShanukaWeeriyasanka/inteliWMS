"""
Read-only question autocomplete for the Inventory Agent.

GET /inventory/suggestions?q=... returns 3-5 complete questions for the text being typed.
It only reads product names/SKUs/categories (never quantities), calls no agent, MCP tool or
LLM, and writes nothing. Sending a chosen question still goes through POST /query as usual.
"""
from typing import List, Optional

import anyio
from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from agents.inventory_agent import suggestions
from backend.auth import Identity, resolve_identity
from backend.middleware.error_handler import AppError
from database.connection import get_db
from security.rbac import rbac_manager

router = APIRouter(prefix="/inventory", tags=["Inventory Suggestions"])


class Suggestion(BaseModel):
    text: str
    kind: str
    sku: Optional[str] = None


class SuggestionsResponse(BaseModel):
    suggestions: List[Suggestion]
    degraded: bool = False  # True when the product lookup failed and only generic questions are offered


def require_inventory_reader(authorization: Optional[str] = Header(None)) -> Identity:
    """Signed-in users whose role may ask the Inventory Agent (the agent's own query_location check)."""
    identity = resolve_identity(None, authorization)
    if not identity.authenticated:
        raise AppError(401, "AUTH_REQUIRED", "Sign in to get inventory suggestions")
    if not rbac_manager.check_permission(identity.role, "query_location"):
        raise AppError(403, "PERMISSION_DENIED", "Your role cannot query inventory")
    return identity


@router.get("/suggestions", response_model=SuggestionsResponse)
async def inventory_suggestions(
    q: str = Query(..., min_length=suggestions.MIN_CHARS, max_length=120),
    limit: int = Query(suggestions.MAX_SUGGESTIONS, ge=1, le=suggestions.MAX_SUGGESTIONS),
    identity: Identity = Depends(require_inventory_reader),
    db: Session = Depends(get_db),
):
    def build():
        catalog = suggestions.load_catalog(db)
        return suggestions.build_suggestions(q, catalog, limit=limit), catalog is None

    items, degraded = await anyio.to_thread.run_sync(build)
    return SuggestionsResponse(suggestions=items, degraded=degraded)
