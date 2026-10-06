"""
Request correlation middleware (pure ASGI, so streaming responses such as the
twin SSE feed pass through untouched).

For every HTTP request it:
  - accepts a well-formed X-Request-ID or generates one,
  - continues the caller's W3C traceparent or starts a new trace,
  - binds both into utils.request_context for logs / spans / MCP calls,
  - echoes X-Request-ID and X-Trace-ID on the response,
  - logs REQUEST_COMPLETED with the route *template* (never the raw path or
    query string, which may carry tokens) and records HTTP metrics.
"""
import re
import time
import uuid

from utils import request_context
from utils.logger import StructuredLogger
from utils.metrics import HTTP_DURATION, HTTP_REQUESTS
from utils.tracing import new_span_id, new_trace_id, parse_traceparent

logger = StructuredLogger("backend.request")

_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


def _header(scope, name: bytes):
    for k, v in scope.get("headers") or []:
        if k.lower() == name:
            return v.decode("latin-1")
    return None


class RequestContextMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = _header(scope, b"x-request-id")
        request_id = incoming if incoming and _REQUEST_ID.match(incoming) else uuid.uuid4().hex
        parent = parse_traceparent(_header(scope, b"traceparent"))
        trace_id = parent[0] if parent else new_trace_id()
        span_id = new_span_id()

        scope.setdefault("state", {})
        scope["state"]["request_id"] = request_id
        scope["state"]["trace_id"] = trace_id

        tokens = request_context.bind(request_id=request_id, trace_id=trace_id, span_id=span_id,
                                      thread_id=None, agent=None)
        start = time.perf_counter()
        status_holder = {"status": 500}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
                headers = list(message.get("headers") or [])
                headers.append((b"x-request-id", request_id.encode("latin-1")))
                headers.append((b"x-trace-id", trace_id.encode("latin-1")))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration = time.perf_counter() - start
            route = getattr(scope.get("route"), "path", None) or "unmatched"
            method = scope.get("method", "")
            status = status_holder["status"]
            HTTP_REQUESTS.inc(route=route, method=method, status=status)
            HTTP_DURATION.observe(duration, route=route, method=method)
            logger.log_event("REQUEST_COMPLETED", {
                "method": method,
                "route": route,
                "status": status,
                "duration_ms": round(duration * 1000, 2),
            })
            request_context.reset(tokens)
