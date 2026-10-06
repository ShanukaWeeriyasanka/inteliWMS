"""
MCP tool gateway — how agents reach MCP tools.

    async with inventory_tool_gateway.session("inventory_agent") as tools:
        result = await tools.call("get_product_stock", {"sku": "SKU-4521"})

One MCP client session per request (never shared between requests):
  1. Connect over the configured transport and run MCP tool discovery.
       memory           — the inventory server in this process, real MCP protocol (default)
       streamable_http  — a standalone server at INVENTORY_MCP_URL, Bearer INVENTORY_MCP_TOKEN
  2. Expose to the agent only tools that are discovered AND registered in
     mcp_servers/tool_policy.py AND on that agent's allowlist.
  3. Every call is checked again against the allowlist (unauthorized calls are
     rejected before anything is sent), its arguments are validated against the
     tool contract, it runs under a timeout, the response is validated against
     the result contract, and read-only tools are retried a bounded number of
     times on timeouts / connection failures. Mutations are never retried.
  4. Everything ends in a ToolResult — callers never see transport exceptions.
"""
import json
import os
import random
import re
import time
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum
from typing import Any, AsyncIterator, Callable, Dict, FrozenSet, Iterable, List, Optional, Tuple

import anyio
import httpx
from mcp import ClientSession
from mcp.shared.exceptions import McpError
from pydantic import BaseModel, ValidationError

from agents.inventory_agent.tool_contracts import ARG_MODELS, RESULT_MODELS
from mcp_servers.tool_policy import ToolKind, allowed_tools, is_allowed, kind_of, TOOL_REGISTRY
from utils.logger import StructuredLogger
from utils.metrics import (
    MCP_ERRORS,
    MCP_TOOL_CALLS,
    MCP_TOOL_DURATION,
    MCP_TOOL_REJECTIONS,
    MCP_TOOL_RETRIES,
    MCP_TOOL_TIMEOUTS,
)
from utils.tracing import format_traceparent, span

logger = StructuredLogger(__name__)


class ToolStatus(str, Enum):
    # A valid tool result (the tool ran and answered)
    OK = "ok"
    NOT_FOUND = "not_found"
    EMPTY = "empty"
    AMBIGUOUS = "ambiguous"
    DISABLED = "disabled"
    # No usable result
    INVALID_ARGUMENTS = "invalid_arguments"
    UNAUTHORIZED = "unauthorized"
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"
    TOOL_ERROR = "tool_error"
    INVALID_RESPONSE = "invalid_response"
    CONFIG_ERROR = "config_error"


FAILURE_STATUSES = frozenset({
    ToolStatus.INVALID_ARGUMENTS, ToolStatus.UNAUTHORIZED, ToolStatus.TIMEOUT, ToolStatus.UNAVAILABLE,
    ToolStatus.TOOL_ERROR, ToolStatus.INVALID_RESPONSE, ToolStatus.CONFIG_ERROR,
})
RETRYABLE = frozenset({ToolStatus.TIMEOUT, ToolStatus.UNAVAILABLE})


@dataclass
class ToolResult:
    tool: str
    status: ToolStatus
    data: Optional[BaseModel] = None
    error_code: Optional[str] = None
    duration_ms: float = 0.0
    attempts: int = 0

    @property
    def failed(self) -> bool:
        return self.status in FAILURE_STATUSES


# ── Configuration ────────────────────────────────────────────────────────────

_TRANSPORT_ALIASES = {"memory": "memory", "in-memory": "memory", "inprocess": "memory",
                      "streamable_http": "streamable_http", "streamable-http": "streamable_http",
                      "http": "streamable_http"}


@dataclass(frozen=True)
class InventoryMCPSettings:
    transport: str = "memory"
    url: str = ""
    token: str = ""
    timeout_s: float = 5.0
    max_retries: int = 2
    backoff_s: float = 0.2
    parse_problems: Tuple[str, ...] = ()

    @classmethod
    def from_env(cls) -> "InventoryMCPSettings":
        """Read at call time so configuration can change without a restart (and in tests)."""
        problems: List[str] = []

        def number(name: str, default: str, cast, minimum: float):
            raw = os.getenv(name, default)
            try:
                value = cast(raw)
                if value < minimum:
                    raise ValueError
                return value
            except ValueError:
                problems.append(f"{name} must be a number >= {minimum} (got '{raw}')")
                return cast(default)

        raw_transport = os.getenv("INVENTORY_MCP_TRANSPORT", "memory").strip().lower()
        transport = _TRANSPORT_ALIASES.get(raw_transport)
        if transport is None:
            problems.append(f"INVENTORY_MCP_TRANSPORT must be 'memory' or 'streamable_http' (got '{raw_transport}')")
            transport = raw_transport
        return cls(
            transport=transport,
            url=os.getenv("INVENTORY_MCP_URL", "").strip(),
            token=os.getenv("INVENTORY_MCP_TOKEN", "").strip(),
            timeout_s=number("INVENTORY_MCP_TIMEOUT_S", "5", float, 0.1),
            max_retries=int(number("INVENTORY_MCP_MAX_RETRIES", "2", int, 0)),
            backoff_s=number("INVENTORY_MCP_RETRY_BACKOFF_S", "0.2", float, 0.0),
            parse_problems=tuple(problems),
        )

    def problems(self) -> List[str]:
        """Exact, secret-free reasons the configuration cannot work."""
        out = list(self.parse_problems)
        if self.transport == "streamable_http":
            if not self.url:
                out.append("INVENTORY_MCP_URL is required when INVENTORY_MCP_TRANSPORT=streamable_http")
            elif not re.match(r"^https?://", self.url):
                out.append("INVENTORY_MCP_URL must start with http:// or https://")
            if not self.token:
                out.append("INVENTORY_MCP_TOKEN is required when INVENTORY_MCP_TRANSPORT=streamable_http")
        return out

    def describe(self) -> Dict[str, Any]:
        problems = self.problems()
        return {"transport": self.transport, "configured": not problems, "url_set": bool(self.url),
                "token_set": bool(self.token), "timeout_s": self.timeout_s, "max_retries": self.max_retries,
                "problems": problems}


# ── Transport error trap ─────────────────────────────────────────────────────

class _TransportFailure(Exception):
    def __init__(self, cause: BaseException):
        super().__init__(str(cause))
        self.cause = cause


class _Trap:
    """
    The MCP client hands transport exceptions (HTTP 401, connection refused, ...) to the
    session's message handler instead of failing the pending request, which would then
    hang until its read timeout. The trap records the error and cancels the waiting call.
    """
    _UNSET = object()

    def __init__(self):
        self.error: Optional[BaseException] = None
        self._scope: Optional[anyio.CancelScope] = None

    async def handler(self, message: Any) -> None:
        if isinstance(message, Exception):
            self.error = message
            if self._scope is not None:
                self._scope.cancel()

    async def run(self, call: Callable[[], Any], timeout_s: float) -> Any:
        self.error = None
        result = self._UNSET
        with anyio.CancelScope() as scope:
            self._scope = scope
            try:
                with anyio.fail_after(timeout_s):
                    result = await call()
            finally:
                self._scope = None
        if result is self._UNSET:
            raise _TransportFailure(self.error or ConnectionError("MCP transport closed"))
        return result


def _leaves(exc: BaseException) -> Iterable[BaseException]:
    if isinstance(exc, _TransportFailure):
        yield from _leaves(exc.cause)
    elif isinstance(exc, BaseExceptionGroup):
        for e in exc.exceptions:
            yield from _leaves(e)
    else:
        yield exc


def classify_exception(exc: BaseException) -> Tuple[ToolStatus, str]:
    for e in _leaves(exc):
        if isinstance(e, httpx.HTTPStatusError):
            code = e.response.status_code
            if code in (401, 403):
                return ToolStatus.UNAUTHORIZED, "MCP_AUTH_FAILED"
            return ToolStatus.UNAVAILABLE, f"MCP_HTTP_{code}"
        if isinstance(e, (TimeoutError, httpx.TimeoutException)):
            return ToolStatus.TIMEOUT, "MCP_TIMEOUT"
        if isinstance(e, (httpx.TransportError, ConnectionError, OSError)):
            return ToolStatus.UNAVAILABLE, "MCP_CONNECT_FAILED"
        if isinstance(e, McpError):
            if "timed out" in str(e).lower():
                return ToolStatus.TIMEOUT, "MCP_TIMEOUT"
            return ToolStatus.UNAVAILABLE, "MCP_PROTOCOL_ERROR"
        if isinstance(e, RuntimeError) and "structured content" in str(e).lower():
            return ToolStatus.INVALID_RESPONSE, "INVALID_STRUCTURED_CONTENT"
    return ToolStatus.UNAVAILABLE, "MCP_CONNECT_FAILED"


_ERROR_CODE = re.compile(r"\[([A-Z][A-Z0-9_]+)\]")


# ── Session ──────────────────────────────────────────────────────────────────

@dataclass
class ToolSession:
    gateway: "MCPToolGateway"
    agent: str
    settings: InventoryMCPSettings
    client: Optional[ClientSession] = None
    tools: Dict[str, ToolKind] = field(default_factory=dict)  # exposed tool → effective kind
    trap: Optional[_Trap] = None
    failure: Optional[Tuple[ToolStatus, str]] = None
    deadline: Optional[float] = None  # time.monotonic() budget for the whole request

    @property
    def available(self) -> FrozenSet[str]:
        return frozenset(self.tools)

    @property
    def transport(self) -> str:
        return self.settings.transport

    async def call(self, tool: str, arguments: Optional[Dict[str, Any]] = None,
                   *, timeout_s: Optional[float] = None) -> ToolResult:
        server = self.gateway.server_name
        start = time.perf_counter()
        with span("mcp.tool", server=server, tool=tool, agent=self.agent, transport=self.transport) as sp:
            result = await self._call(tool, arguments or {}, timeout_s or self.settings.timeout_s)
            result.duration_ms = round((time.perf_counter() - start) * 1000, 2)
            sp.set(status="error" if result.failed else "ok", outcome=result.status.value,
                   attempts=result.attempts, error_code=result.error_code)
        kind = self.tools.get(tool) or kind_of(tool)
        MCP_TOOL_CALLS.inc(server=server, tool=tool, outcome=result.status.value, transport=self.transport)
        MCP_TOOL_DURATION.observe(result.duration_ms / 1000, server=server, tool=tool, transport=self.transport)
        logger.log_event("MCP_TOOL_CALL", {
            "server": server, "agent": self.agent, "tool": tool, "kind": kind.value if kind else None,
            "status": result.status.value, "attempts": result.attempts, "duration_ms": result.duration_ms,
            "error_code": result.error_code, "arguments": arguments,
        }, level="WARNING" if result.failed else "INFO")
        return result

    async def _call(self, tool: str, arguments: Dict[str, Any], timeout_s: float) -> ToolResult:
        # 1. Allowlist (enforced here, whatever the agent's prompt or code asked for)
        if not is_allowed(self.agent, tool):
            reason = "unknown_tool" if tool not in TOOL_REGISTRY else "not_allowlisted"
            MCP_TOOL_REJECTIONS.inc(agent=self.agent, reason=reason)
            logger.log_event("MCP_TOOL_CALL_REJECTED", {"agent": self.agent, "tool": tool, "reason": reason},
                             level="WARNING")
            return ToolResult(tool, ToolStatus.UNAUTHORIZED, error_code="TOOL_NOT_ALLOWED")
        # 2. Session problems (bad config, server unreachable)
        if self.failure is not None:
            return ToolResult(tool, self.failure[0], error_code=self.failure[1])
        # 3. Discovered on the server and exposed to this agent?
        if tool not in self.tools:
            return ToolResult(tool, ToolStatus.UNAVAILABLE, error_code="TOOL_NOT_DISCOVERED")
        # 4. Arguments must match the tool contract
        try:
            args = ARG_MODELS[tool].model_validate(arguments).model_dump(exclude_none=True)
        except ValidationError:
            return ToolResult(tool, ToolStatus.INVALID_ARGUMENTS, error_code="INVALID_ARGUMENTS")

        retries = self.settings.max_retries if self.tools[tool] is ToolKind.READ else 0
        attempt = 0
        while True:
            attempt += 1
            result = await self._attempt(tool, args, timeout_s)
            result.attempts = attempt
            if result.status not in RETRYABLE or attempt > retries:
                return result
            backoff = self.settings.backoff_s * (2 ** (attempt - 1)) + random.uniform(0, self.settings.backoff_s / 2)
            if self.deadline is not None and time.monotonic() + backoff + timeout_s > self.deadline:
                return result  # no time left for another attempt inside the request budget
            MCP_TOOL_RETRIES.inc(server=self.gateway.server_name, tool=tool)
            logger.log_event("MCP_TOOL_RETRY", {"tool": tool, "attempt": attempt, "status": result.status.value,
                                                "backoff_s": round(backoff, 3)}, level="WARNING")
            await anyio.sleep(backoff)

    async def _attempt(self, tool: str, args: Dict[str, Any], timeout_s: float) -> ToolResult:
        try:
            raw = await self.trap.run(lambda: self.client.call_tool(tool, args), timeout_s)
        except TimeoutError:
            MCP_TOOL_TIMEOUTS.inc(server=self.gateway.server_name, tool=tool)
            return ToolResult(tool, ToolStatus.TIMEOUT, error_code="MCP_TIMEOUT")
        except Exception as exc:
            status, code = classify_exception(exc)
            MCP_ERRORS.inc(server=self.gateway.server_name, kind=code)
            return ToolResult(tool, status, error_code=code)

        text = next((c.text for c in raw.content or [] if getattr(c, "type", "") == "text"), "")
        if raw.isError:
            m = _ERROR_CODE.search(text)
            code = m.group(1) if m else ("INVALID_ARGUMENTS" if "validation error" in text.lower() else "TOOL_ERROR")
            status = ToolStatus.INVALID_ARGUMENTS if code == "INVALID_ARGUMENTS" else ToolStatus.TOOL_ERROR
            return ToolResult(tool, status, error_code=code)

        payload = raw.structuredContent
        if payload is None:
            try:
                payload = json.loads(text)
            except (TypeError, ValueError):
                return ToolResult(tool, ToolStatus.INVALID_RESPONSE, error_code="NON_JSON_RESULT")
        try:
            data = RESULT_MODELS[tool].model_validate(payload)
        except ValidationError:
            return ToolResult(tool, ToolStatus.INVALID_RESPONSE, error_code="RESULT_SCHEMA_MISMATCH")
        try:
            status = ToolStatus(getattr(data, "status", "ok"))
        except ValueError:
            return ToolResult(tool, ToolStatus.INVALID_RESPONSE, error_code="UNKNOWN_RESULT_STATUS")
        return ToolResult(tool, status, data=data)


# ── Gateway ──────────────────────────────────────────────────────────────────

class MCPToolGateway:
    def __init__(self, server_name: str, server_factory: Callable[[], Any],
                 settings_factory: Callable[[], InventoryMCPSettings] = InventoryMCPSettings.from_env):
        self.server_name = server_name
        self.server_factory = server_factory
        self.settings_factory = settings_factory

    def describe(self) -> Dict[str, Any]:
        return self.settings_factory().describe()

    @asynccontextmanager
    async def session(self, agent: str, *, budget_s: Optional[float] = None) -> AsyncIterator[ToolSession]:
        settings = self.settings_factory()
        deadline = time.monotonic() + budget_s if budget_s else None
        problems = settings.problems()
        if problems:
            MCP_ERRORS.inc(server=self.server_name, kind="config")
            for p in problems:
                logger.log_event("MCP_CONFIG_PROBLEM", {"server": self.server_name, "problem": p}, level="ERROR")
            yield ToolSession(self, agent, settings, failure=(ToolStatus.CONFIG_ERROR, "MCP_CONFIG_INVALID"),
                              deadline=deadline)
            return

        trap = _Trap()
        stack = AsyncExitStack()
        sp = span("mcp.session", server=self.server_name, transport=settings.transport, agent=agent)
        sp.__enter__()
        try:
            try:
                client = await stack.enter_async_context(self._connect(settings, trap))
                listed = await self._list_tools(client, trap, settings.timeout_s)
            except Exception as exc:
                status, code = classify_exception(exc)
                MCP_ERRORS.inc(server=self.server_name, kind=code)
                logger.log_event("MCP_CONNECT_FAILED", {"server": self.server_name, "transport": settings.transport,
                                                        "status": status.value, "error_code": code,
                                                        "error_type": type(exc).__name__}, level="ERROR")
                await _safe_close(stack, self.server_name)
                sp.set(status="error", error_code=code)
                yield ToolSession(self, agent, settings, failure=(status, code), deadline=deadline)
                return

            tools = self._expose(agent, listed)
            sp.set(exposed=len(tools))
            try:
                yield ToolSession(self, agent, settings, client=client, tools=tools, trap=trap, deadline=deadline)
            finally:
                await _safe_close(stack, self.server_name)
        finally:
            sp.__exit__(None, None, None)

    @asynccontextmanager
    async def _connect(self, settings: InventoryMCPSettings, trap: _Trap) -> AsyncIterator[ClientSession]:
        read_timeout = timedelta(seconds=settings.timeout_s)
        if settings.transport == "memory":
            from mcp.shared.memory import create_connected_server_and_client_session
            server = self.server_factory()
            lowlevel = getattr(server, "_mcp_server", server)
            async with create_connected_server_and_client_session(
                    lowlevel, read_timeout_seconds=read_timeout, message_handler=trap.handler) as client:
                yield client
            return

        from mcp.client.streamable_http import streamable_http_client
        from mcp.shared._httpx_utils import create_mcp_http_client
        headers = {"Authorization": f"Bearer {settings.token}"}
        traceparent = format_traceparent()
        if traceparent:
            headers["traceparent"] = traceparent
        timeout = httpx.Timeout(settings.timeout_s, read=max(settings.timeout_s, 30.0))
        async with create_mcp_http_client(headers=headers, timeout=timeout) as http:
            async with streamable_http_client(settings.url, http_client=http) as (read, write, _):
                async with ClientSession(read, write, read_timeout_seconds=read_timeout,
                                         message_handler=trap.handler) as client:
                    await trap.run(client.initialize, settings.timeout_s)
                    yield client

    async def _list_tools(self, client: ClientSession, trap: _Trap, timeout_s: float) -> List[Any]:
        tools: List[Any] = []
        cursor = None
        for _ in range(10):  # bounded pagination
            page = await trap.run(lambda: client.list_tools(cursor), timeout_s)
            tools.extend(page.tools)
            cursor = page.nextCursor
            if not cursor:
                break
        return tools

    def _expose(self, agent: str, listed: List[Any]) -> Dict[str, ToolKind]:
        """Discovered ∩ registered ∩ allowlisted; read tools must be declared read-only by the server."""
        discovered = {t.name: t for t in listed}
        allow = allowed_tools(agent)
        for name in sorted(set(discovered) - set(TOOL_REGISTRY)):
            MCP_ERRORS.inc(server=self.server_name, kind="unregistered_tool")
            logger.log_event("MCP_TOOL_UNREGISTERED", {"server": self.server_name, "tool": name}, level="WARNING")
        for name in sorted(allow - set(discovered)):
            MCP_ERRORS.inc(server=self.server_name, kind="missing_tool")
            logger.log_event("MCP_TOOL_MISSING", {"server": self.server_name, "agent": agent, "tool": name},
                             level="WARNING")
        exposed: Dict[str, ToolKind] = {}
        for name, tool in discovered.items():
            if name not in allow or name not in TOOL_REGISTRY:
                continue
            kind = TOOL_REGISTRY[name]
            read_only = bool(getattr(tool.annotations, "readOnlyHint", False)) if tool.annotations else False
            if kind is ToolKind.READ and not read_only:
                logger.log_event("MCP_TOOL_KIND_MISMATCH", {"server": self.server_name, "tool": name},
                                 level="WARNING")
                kind = ToolKind.MUTATION  # treat as a write: never retried
            exposed[name] = kind
        logger.log_event("MCP_TOOLS_DISCOVERED", {"server": self.server_name, "agent": agent,
                                                  "discovered": len(discovered), "exposed": sorted(exposed)})
        return exposed


async def _safe_close(stack: AsyncExitStack, server: str) -> None:
    try:
        await stack.aclose()
    except Exception as exc:  # closing a broken transport must not hide the real outcome
        logger.log_event("MCP_SESSION_CLOSE_ERROR", {"server": server, "error_type": type(exc).__name__},
                         level="WARNING")


def _inventory_server():
    from mcp_servers.inventory_mcp_server import server
    return server


inventory_tool_gateway = MCPToolGateway("inventory", server_factory=_inventory_server)
