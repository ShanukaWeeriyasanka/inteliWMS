"""GET /metrics — Prometheus text exposition of the in-process metrics registry."""
import hmac
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import PlainTextResponse

from config.settings import settings
from utils.metrics import REGISTRY

router = APIRouter(tags=["Observability"])


@router.get("/metrics", response_class=PlainTextResponse)
def metrics(authorization: Optional[str] = Header(None)) -> PlainTextResponse:
    if not settings.METRICS_ENABLED:
        raise HTTPException(status_code=404, detail="Metrics are disabled")
    if settings.METRICS_TOKEN:
        supplied = (authorization or "").removeprefix("Bearer ").strip()
        if not hmac.compare_digest(supplied, settings.METRICS_TOKEN):
            raise HTTPException(status_code=401, detail="Metrics token required")
    return PlainTextResponse(REGISTRY.render(), media_type="text/plain; version=0.0.4")
