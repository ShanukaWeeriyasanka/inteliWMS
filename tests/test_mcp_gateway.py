"""
MCP tool gateway: allowlists, discovery filtering, argument / response validation,
timeouts, bounded retries and configuration errors.

Test types (see HOW_TO_RUN.md):
  * unit            — policy and configuration checks, no MCP session
  * mcp_inmemory    — real MCP protocol (FastMCP server + ClientSession) over the in-memory
                      transport, against purpose-built test servers; no network, no live server
Live-server checks are in tests/test_inventory_mcp_live.py.
"""
import json

import anyio
import pytest
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations

from agents.inventory_agent import tool_contracts as C
from mcp_servers import tool_policy
from mcp_servers.mcp_tool_client import InventoryMCPSettings, MCPToolGateway, ToolStatus
from utils.metrics import MCP_TOOL_REJECTIONS, MCP_TOOL_RETRIES

READ = ToolAnnotations(readOnlyHint=True)


def _settings(**kw):
    base = dict(transport="memory", timeout_s=0.3, max_retries=2, backoff_s=0.01)
    base.update(kw)
    return InventoryMCPSettings(**base)


def _gateway(server, **settings_kw):
    return MCPToolGateway("test", server_factory=lambda: server, settings_factory=lambda: _settings(**settings_kw))


def _stock_payload(status="ok"):
    return {"status": status, "sku": "SKU-1001"}


def run(coro_fn):
    return anyio.run(coro_fn)


# ── Policy (unit) ────────────────────────────────────────────────────────────

def test_every_agent_has_an_explicit_allowlist():
    assert tool_policy.allowed_tools("coordinator") == frozenset()
    assert tool_policy.allowed_tools("fulfillment_agent") == frozenset()
    inv = tool_policy.allowed_tools("inventory_agent")
    assert C.GET_PRODUCT_STOCK in inv and C.PUBLISH_MAP_COMMAND in inv
    assert inv <= set(tool_policy.TOOL_REGISTRY)


def test_unknown_agent_and_unknown_tool_are_denied():
    assert not tool_policy.is_allowed("some_new_agent", C.GET_PRODUCT_STOCK)
    assert not tool_policy.is_allowed("inventory_agent", "drop_all_stock")


def test_mutation_tools_are_marked():
    assert tool_policy.kind_of(C.PUBLISH_MAP_COMMAND) is tool_policy.ToolKind.MUTATION
    assert all(tool_policy.kind_of(t) is tool_policy.ToolKind.READ for t in tool_policy.INVENTORY_READ_TOOLS)


def test_registry_and_contracts_agree():
    assert set(tool_policy.TOOL_REGISTRY) == set(C.ARG_MODELS) == set(C.RESULT_MODELS)


# ── Configuration (unit) ─────────────────────────────────────────────────────

def test_config_problems_are_precise(monkeypatch):
    monkeypatch.setenv("INVENTORY_MCP_TRANSPORT", "streamable_http")
    monkeypatch.delenv("INVENTORY_MCP_URL", raising=False)
    monkeypatch.delenv("INVENTORY_MCP_TOKEN", raising=False)
    problems = InventoryMCPSettings.from_env().problems()
    assert "INVENTORY_MCP_URL is required when INVENTORY_MCP_TRANSPORT=streamable_http" in problems
    assert "INVENTORY_MCP_TOKEN is required when INVENTORY_MCP_TRANSPORT=streamable_http" in problems

    monkeypatch.setenv("INVENTORY_MCP_URL", "ftp://host/mcp")
    monkeypatch.setenv("INVENTORY_MCP_TOKEN", "secret-token-value")
    s = InventoryMCPSettings.from_env()
    assert s.problems() == ["INVENTORY_MCP_URL must start with http:// or https://"]
    assert "secret-token-value" not in json.dumps(s.describe())

    monkeypatch.setenv("INVENTORY_MCP_TRANSPORT", "carrier-pigeon")
    monkeypatch.setenv("INVENTORY_MCP_TIMEOUT_S", "soon")
    problems = InventoryMCPSettings.from_env().problems()
    assert any("INVENTORY_MCP_TRANSPORT must be 'memory' or 'streamable_http'" in p for p in problems)
    assert any(p.startswith("INVENTORY_MCP_TIMEOUT_S must be a number") for p in problems)


def test_config_error_turns_every_call_into_config_error():
    gw = _gateway(FastMCP("unused"), transport="streamable_http", url="", token="")

    async def go():
        async with gw.session("inventory_agent") as tools:
            return await tools.call(C.GET_PRODUCT_STOCK, {"sku": "SKU-1001"})
    r = run(go)
    assert r.status is ToolStatus.CONFIG_ERROR and r.error_code == "MCP_CONFIG_INVALID"


# ── In-memory MCP against test servers ───────────────────────────────────────

@pytest.mark.mcp_inmemory
def test_unauthorized_agent_call_is_rejected_before_the_server_is_called():
    calls = []
    server = FastMCP("t")

    @server.tool(name=C.GET_PRODUCT_STOCK, annotations=READ)
    async def get_product_stock(sku: str) -> dict:
        calls.append(sku)
        return _stock_payload()

    before = MCP_TOOL_REJECTIONS.value(agent="fulfillment_agent", reason="not_allowlisted")

    async def go():
        async with _gateway(server).session("fulfillment_agent") as tools:
            assert tools.available == frozenset()
            return await tools.call(C.GET_PRODUCT_STOCK, {"sku": "SKU-1001"})
    r = run(go)
    assert r.status is ToolStatus.UNAUTHORIZED and r.error_code == "TOOL_NOT_ALLOWED"
    assert calls == []
    assert MCP_TOOL_REJECTIONS.value(agent="fulfillment_agent", reason="not_allowlisted") == before + 1


@pytest.mark.mcp_inmemory
def test_unregistered_discovered_tool_is_never_exposed_or_called():
    calls = []
    server = FastMCP("t")

    @server.tool(name="drop_all_stock")
    async def drop_all_stock() -> str:
        calls.append(1)
        return "dropped"

    @server.tool(name=C.GET_PRODUCT_STOCK, annotations=READ)
    async def get_product_stock(sku: str) -> dict:
        return _stock_payload()

    async def go():
        async with _gateway(server).session("inventory_agent") as tools:
            assert "drop_all_stock" not in tools.available
            assert C.GET_PRODUCT_STOCK in tools.available
            return await tools.call("drop_all_stock", {})
    r = run(go)
    assert r.status is ToolStatus.UNAUTHORIZED and calls == []


@pytest.mark.mcp_inmemory
def test_allowlisted_tool_missing_on_server_is_unavailable():
    async def go():
        async with _gateway(FastMCP("empty")).session("inventory_agent") as tools:
            return await tools.call(C.GET_PRODUCT_STOCK, {"sku": "SKU-1001"})
    r = run(go)
    assert r.status is ToolStatus.UNAVAILABLE and r.error_code == "TOOL_NOT_DISCOVERED"


@pytest.mark.mcp_inmemory
def test_arguments_are_validated_against_the_contract_before_sending():
    calls = []
    server = FastMCP("t")

    @server.tool(name=C.GET_PRODUCT_STOCK, annotations=READ)
    async def get_product_stock(sku: str) -> dict:
        calls.append(sku)
        return _stock_payload()

    async def go():
        async with _gateway(server).session("inventory_agent") as tools:
            return [await tools.call(C.GET_PRODUCT_STOCK, {"sku": "DROP TABLE"}),
                    await tools.call(C.GET_PRODUCT_STOCK, {"sku": "SKU-1001", "extra": 1})]
    results = run(go)
    assert all(r.status is ToolStatus.INVALID_ARGUMENTS for r in results) and calls == []


@pytest.mark.mcp_inmemory
def test_slow_read_tool_times_out_and_is_retried_a_bounded_number_of_times():
    calls = []
    server = FastMCP("t")

    @server.tool(name=C.GET_PRODUCT_STOCK, annotations=READ)
    async def get_product_stock(sku: str) -> dict:
        calls.append(sku)
        await anyio.sleep(5)
        return _stock_payload()

    before = MCP_TOOL_RETRIES.value(server="test", tool=C.GET_PRODUCT_STOCK)

    async def go():
        async with _gateway(server, max_retries=2).session("inventory_agent") as tools:
            return await tools.call(C.GET_PRODUCT_STOCK, {"sku": "SKU-1001"})
    r = run(go)
    assert r.status is ToolStatus.TIMEOUT and r.attempts == 3 and len(calls) == 3
    assert MCP_TOOL_RETRIES.value(server="test", tool=C.GET_PRODUCT_STOCK) == before + 2


@pytest.mark.mcp_inmemory
def test_mutation_tool_is_never_retried():
    calls = []
    server = FastMCP("t")

    @server.tool(name=C.PUBLISH_MAP_COMMAND, annotations=ToolAnnotations(readOnlyHint=False))
    async def publish_map_command(session_id: str, query_text: str, command: dict) -> dict:
        calls.append(1)
        await anyio.sleep(5)
        return {"status": "ok", "command_id": "x"}

    async def go():
        async with _gateway(server, max_retries=3).session("inventory_agent") as tools:
            return await tools.call(C.PUBLISH_MAP_COMMAND,
                                    {"session_id": "s1", "query_text": "q", "command": {"action": "clear"}})
    r = run(go)
    assert r.status is ToolStatus.TIMEOUT and r.attempts == 1 and calls == [1]


@pytest.mark.mcp_inmemory
def test_read_tool_not_declared_read_only_is_treated_as_mutation():
    calls = []
    server = FastMCP("t")

    @server.tool(name=C.GET_PRODUCT_STOCK)  # no readOnlyHint
    async def get_product_stock(sku: str) -> dict:
        calls.append(1)
        await anyio.sleep(5)
        return _stock_payload()

    async def go():
        async with _gateway(server, max_retries=3).session("inventory_agent") as tools:
            return await tools.call(C.GET_PRODUCT_STOCK, {"sku": "SKU-1001"})
    r = run(go)
    assert r.status is ToolStatus.TIMEOUT and r.attempts == 1


@pytest.mark.mcp_inmemory
def test_retry_never_exceeds_the_request_budget():
    server = FastMCP("t")

    @server.tool(name=C.GET_PRODUCT_STOCK, annotations=READ)
    async def get_product_stock(sku: str) -> dict:
        await anyio.sleep(5)
        return _stock_payload()

    async def go():
        async with _gateway(server, max_retries=5).session("inventory_agent", budget_s=0.5) as tools:
            return await tools.call(C.GET_PRODUCT_STOCK, {"sku": "SKU-1001"})
    r = run(go)
    assert r.status is ToolStatus.TIMEOUT and r.attempts <= 2


@pytest.mark.mcp_inmemory
@pytest.mark.parametrize("raise_exc, expected_status, expected_code", [
    (ToolError("[DB_UNAVAILABLE] inventory database query failed"), ToolStatus.TOOL_ERROR, "DB_UNAVAILABLE"),
    (RuntimeError("password=hunter2 internal details"), ToolStatus.TOOL_ERROR, "TOOL_ERROR"),
])
def test_tool_errors_are_reported_not_hidden(raise_exc, expected_status, expected_code):
    server = FastMCP("t")

    @server.tool(name=C.GET_PRODUCT_STOCK, annotations=READ)
    async def get_product_stock(sku: str) -> dict:
        raise raise_exc

    async def go():
        async with _gateway(server).session("inventory_agent") as tools:
            return await tools.call(C.GET_PRODUCT_STOCK, {"sku": "SKU-1001"})
    r = run(go)
    assert (r.status, r.error_code, r.attempts) == (expected_status, expected_code, 1)


@pytest.mark.mcp_inmemory
@pytest.mark.parametrize("text, code", [
    ('{"status": "maybe", "sku": "SKU-1001"}', "RESULT_SCHEMA_MISMATCH"),
    ('{"sku": "SKU-1001"}', "RESULT_SCHEMA_MISMATCH"),
    ("not json at all", "NON_JSON_RESULT"),
])
def test_malformed_responses_are_rejected(text, code):
    server = FastMCP("t")

    @server.tool(name=C.GET_PRODUCT_STOCK, annotations=READ, structured_output=False)
    async def get_product_stock(sku: str) -> str:
        return text

    async def go():
        async with _gateway(server).session("inventory_agent") as tools:
            return await tools.call(C.GET_PRODUCT_STOCK, {"sku": "SKU-1001"})
    r = run(go)
    assert r.status is ToolStatus.INVALID_RESPONSE and r.error_code == code and r.data is None


@pytest.mark.mcp_inmemory
def test_server_that_cannot_start_is_unavailable_not_an_exception():
    def broken_factory():
        raise RuntimeError("cannot build server")
    gw = MCPToolGateway("test", server_factory=broken_factory, settings_factory=lambda: _settings())

    async def go():
        async with gw.session("inventory_agent") as tools:
            return await tools.call(C.GET_PRODUCT_STOCK, {"sku": "SKU-1001"})
    r = run(go)
    assert r.status is ToolStatus.UNAVAILABLE and r.error_code == "MCP_CONNECT_FAILED"


def test_http_connection_refused_is_reported_as_unavailable():
    """Unit check of the HTTP transport's failure path (nothing listens on the port; not a live test)."""
    gw = MCPToolGateway("test", server_factory=lambda: None, settings_factory=lambda: _settings(
        transport="streamable_http", url="http://127.0.0.1:9/mcp", token="t", timeout_s=2, max_retries=0))

    async def go():
        async with gw.session("inventory_agent") as tools:
            return await tools.call(C.GET_PRODUCT_STOCK, {"sku": "SKU-1001"})
    r = run(go)
    assert r.status in (ToolStatus.UNAVAILABLE, ToolStatus.TIMEOUT)
    assert r.error_code in ("MCP_CONNECT_FAILED", "MCP_TIMEOUT")
