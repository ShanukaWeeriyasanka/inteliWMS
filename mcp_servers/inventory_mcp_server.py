"""
Inventory MCP server (official `mcp` SDK, FastMCP).

Exposes the inventory agent's tools with typed input/output schemas. The backend
talks to it through mcp_servers/mcp_tool_client.py, by default over the in-memory
MCP transport (same process, real MCP protocol). It can also run on its own:

    python -m mcp_servers.inventory_mcp_server --transport streamable-http --port 8003
    python -m mcp_servers.inventory_mcp_server --transport stdio

Streamable HTTP requires INVENTORY_MCP_TOKEN (sent by the client as a Bearer token).

Every tool opens its own database session and runs the blocking query in a worker
thread. Failures become MCP tool errors with a stable code ("[DB_UNAVAILABLE] ...")
and no internal details; the raw exception only goes to this server's log.
"""
import argparse
import hmac
import ipaddress
import json
import os
import sys
from functools import partial
from typing import Annotated, Any, Callable, Dict, Optional

import anyio
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pydantic import Field, ValidationError
from sqlalchemy.exc import SQLAlchemyError

from agents.inventory_agent import tool_contracts as C
from agents.inventory_agent import tools as T
from database.connection import SessionLocal
from database.twin.connection import TwinUnavailable
from utils.logger import StructuredLogger

logger = StructuredLogger("mcp_servers.inventory")

SERVER_NAME = "intelliwms-inventory"
DEFAULT_PORT = 8003

READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
MUTATION = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)

Sku = Annotated[str, Field(pattern=C.SKU_PATTERN, description="Canonical SKU, e.g. SKU-4521")]
OptSku = Annotated[Optional[str], Field(pattern=C.SKU_PATTERN, description="Canonical SKU, e.g. SKU-4521")]
OptPrd = Annotated[Optional[str], Field(pattern=C.PRD_PATTERN, description="Digital Twin product id")]


def _transport_security() -> TransportSecuritySettings:
    hosts = os.getenv("INVENTORY_MCP_ALLOWED_HOSTS", "127.0.0.1:*,localhost:*,[::1]:*")
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[h.strip() for h in hosts.split(",") if h.strip()],
        allowed_origins=[],
    )


def build_inventory_server(session_factory: Callable[[], Any] = SessionLocal) -> FastMCP:
    server = FastMCP(
        SERVER_NAME,
        instructions="Read-only warehouse inventory lookups plus storing Digital Twin map commands. "
                     "Results carry a status: ok | not_found | empty | ambiguous | disabled.",
        stateless_http=True,
        json_response=True,
        log_level="WARNING",
        transport_security=_transport_security(),
    )

    async def guarded(call: Callable[[], Any], tool: str) -> Any:
        try:
            # abandon_on_cancel: a client timeout returns at once instead of waiting for a stuck query
            return await anyio.to_thread.run_sync(call, abandon_on_cancel=True)
        except ToolError:
            raise
        except SQLAlchemyError as exc:
            logger.log_event("INVENTORY_TOOL_FAILED", {"tool": tool, "code": "DB_UNAVAILABLE",
                                                       "error_type": type(exc).__name__, "error": str(exc)},
                             level="ERROR")
            raise ToolError("[DB_UNAVAILABLE] inventory database query failed")
        except TwinUnavailable as exc:
            logger.log_event("INVENTORY_TOOL_FAILED", {"tool": tool, "code": "TWIN_UNAVAILABLE", "error": str(exc)},
                             level="WARNING")
            raise ToolError("[TWIN_UNAVAILABLE] digital twin database unavailable")
        except ValidationError as exc:
            logger.log_event("INVENTORY_TOOL_FAILED", {"tool": tool, "code": "DATA_INVALID", "error": str(exc)},
                             level="ERROR")
            raise ToolError("[DATA_INVALID] stored inventory data failed validation")
        except Exception as exc:  # never leak internals to the client
            logger.log_event("INVENTORY_TOOL_FAILED", {"tool": tool, "code": "TOOL_FAILED",
                                                       "error_type": type(exc).__name__, "error": str(exc)},
                             level="ERROR")
            raise ToolError("[TOOL_FAILED] inventory tool failed")

    async def with_db(tool: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        def call():
            db = session_factory()
            try:
                return fn(db, *args, **kwargs)
            finally:
                db.close()
        return await guarded(call, tool)

    async def plain(tool: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        return await guarded(partial(fn, *args, **kwargs), tool)

    @server.tool(name=C.GET_PRODUCT_STOCK, annotations=READ,
                 description="On-hand, reserved and available quantity, thresholds, status and location of one SKU.")
    async def get_product_stock(sku: Sku) -> C.ProductStockResult:
        return await with_db(C.GET_PRODUCT_STOCK, T.get_product_stock, sku)

    @server.tool(name=C.SEARCH_PRODUCTS, annotations=READ,
                 description="Find products by name words. 'ambiguous' means several products match.")
    async def search_products(text: Annotated[str, Field(min_length=1, max_length=300)],
                              limit: Annotated[int, Field(ge=1, le=20)] = 5) -> C.SearchProductsResult:
        return await with_db(C.SEARCH_PRODUCTS, T.search_products, text, limit)

    @server.tool(name=C.LIST_LOW_STOCK, annotations=READ,
                 description="Products at or below their reorder point, out-of-stock first.")
    async def list_low_stock(limit: Annotated[int, Field(ge=1, le=200)] = 50) -> C.LowStockResult:
        return await with_db(C.LIST_LOW_STOCK, T.list_low_stock, limit)

    @server.tool(name=C.GET_STOCK_MOVEMENTS, annotations=READ,
                 description="Recent stock movements for a SKU (inventory transactions) or a twin product id.")
    async def get_stock_movements(sku: OptSku = None, product_id: OptPrd = None,
                                  limit: Annotated[int, Field(ge=1, le=100)] = 20) -> C.MovementsResult:
        if bool(sku) == bool(product_id):
            raise ToolError("[INVALID_ARGUMENTS] give exactly one of sku or product_id")
        return await with_db(C.GET_STOCK_MOVEMENTS, T.get_stock_movements, sku, product_id, limit)

    @server.tool(name=C.PREDICT_DEPLETION, annotations=READ,
                 description="Burn-rate based days-until-stockout forecast for one SKU.")
    async def predict_depletion(sku: Sku) -> C.DepletionResult:
        return await with_db(C.PREDICT_DEPLETION, T.predict_depletion, sku)

    @server.tool(name=C.CHECK_STOCK_ANOMALIES, annotations=READ,
                 description="Shrinkage / unexplained adjustments from inventory transactions (one SKU or all).")
    async def check_stock_anomalies(sku: OptSku = None) -> C.AnomalyResult:
        return await with_db(C.CHECK_STOCK_ANOMALIES, T.check_stock_anomalies, sku)

    @server.tool(name=C.EVALUATE_TRANSFER, annotations=READ,
                 description="Compare sibling-warehouse transfer against an external purchase for one SKU.")
    async def evaluate_transfer(sku: Sku,
                                needed_quantity: Annotated[Optional[int], Field(ge=1, le=100000)] = None
                                ) -> C.TransferResult:
        return await with_db(C.EVALUATE_TRANSFER, T.evaluate_transfer, sku, needed_quantity)

    @server.tool(name=C.PARSE_SUPPLIER_DOCUMENT, annotations=READ,
                 description="Extract SKU, quantity, date and PO from a supplier email or document text.")
    async def parse_supplier_document(text: Annotated[str, Field(min_length=1, max_length=5000)]
                                      ) -> C.DocumentResult:
        return await plain(C.PARSE_SUPPLIER_DOCUMENT, T.parse_supplier_document, text)

    @server.tool(name=C.ANALYZE_EQUIPMENT_LOG, annotations=READ,
                 description="Classify an informal equipment complaint into a failure mode and risk.")
    async def analyze_equipment_log(text: Annotated[str, Field(min_length=1, max_length=5000)]
                                    ) -> C.EquipmentResult:
        return await plain(C.ANALYZE_EQUIPMENT_LOG, T.analyze_equipment_log, text)

    @server.tool(name=C.TWIN_ANSWER, annotations=READ,
                 description="Answer a where-is / how-many / route / low-stock question from the Digital Twin map.")
    async def twin_answer(query: Annotated[str, Field(min_length=1, max_length=2000)]) -> C.TwinAnswerResult:
        return await plain(C.TWIN_ANSWER, T.twin_answer, query)

    @server.tool(name=C.PUBLISH_MAP_COMMAND, annotations=MUTATION,
                 description="Store a validated map command so the user's browser session plays it.")
    async def publish_map_command(session_id: Annotated[str, Field(min_length=1, max_length=128)],
                                  query_text: Annotated[str, Field(min_length=1, max_length=2000)],
                                  command: Dict[str, Any]) -> C.PublishMapCommandResult:
        return await plain(C.PUBLISH_MAP_COMMAND, T.publish_map_command, session_id, query_text, command)

    return server


server = build_inventory_server()


# ── Standalone HTTP mode ─────────────────────────────────────────────────────

class BearerAuth:
    """Pure-ASGI bearer token check in front of the streamable HTTP app (lifespan passes through)."""

    def __init__(self, app, token: str):
        self.app = app
        self.token = token

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            supplied = ""
            for k, v in scope.get("headers") or []:
                if k.lower() == b"authorization":
                    raw = v.decode("latin-1")
                    supplied = raw[7:].strip() if raw.lower().startswith("bearer ") else ""
            if not (supplied and hmac.compare_digest(supplied, self.token)):
                body = json.dumps({"error": "unauthorized", "message": "valid bearer token required"}).encode()
                await send({"type": "http.response.start", "status": 401,
                            "headers": [(b"content-type", b"application/json"),
                                        (b"www-authenticate", b'Bearer realm="intelliwms-inventory"')]})
                await send({"type": "http.response.body", "body": body})
                return
        await self.app(scope, receive, send)


def _is_loopback(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host == "localhost"


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="IntelliWMS inventory MCP server")
    parser.add_argument("--transport", choices=["streamable-http", "stdio"], default="streamable-http")
    parser.add_argument("--host", default=os.getenv("INVENTORY_MCP_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("INVENTORY_MCP_PORT", str(DEFAULT_PORT))))
    parser.add_argument("--allow-no-auth", action="store_true",
                        help="Allow HTTP without INVENTORY_MCP_TOKEN (loopback hosts only)")
    args = parser.parse_args(argv)

    if args.transport == "stdio":
        server.run("stdio")
        return 0

    token = os.getenv("INVENTORY_MCP_TOKEN", "")
    if not token and not (args.allow_no_auth and _is_loopback(args.host)):
        print("INVENTORY_MCP_TOKEN is required for --transport streamable-http "
              "(or pass --allow-no-auth with a loopback --host for local testing).", file=sys.stderr)
        return 2

    import uvicorn
    app = server.streamable_http_app()
    app = BearerAuth(app, token) if token else app
    logger.log_event("INVENTORY_MCP_SERVER_START", {"transport": "streamable-http", "host": args.host,
                                                    "port": args.port, "auth": bool(token)})
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
