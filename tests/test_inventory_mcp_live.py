"""
LIVE MCP checks: the inventory MCP server runs as a separate process over streamable
HTTP with bearer-token auth, and the gateway connects to it over the network.

Skipped unless RUN_LIVE_MCP=1. By default the test starts the server itself:

    $env:RUN_LIVE_MCP = "1"; .\\venv\\Scripts\\python.exe -m pytest tests/test_inventory_mcp_live.py

To test an already running server instead, also set INVENTORY_MCP_LIVE_URL and
INVENTORY_MCP_LIVE_TOKEN. Reads only (no map commands are published); it queries the
database configured for that server (DATABASE_URL).
"""
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import anyio
import pytest

from agents.inventory_agent import tool_contracts as C
from mcp_servers.mcp_tool_client import InventoryMCPSettings, MCPToolGateway, ToolStatus

pytestmark = [
    pytest.mark.mcp_live,
    pytest.mark.skipif(os.getenv("RUN_LIVE_MCP") != "1", reason="live MCP test: set RUN_LIVE_MCP=1"),
]

ROOT = Path(__file__).resolve().parent.parent


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def live_server():
    url, token = os.getenv("INVENTORY_MCP_LIVE_URL"), os.getenv("INVENTORY_MCP_LIVE_TOKEN")
    if url and token:
        yield url, token
        return
    port, token = _free_port(), "live-test-token-123"
    env = {**os.environ, "INVENTORY_MCP_TOKEN": token, "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.Popen([sys.executable, "-m", "mcp_servers.inventory_mcp_server",
                             "--transport", "streamable-http", "--port", str(port)],
                            cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    deadline = time.time() + 30
    while time.time() < deadline:
        if proc.poll() is not None:
            pytest.fail(f"MCP server exited: {proc.stdout.read().decode(errors='replace')[-2000:]}")
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.5).close()
            break
        except OSError:
            time.sleep(0.3)
    else:
        proc.kill()
        pytest.fail("MCP server did not start listening within 30 s")
    yield f"http://127.0.0.1:{port}/mcp", token
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def _gateway(url, token):
    settings = InventoryMCPSettings(transport="streamable_http", url=url, token=token, timeout_s=10,
                                    max_retries=1, backoff_s=0.1)
    return MCPToolGateway("inventory-live", server_factory=lambda: None, settings_factory=lambda: settings)


def test_discovery_and_read_calls_over_http(live_server):
    url, token = live_server

    async def go():
        async with _gateway(url, token).session("inventory_agent") as tools:
            assert C.GET_PRODUCT_STOCK in tools.available and C.PUBLISH_MAP_COMMAND in tools.available
            low = await tools.call(C.LIST_LOW_STOCK, {"limit": 5})
            missing = await tools.call(C.GET_PRODUCT_STOCK, {"sku": "SKU-000001"})
            bad = await tools.call(C.GET_PRODUCT_STOCK, {"sku": "not a sku"})
            return low, missing, bad
    low, missing, bad = anyio.run(go)
    assert low.status in (ToolStatus.OK, ToolStatus.EMPTY) and low.data.total_checked >= 0
    assert missing.status is ToolStatus.NOT_FOUND
    assert bad.status is ToolStatus.INVALID_ARGUMENTS


def test_allowlist_is_enforced_over_http_too(live_server):
    url, token = live_server

    async def go():
        async with _gateway(url, token).session("fulfillment_agent") as tools:
            return tools.available, await tools.call(C.GET_PRODUCT_STOCK, {"sku": "SKU-4521"})
    available, r = anyio.run(go)
    assert available == frozenset() and r.status is ToolStatus.UNAUTHORIZED


def test_wrong_token_is_rejected(live_server):
    url, _ = live_server

    async def go():
        async with _gateway(url, "wrong-token").session("inventory_agent") as tools:
            return await tools.call(C.GET_PRODUCT_STOCK, {"sku": "SKU-4521"})
    r = anyio.run(go)
    assert r.status is ToolStatus.UNAUTHORIZED and r.error_code == "MCP_AUTH_FAILED"
