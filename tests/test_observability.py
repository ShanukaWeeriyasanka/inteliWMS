"""
Logging, tracing and metrics (unit tests + one in-memory MCP request).
"""
import json
import logging

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.threads.store import ThreadStore
from config.settings import settings
from database.models import ChatThread
from inventory_testkit import auth
from utils.logger import StructuredLogger, redact
from utils.metrics import Counter, REGISTRY

client = TestClient(app)


def test_request_id_is_honoured_or_replaced_and_trace_is_continued():
    res = client.get("/health", headers={"X-Request-ID": "req-12345678"})
    assert res.headers["x-request-id"] == "req-12345678"
    res = client.get("/health", headers={"X-Request-ID": "bad id!"})
    assert res.headers["x-request-id"] != "bad id!" and len(res.headers["x-request-id"]) == 32
    trace = "4bf92f3577b34da6a3ce929d0e0e4736"
    res = client.get("/health", headers={"traceparent": f"00-{trace}-00f067aa0ba902b7-01"})
    assert res.headers["x-trace-id"] == trace


def test_error_responses_carry_correlation_ids():
    res = client.post("/query", json={"message": "x", "thread_id": "nope"}, headers=auth("zoe"))
    body = res.json()
    assert res.status_code == 400 and body["audit"]["request_id"] == res.headers["x-request-id"]


def test_secrets_are_redacted_and_content_omitted_by_default():
    jwt_like = "eyJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiYSJ9.c2lnbmF0dXJl"
    out = redact({
        "token": "abc", "password": "pw", "authorization": "Bearer xyz", "nested": {"api_key": "k1"},
        "error": f"connect postgresql://admin:supersecret@db/wms failed; header Bearer {jwt_like}",
        "query": "where is SKU-1001?", "status": "ok",
    })
    text = json.dumps(out)
    for secret in ("abc", "\"pw\"", "xyz", "k1", "supersecret", jwt_like, "where is SKU-1001?"):
        assert secret not in text, secret
    assert out["query"] == {"omitted": True, "len": 18} and out["status"] == "ok"


def test_content_logging_can_be_switched_on(monkeypatch):
    monkeypatch.setattr(settings, "LOG_INCLUDE_CONTENT", True)
    assert redact({"query": "where is SKU-1001?"})["query"] == "where is SKU-1001?"


def test_log_lines_carry_correlation_ids_and_levels(caplog):
    from utils import request_context
    tokens = request_context.bind(request_id="r1", trace_id="t1", thread_id="th1")
    try:
        with caplog.at_level(logging.DEBUG, logger="obs-test"):
            StructuredLogger("obs-test").log_event("SAMPLE", {"tool": "x"}, level="WARNING")
    finally:
        request_context.reset(tokens)
    record = caplog.records[-1]
    entry = json.loads(record.getMessage())
    assert record.levelname == "WARNING"
    assert (entry["request_id"], entry["trace_id"], entry["thread_id"]) == ("r1", "t1", "th1")


def test_high_cardinality_metric_labels_are_refused():
    for label in ("thread_id", "user_id", "request_id", "sku"):
        with pytest.raises(ValueError):
            Counter("bad_metric_total", "x", [label])


@pytest.mark.mcp_inmemory
def test_metrics_endpoint_has_inventory_series_but_no_ids(inventory_server, monkeypatch):
    data = client.post("/query", json={"message": "how many SKU-1001 are on hand?"}, headers=auth("mia")).json()
    text = client.get("/metrics").text
    for series in ("inventory_requests_total", "mcp_tool_calls_total", "routing_decisions_total",
                   "agent_requests_total", "thread_operations_total", "http_request_duration_seconds"):
        assert series in text, series
    assert data["thread_id"] not in text and data["request_id"] not in text and "mia" not in text
    monkeypatch.setattr(settings, "METRICS_TOKEN", "metrics-secret")
    assert client.get("/metrics").status_code == 401
    assert client.get("/metrics", headers={"Authorization": "Bearer metrics-secret"}).status_code == 200


@pytest.mark.mcp_inmemory
def test_one_trace_spans_the_request_routing_and_mcp_tools(inventory_server, caplog):
    with caplog.at_level(logging.INFO):
        res = client.post("/query", json={"message": "where is SKU-1004?"}, headers=auth("tracy"))
    trace_id = res.headers["x-trace-id"]
    events = [json.loads(r.getMessage()) for r in caplog.records if r.getMessage().startswith("{")]
    spans = {e["span"] for e in events if e.get("event_type") == "SPAN_END" and e.get("trace_id") == trace_id}
    assert {"query.handle", "routing.decide", "agent.dispatch", "inventory.handle", "mcp.session",
            "mcp.tool"} <= spans
    tool_calls = [e for e in events if e.get("event_type") == "MCP_TOOL_CALL"]
    assert tool_calls and all(e["trace_id"] == trace_id and e["agent"] == "inventory_agent" for e in tool_calls)
    assert all(e["arguments"] == {"omitted": True, "len": 1} for e in tool_calls)  # payloads not logged


def test_health_reports_mcp_configuration_without_secrets(monkeypatch):
    monkeypatch.setenv("INVENTORY_MCP_TRANSPORT", "streamable_http")
    monkeypatch.setenv("INVENTORY_MCP_URL", "http://inventory-mcp:8003/mcp")
    monkeypatch.setenv("INVENTORY_MCP_TOKEN", "very-secret-token")
    body = client.get("/health").json()
    assert body["inventory_mcp"]["configured"] is True and body["inventory_mcp"]["token_set"] is True
    assert "very-secret-token" not in json.dumps(body)


def test_corrupt_thread_context_is_reset_not_fatal(thread_db):
    with thread_db() as s:
        store = ThreadStore(s)
        t = store.create("u1", "x")
        t.context_json = {"inventory": {"skus": "not-a-list"}, "turn_count": "many"}
        s.commit()
        assert store.context(t).turn_count == 0
