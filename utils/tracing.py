"""
Lightweight tracing on top of the structured logger.

`span()` opens a child span under the current trace (request_context.trace_id),
makes it the current span while the block runs, and logs SPAN_END with the
duration and outcome. Works with both `with` and `async with`. Trace ids follow
W3C traceparent so a caller's trace can be continued and passed on (e.g. to an
HTTP MCP server).
"""
import re
import secrets
import time
from typing import Any, Dict, Optional, Tuple

from utils import request_context
from utils.logger import StructuredLogger

logger = StructuredLogger("tracing")

_TRACEPARENT = re.compile(r"^00-([0-9a-f]{32})-([0-9a-f]{16})-[0-9a-f]{2}$")


def new_trace_id() -> str:
    return secrets.token_hex(16)


def new_span_id() -> str:
    return secrets.token_hex(8)


def parse_traceparent(header: Optional[str]) -> Optional[Tuple[str, str]]:
    """Returns (trace_id, parent_span_id) from a valid W3C traceparent header."""
    if not header:
        return None
    m = _TRACEPARENT.match(header.strip().lower())
    if not m or m.group(1) == "0" * 32 or m.group(2) == "0" * 16:
        return None
    return m.group(1), m.group(2)


def format_traceparent() -> Optional[str]:
    """traceparent for the current span, to pass to downstream services."""
    trace_id = request_context.get("trace_id")
    if not trace_id:
        return None
    return f"00-{trace_id}-{request_context.get('span_id') or new_span_id()}-01"


class span:
    """Child span: `with span("mcp.tool", tool="x") as s: s.set(status="ok")`."""

    def __init__(self, name: str, **attrs: Any):
        self.name = name
        self.attrs: Dict[str, Any] = dict(attrs)
        self.status = "ok"
        self.error_type: Optional[str] = None
        self._tokens = None
        self._start = 0.0
        self.span_id = new_span_id()
        self.parent_span_id: Optional[str] = None

    def set(self, **attrs: Any) -> "span":
        """Add attributes; `status=` overrides the outcome (e.g. a handled failure)."""
        if "status" in attrs:
            self.status = str(attrs.pop("status"))
        self.attrs.update(attrs)
        return self

    def __enter__(self) -> "span":
        self.parent_span_id = request_context.get("span_id")
        bind = {"span_id": self.span_id}
        if not request_context.get("trace_id"):
            bind["trace_id"] = new_trace_id()
        self._tokens = request_context.bind(**bind)
        self._start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        duration_ms = round((time.perf_counter() - self._start) * 1000, 2)
        if exc_type is not None:
            self.status = "error"
            self.error_type = exc_type.__name__
        logger.log_event("SPAN_END", {
            "span": self.name,
            "parent_span_id": self.parent_span_id,
            "duration_ms": duration_ms,
            "status": self.status,
            "error_type": self.error_type,
            **self.attrs,
        })
        request_context.reset(self._tokens)
        return False

    async def __aenter__(self) -> "span":
        return self.__enter__()

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return self.__exit__(exc_type, exc, tb)
