"""
Inventory agent over the real inventory MCP server (in-memory transport) and a seeded
throwaway database (tests/inventory_testkit.py). No network, no live server.

Every quantity asserted here is checked against the seeded row, so answers must match
the tool results exactly — zero stock, unknown products, empty results and ambiguous
names are all distinguished, and nothing is invented.
"""
import asyncio
import re
from unittest.mock import MagicMock, patch

import anyio
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from agents.inventory_agent import responder
from agents.inventory_agent import tool_contracts as C
from agents.inventory_agent.agent import handle_inventory_query, handle_inventory_query_async
from inventory_testkit import PRODUCTS

pytestmark = pytest.mark.mcp_inmemory


def ask(query, **kw):
    return anyio.run(lambda: handle_inventory_query_async(query, **kw))


def numbers(text):
    return {int(n) for n in re.findall(r"\b\d+\b", text)}


# ── Grounded answers ─────────────────────────────────────────────────────────

def test_stock_answer_matches_the_database_row(inventory_server):
    r = ask("how many SKU-1001 do we have on hand?")
    row = PRODUCTS["SKU-1001"]
    assert r["outcome"] == "answered" and r["source"] == "database"
    item = r["items"][0]
    assert item["quantity_on_hand"] == row["quantity"] == 15
    assert item["available_quantity"] == row["quantity"] - row["reserved_quantity"] == 13
    assert item["status"] == "LOW_STOCK"  # 15 <= reorder point 20
    assert "**15** units on hand" in r["response"] and "13 available" in r["response"]
    # No number in the answer that isn't from the row (quantities, thresholds, reorder batch, location digits,
    # and the record's own last-updated time)
    allowed = ({15, 13, 2, 20, 10, 5, 1, 2, 45, 21, 0, row["reorder_quantity"]} | numbers(row["location"])
               | numbers("SKU-1001") | numbers(responder._stamp(item["updated_at"]) or ""))
    assert numbers(r["response"]) <= allowed


def test_zero_stock_is_a_real_zero_not_unknown(inventory_server):
    r = ask("is SKU-1003 in stock?")
    assert r["outcome"] == "answered"
    assert r["items"][0]["quantity_on_hand"] == 0 and r["items"][0]["status"] == "OUT_OF_STOCK"
    assert "OUT OF STOCK" in r["response"] and "No —" in r["response"]


def test_unknown_sku_is_not_found_with_no_numbers(inventory_server):
    r = ask("where is SKU-9999?")
    assert r["outcome"] == "not_found" and r["items"] == []
    assert "couldn't find **SKU-9999**" in r["response"]
    assert numbers(r["response"]) <= {9999, 4521}  # only the SKU itself and the example format


def test_availability_by_product_name(inventory_server):
    r = ask("do we have any wireless barcode scanners available?")
    assert r["items"][0]["sku"] == "SKU-1004"
    assert "**330** units of **Wireless Barcode Scanner**" in r["response"]


def test_missing_thresholds_are_flagged_as_defaults(inventory_server):
    r = ask("stock level for SKU-1005")
    assert "aren't set in the database" in r["response"]


def test_low_stock_list_uses_reorder_points(inventory_server):
    r = ask("what's running low?")
    skus = [i["sku"] for i in r["items"]]
    assert skus[0] == "SKU-1003"                  # out of stock first
    assert set(skus) == {"SKU-1003", "SKU-1001", "SKU-1005"}  # 8 <= default reorder point 30
    assert "SKU-1004" not in skus and "SKU-1002" not in skus


def test_stock_movements_and_empty_movements(inventory_server):
    r = ask("show stock movements for SKU-1004")
    assert r["outcome"] == "answered" and "-10 (350 → 340)" in r["response"] and "ORD-1001" in r["response"]
    r = ask("stock movements for SKU-1001")
    assert r["outcome"] == "empty" and "No stock movements are recorded" in r["response"]


def test_forecast_and_transfer_need_a_real_product(inventory_server):
    r = ask("what is the burn rate and depletion forecast?")
    assert r["outcome"] == "needs_product" and r["prediction_result"] is None
    r = ask("depletion forecast for SKU-1001")
    assert r["prediction_result"]["current_stock"] == 15 and r["prediction_result"]["daily_burn_rate"] == 6.2
    r = ask("can we transfer surplus stock of SKU-1002 from a sibling warehouse?")
    assert r["transfer_result"]["required_quantity"] == 500  # the product's reorder quantity, labelled
    assert "reorder quantity (500)" in r["response"]


def test_anomalies_come_from_transactions_and_demo_data_is_opt_in(inventory_server, monkeypatch):
    # SKU-1004 has a real -10 outbound transaction in the last 48 h → live anomaly
    r = ask("detect inventory shrinkage for SKU-1004")
    assert r["anomaly_result"]["is_demo"] is False and r["anomaly_result"]["variance"] == -10
    assert "Demo scenario" not in r["response"]
    # SKU-1001 has no transactions → empty, and no curated scenario is shown in its place
    r = ask("detect inventory shrinkage for SKU-1001")
    assert r["outcome"] == "empty" and r["anomaly_result"] is None
    monkeypatch.setenv("INVENTORY_DEMO_DATA", "true")
    r = ask("any shrinkage anomaly on SKU-4521?")
    assert r["outcome"] == "not_found"  # demo scenarios never stand in for a product that doesn't exist


# ── Ambiguity and follow-ups ─────────────────────────────────────────────────

def test_ambiguous_product_asks_a_short_clarification(inventory_server):
    r = ask("how many thermal labels do we have?")
    assert r["outcome"] == "clarification_needed"
    assert {c["sku"] for c in r["clarification"]} == {"SKU-1001", "SKU-1002"}
    assert "Which one did you mean?" in r["response"]


def test_clarification_answer_picks_the_offered_product(inventory_server):
    first = ask("how many thermal labels do we have?")
    conv = first["context_update"]
    second_label = first["clarification"][1]
    r = ask("the second one", conversation=conv)
    assert r["items"][0]["sku"] == second_label["sku"]
    r = ask("the printer", conversation=conv)
    assert r["items"][0]["sku"] == "SKU-1001"


def test_follow_up_resolves_to_previous_product(inventory_server):
    first = ask("how many wireless barcode scanners are on hand?")
    r = ask("and where is it?", conversation=first["context_update"])
    assert r["items"][0]["sku"] == "SKU-1004" and "Using **SKU-1004** from earlier" in r["response"]


def test_new_product_named_in_a_follow_up_wins_over_context(inventory_server):
    first = ask("how many wireless barcode scanners are on hand?")
    r = ask("pallet wrap stock?", conversation=first["context_update"])
    assert r["items"][0]["sku"] == "SKU-1003"


def test_question_without_product_and_no_context_asks_which(inventory_server):
    r = ask("where is it?")
    assert r["outcome"] == "needs_product" and "Which product" in r["response"]


def test_conversations_do_not_share_context(inventory_server):
    a = ask("how many SKU-1001 are on hand?")["context_update"]
    b = ask("how many SKU-1004 are on hand?")["context_update"]
    assert ask("where is it?", conversation=a)["items"][0]["sku"] == "SKU-1001"
    assert ask("where is it?", conversation=b)["items"][0]["sku"] == "SKU-1004"


# ── Failures ─────────────────────────────────────────────────────────────────

def test_database_failure_is_an_error_not_not_found(tmp_path, monkeypatch, inventory_server):
    from mcp_servers.inventory_mcp_server import build_inventory_server
    from mcp_servers.mcp_tool_client import inventory_tool_gateway
    broken = sessionmaker(bind=create_engine(f"sqlite:///{tmp_path}/missing-dir/none.db"))
    monkeypatch.setattr(inventory_tool_gateway, "server_factory", lambda: build_inventory_server(broken))
    r = ask("where is SKU-1001?")
    assert r["outcome"] == "error" and r["error_code"] == "DB_UNAVAILABLE" and r["items"] == []
    assert "couldn't find" not in r["response"] and "could not be queried" in r["response"]


def test_mcp_misconfiguration_is_reported_not_guessed(inventory_server, monkeypatch):
    monkeypatch.setenv("INVENTORY_MCP_TRANSPORT", "streamable_http")
    r = ask("where is SKU-1001?")
    assert r["outcome"] == "error" and r["error_code"] == "MCP_CONFIG_INVALID" and r["items"] == []


# ── Digital Twin path (twin tools replaced by fakes; no PostgreSQL needed) ────

def test_twin_answer_is_published_to_the_browser_session(inventory_server, monkeypatch):
    import agents.inventory_agent.tools as T
    published = []
    cmd = {"version": "1.1", "action": "locate_product", "product_ids": ["PRD-00008"], "answer_text": "x"}
    monkeypatch.setattr(T, "twin_answer", lambda q: C.TwinAnswerResult(status="ok", command=cmd, chat_text="On F3."))
    monkeypatch.setattr(T, "publish_map_command",
                        lambda s, q, c: published.append(s) or C.PublishMapCommandResult(status="ok", command_id="c1"))
    r = ask("where is the coconut milk", session_id="tab-1")
    assert r["source"] == "digital_twin" and r["ui_command_id"] == "c1" and published == ["tab-1"]
    assert r["context_update"]["product_ids"] == ["PRD-00008"]


def test_twin_clarification_then_pick_by_number(inventory_server, monkeypatch):
    import agents.inventory_agent.tools as T
    seen = []
    clarify = {"version": "1.1", "action": "clarify", "answer_text": "Which?", "candidates": [
        {"label": "Box A (PRD-00001)", "product_id": "PRD-00001"},
        {"label": "Box B (PRD-00002)", "product_id": "PRD-00002"}]}
    locate = {"version": "1.1", "action": "locate_product", "product_ids": ["PRD-00002"], "answer_text": "B"}

    def fake(query):
        seen.append(query)
        cmd = locate if "PRD-00002" in query else clarify
        return C.TwinAnswerResult(status="ok", command=cmd, chat_text=cmd["answer_text"])
    monkeypatch.setattr(T, "twin_answer", fake)
    first = ask("where is the box")
    assert first["outcome"] == "clarification_needed"
    r = ask("2", conversation=first["context_update"])
    assert seen[-1].endswith("PRD-00002") and r["ui_command"]["product_ids"] == ["PRD-00002"]


def test_twin_place_total_is_not_accepted_for_a_product_question(inventory_server, monkeypatch):
    """Found in the live smoke test: the twin counted the whole warehouse for an unknown product."""
    import agents.inventory_agent.tools as T
    total = {"version": "1.1", "action": "count", "scope": {"level": "warehouse", "id": "WH1"},
             "metric": "total_units", "answer_text": "The warehouse holds 580 units across 11 products."}
    monkeypatch.setattr(T, "twin_answer",
                        lambda q: C.TwinAnswerResult(status="ok", command=total, chat_text=total["answer_text"]))
    r = ask("how many wireless barcode scanners are on hand?")
    assert r["source"] == "database" and r["items"][0]["sku"] == "SKU-1004" and "580" not in r["response"]
    # A count about a place (no product named) is still the twin's answer
    r = ask("how many units are in cold storage on floor 2?")
    assert r["source"] == "digital_twin" and r["response"].startswith("The warehouse holds")


def test_sku_questions_skip_the_twin(inventory_server, monkeypatch):
    import agents.inventory_agent.tools as T
    monkeypatch.setattr(T, "twin_answer", lambda q: pytest.fail("twin must not answer SKU-xxxx questions"))
    assert ask("where is SKU-1001?")["items"][0]["sku"] == "SKU-1001"


# ── Facades and cross-agent coordination ─────────────────────────────────────

def test_sync_facade_works_inside_a_running_event_loop(inventory_server):
    async def caller():
        return handle_inventory_query("where is SKU-1004?")  # sync call from async code
    r = asyncio.run(caller())
    assert r["items"][0]["sku"] == "SKU-1004" and r["warehouse_layout"] is not None


@pytest.mark.parametrize("text", list(responder.FAILURE_TEXT.values()) + [
    responder.not_found("SKU1"), responder.needs_product("stock_check")])
def test_failure_and_not_found_texts_avoid_fulfillment_keywords(text):
    low = text.lower()
    assert not any(k in low for k in ("available", "stock:", "units on hand", "out of stock"))
    assert not re.search(r"\d0 units", low)


@pytest.mark.parametrize("sku, expected", [
    ("SKU-1003", "is currently out of stock"),                # zero stock
    ("SKU-1004", "currently has stock available"),            # 340 on hand ("340 units" no longer reads as 0)
    ("SKU-4040", "specific delay reason is not available"),   # unknown product: no stock claim either way
])
def test_fulfillment_handoff_reads_the_inventory_answer_correctly(inventory_server, sku, expected):
    from agents.fulfillment.fulfillment_agent import FulfillmentAgent
    from agents.fulfillment.schemas import FulfillmentIntent, FulfillmentIntentResult, FulfillmentRequest
    classifier = MagicMock()
    classifier.classify.return_value = FulfillmentIntentResult(intent=FulfillmentIntent.ORDER_DELAY, confidence=0.9)
    order = MagicMock(status="delayed", sku=sku)
    with patch("agents.fulfillment.fulfillment_agent.get_order_by_id", return_value=order):
        resp = asyncio.run(FulfillmentAgent(classifier=classifier).handle(
            FulfillmentRequest(query="Why is ORD-1001 delayed?"), MagicMock()))
    assert expected in resp.message
