"""
Warehouse Digital Twin API.

Read endpoints wrap the views and functions in database/twin/schema.sql; the
browser never runs SQL and never computes a route itself. GET /twin/stream
pushes live changes (stock, alerts, blocked aisles, agent commands) as
Server-Sent Events. All endpoints need a valid IntelliWMS JWT; EventSource
cannot send headers, so the stream also accepts ?access_token=.
"""
import asyncio
import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import DBAPIError
from pydantic import BaseModel, Field
from datetime import datetime
from database.inventory_writes import InventoryConflict, update_placement

from agents.inventory_agent.schemas import UiCommandCreate
from backend.twin.realtime import twin_broker
from backend.twin.sessions import twin_sessions
from config.settings import settings
from database.twin import repository as twin_repo
from database.twin.connection import TwinUnavailable, is_enabled
from security.jwt_handler import jwt_handler
from utils.logger import StructuredLogger

logger = StructuredLogger(__name__)
router = APIRouter(prefix="/twin", tags=["Warehouse Digital Twin"])


def require_twin_user(
    authorization: Optional[str] = Header(None),
    access_token: Optional[str] = Query(None, description="JWT for EventSource clients that cannot set headers"),
) -> Dict[str, Any]:
    token = access_token
    if authorization:
        token = authorization.split(" ", 1)[1] if authorization.startswith("Bearer ") else authorization
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        return jwt_handler.decode_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))


def _call(fn, *args, **kwargs):
    """Run a repository call, mapping database problems to clear HTTP errors."""
    if not is_enabled():
        raise HTTPException(status_code=503, detail="Digital twin disabled: set TWIN_DATABASE_URL to a PostgreSQL database")
    try:
        return fn(*args, **kwargs)
    except TwinUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except InventoryConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except DBAPIError as exc:
        message = str(getattr(exc, "orig", exc)).split("\n")[0]
        raise HTTPException(status_code=400, detail=message)


def _own_session(session_id: Optional[str], user: Dict[str, Any]) -> None:
    """A map session belongs to the first user who uses it; nobody else may read or write it."""
    if session_id and not twin_sessions.claim(session_id, str(user.get("user_id") or "")):
        logger.log_event("TWIN_SESSION_FORBIDDEN", {"user_id": user.get("user_id")}, level="WARNING")
        raise HTTPException(status_code=403, detail="This map session belongs to another user")


def _split_ids(ids: Optional[str]) -> List[str]:
    return [i.strip().upper() for i in (ids or "").split(",") if i.strip()]


@router.get("/status")
def twin_status() -> Dict[str, Any]:
    return {"enabled": is_enabled(), "live": twin_broker.live}


@router.get("/layout", dependencies=[Depends(require_twin_user)])
def twin_layout():
    return _call(twin_repo.get_layout)


@router.get("/nav-edges", dependencies=[Depends(require_twin_user)])
def twin_nav_edges():
    return _call(twin_repo.get_nav_edges)


@router.get("/products", dependencies=[Depends(require_twin_user)])
def twin_products():
    return _call(twin_repo.get_product_totals)


@router.get('/inventory-snapshot', dependencies=[Depends(require_twin_user)])
def twin_inventory_snapshot():
    return _call(twin_repo.get_inventory_snapshot)


class PlacementUpdate(BaseModel):
    product_id: str = Field(pattern=r'^PRD-\d{5}$')
    bin_id: str = Field(pattern=r'^WH\d+-F\d+-Z\d{2}-R\d{2}-S\d{2}-B\d{2}$')
    lot_code: str = Field(default='', max_length=100)
    quantity: int = Field(ge=0)
    reserved_quantity: Optional[int] = Field(default=None, ge=0)
    quarantined_quantity: Optional[int] = Field(default=None, ge=0)
    expected_updated_at: Optional[datetime] = None
    allocate_unplaced: bool = False


@router.get('/stock-placement', dependencies=[Depends(require_twin_user)])
def twin_stock_placements(product_id: str = Query(pattern=r'^PRD-\d{5}$')):
    return _call(twin_repo.get_stock_placements, product_id)


@router.patch('/stock-placement')
def twin_update_placement(payload: PlacementUpdate, user=Depends(require_twin_user)):
    if user.get('role') not in ('manager','admin'):
        raise HTTPException(status_code=403, detail='Manager or admin role required')
    return _call(update_placement, **payload.model_dump(), actor=str(user.get('user_id')))


@router.get("/product-locations", dependencies=[Depends(require_twin_user)])
def twin_product_locations(product_ids: Optional[str] = Query(None, description="Comma-separated PRD ids"),
                           location_prefix: Optional[str] = Query(None)):
    prefix = location_prefix.strip().upper() if location_prefix else None
    return _call(twin_repo.get_product_locations, _split_ids(product_ids), prefix)


@router.get("/rack-fill", dependencies=[Depends(require_twin_user)])
def twin_rack_fill(floor_id: Optional[str] = None):
    return _call(twin_repo.get_rack_fill, floor_id)


@router.get("/locations", dependencies=[Depends(require_twin_user)])
def twin_locations(ids: str = Query(..., description="Comma-separated location ids")):
    return _call(twin_repo.get_locations, _split_ids(ids))


@router.get("/alerts", dependencies=[Depends(require_twin_user)])
def twin_alerts():
    return _call(twin_repo.get_open_alerts)


@router.get("/movements", dependencies=[Depends(require_twin_user)])
def twin_movements(product_id: Optional[str] = None, limit: int = Query(20, ge=1, le=200)):
    return _call(twin_repo.get_movements, product_id, limit)


@router.get("/movements/hourly", dependencies=[Depends(require_twin_user)])
def twin_movements_hourly():
    return _call(twin_repo.get_movements_by_hour)


@router.get("/route", dependencies=[Depends(require_twin_user)])
def twin_route(to_id: str, from_id: Optional[str] = None, prefer: str = "lift"):
    """find_route geometry + get_directions steps for the same trip (same endpoints, same fallback)."""
    return _call(twin_repo.get_route, to_id.strip().upper(),
                 from_id.strip().upper() if from_id else None, prefer)


@router.get("/resolve/product", dependencies=[Depends(require_twin_user)])
def twin_resolve_product(q: str = Query(..., min_length=1, max_length=300)):
    return _call(twin_repo.resolve_product, q)


@router.get("/resolve/location", dependencies=[Depends(require_twin_user)])
def twin_resolve_location(q: str = Query(..., min_length=1, max_length=300)):
    return _call(twin_repo.resolve_location, q)


@router.get("/commands")
def twin_commands(session_id: str, limit: int = Query(10, ge=1, le=50),
                  user: Dict[str, Any] = Depends(require_twin_user)):
    _own_session(session_id, user)
    return _call(twin_repo.get_ui_commands, session_id, limit)


@router.post("/commands")
def twin_create_command(body: UiCommandCreate, user: Dict[str, Any] = Depends(require_twin_user)):
    """Store a command for a browser session (other agents, or the UI's clarify follow-up)."""
    _own_session(body.session_id, user)
    row = _call(twin_repo.insert_ui_command, body.session_id, body.query_text, body.payload.to_payload())
    logger.log_event("TWIN_COMMAND_STORED", {"session_id": body.session_id, "action": body.payload.action,
                                              "user_id": user.get("user_id")})
    return row


@router.get("/stream")
async def twin_stream(request: Request, session_id: Optional[str] = Query(None, max_length=128),
                      user: Dict[str, Any] = Depends(require_twin_user)):
    if not is_enabled():
        raise HTTPException(status_code=503, detail="Digital twin disabled")
    _own_session(session_id, user)
    sub = twin_broker.subscribe(session_id)

    async def events():
        try:
            yield f"event: status\ndata: {json.dumps({'live': twin_broker.live})}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(sub.queue.get(), timeout=settings.TWIN_SSE_KEEPALIVE_S)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                kind = event.pop("type", "change")
                if kind == "change" and event.get("table") == "ui_commands":
                    kind = "command"
                yield f"event: {kind}\ndata: {json.dumps(event, default=str)}\n\n"
        finally:
            twin_broker.unsubscribe(sub)

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
