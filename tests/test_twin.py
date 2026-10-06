"""
Warehouse Digital Twin tests.

Contract + routing tests always run. Database tests run the BUILD_PROMPT
acceptance scenarios against seed.sql and need a THROWAWAY PostgreSQL, because
they drop and rebuild the twin schema:

    TWIN_TEST_DATABASE_URL=postgresql://user:pass@localhost:55432/db pytest tests/test_twin.py
"""
import json
import os

import pytest
from pydantic import ValidationError

from agents.coordinator.intent_classifier import IntentClassifier
from agents.inventory_agent import twin_navigator
from agents.inventory_agent.schemas import UiCommand
from agents.inventory_agent.twin_navigator import _Candidate, _pick, build_twin_answer
from config.settings import settings
from database.twin import connection as twin_connection
from database.twin import repository as twin_repo
from database.twin.setup import ensure_twin_schema

TEST_DB_URL = os.getenv("TWIN_TEST_DATABASE_URL")
needs_db = pytest.mark.skipif(not TEST_DB_URL, reason="set TWIN_TEST_DATABASE_URL to a throwaway PostgreSQL")


# ── UI command contract (mirrors database/twin/ui_command.schema.json) ──────

def _schema():
    return json.loads((settings.TWIN_SQL_DIR / "ui_command.schema.json").read_text(encoding="utf-8"))


def test_schema_examples_are_valid_ui_commands():
    for example in _schema()["examples"]:
        assert UiCommand(**example).to_payload() == example


@pytest.mark.parametrize("payload", [
    {"version": "1.1", "action": "locate_product", "answer_text": "x"},                        # needs product_ids
    {"version": "1.1", "action": "show_location", "answer_text": "x", "location_ids": []},
    {"version": "1.1", "action": "show_location", "answer_text": "x", "location_ids": ["WH1-F2-R02"]},
    {"version": "1.1", "action": "heatmap", "answer_text": "x"},                               # needs floor_id
    {"version": "1.1", "action": "navigate", "answer_text": "x", "route": {"prefer": "lift"}},
    {"version": "1.1", "action": "clarify", "answer_text": "x",
     "candidates": [{"label": "a", "product_id": "PRD-00001"}]},                                # needs 2
    {"version": "1.1", "action": "clarify", "answer_text": "x",
     "candidates": [{"label": "a"}, {"label": "b", "product_id": "PRD-00002"}]},               # no target
    {"version": "2.0", "action": "clear", "answer_text": "x"},
    {"version": "1.1", "action": "clear", "answer_text": "x", "extra": 1},
])
def test_invalid_ui_commands_are_rejected(payload):
    with pytest.raises(ValidationError):
        UiCommand(**payload)


def test_pydantic_model_agrees_with_json_schema():
    jsonschema = pytest.importorskip("jsonschema")
    validator = jsonschema.Draft202012Validator(_schema())
    good = {"version": "1.1", "action": "count", "answer_text": "x", "scope": {"level": "rack", "id": "WH1-F2-Z01-R02"}}
    bad = {"version": "1.1", "action": "count", "answer_text": "x"}
    assert validator.is_valid(good) and UiCommand(**good)
    assert not validator.is_valid(bad)
    with pytest.raises(ValidationError):
        UiCommand(**bad)


# ── Candidate choice (agent rule: >= 0.9 and >= 0.1 ahead, else clarify) ─────

def _c(score, kind="product", match="name", cid="PRD-00001"):
    return _Candidate(kind, cid, score, "n", "l", match)


def test_pick_single_candidate_is_used():
    assert _pick([_c(0.5)]).mode == "one"


def test_pick_needs_clear_margin():
    assert _pick([_c(0.95), _c(0.9)]).mode == "clarify"
    assert _pick([_c(1.0), _c(0.9)]).mode == "one"
    assert _pick([_c(0.85), _c(0.5)]).mode == "clarify"


def test_pick_rack_type_matches_show_all():
    cands = [_c(0.6, "location", "rack_type", f"WH1-F3-Z02-R0{i}") for i in range(1, 4)]
    assert _pick(cands).mode == "multi"


def test_navigator_disabled_without_postgres(monkeypatch):
    monkeypatch.setattr(twin_navigator, "is_enabled", lambda: False)
    assert build_twin_answer("where is product number 2?") is None


# ── Coordinator routing: twin questions go to the inventory agent ───────────

@pytest.mark.parametrize("query", [
    "where is product number 2?", "where is rack 2?", "how do I get to Cold 3?",
    "how many products are in rack 2 on floor 2", "where is PRD-00002",
])
def test_twin_place_and_product_ids_route_to_inventory(query):
    # High-confidence heuristic: decided without calling the LLM
    assert IntentClassifier(llm=None).classify(query).domain == "INVENTORY"


@pytest.mark.parametrize("query", [
    "where is the cold storage?", "take me to unit 3 on floor 3 by stairs", "what's running low",
    "where is the coconut milk",
])
def test_generic_map_wording_falls_back_to_inventory(query):
    # The LLM decides these when it is available; inventory is the no-LLM fallback
    assert IntentClassifier(llm=None)._heuristic_fallback(query).domain == "INVENTORY"


@pytest.mark.parametrize("query, domain", [
    ("where is the returns SOP?", "KNOWLEDGE"),
    ("What is the return policy for item 2?", "KNOWLEDGE"),
    ("What PPE is needed in cold storage? Check the safety protocol", "KNOWLEDGE"),
    ("why is order #4521 delayed?", "FULFILLMENT"),
    ("Track the shipment for product #3", "FULFILLMENT"),
    ("where is order ORD-1001?", "FULFILLMENT"),
])
def test_sop_and_order_questions_still_route_elsewhere(query, domain):
    assert IntentClassifier(llm=None).classify(query).domain == domain


@pytest.mark.parametrize("query", [
    "Where is the emergency assembly point?", "What PPE is needed in cold storage?",
    "Is unit 4 compliant with the hazmat storage rules?",
])
def test_generic_map_wording_leaves_the_decision_to_the_llm(query):
    # Below the heuristic threshold, so the LLM classifies it exactly as before the twin existed
    clf = IntentClassifier(llm=None)
    assert clf._heuristic_fallback(query).confidence < clf.HEURISTIC_CONFIDENCE_THRESHOLD


# ── Acceptance scenarios against seed.sql (throwaway PostgreSQL only) ───────

@pytest.fixture(scope="module")
def twin_db():
    if not TEST_DB_URL:
        pytest.skip("set TWIN_TEST_DATABASE_URL")
    old_url, old_engine = settings.TWIN_DATABASE_URL, twin_connection._engine
    settings.TWIN_DATABASE_URL = TEST_DB_URL
    twin_connection._engine = None
    ensure_twin_schema(reset=True)
    yield
    twin_connection._engine = None
    settings.TWIN_DATABASE_URL, twin_connection._engine = old_url, old_engine


def _ask(query):
    answer = build_twin_answer(query)
    assert answer is not None, query
    return answer.command


@needs_db
def test_seed_text_round_trips_utf8(twin_db):
    zones = {z["id"]: z["name"] for z in twin_repo.get_layout()["zones"]}
    assert zones["WH1-F3-Z01"] == "Zone A — Cold storage"


@needs_db
def test_where_is_product_number_2(twin_db):
    cmd = _ask("where is product number 2?")
    assert cmd["action"] == "locate_product" and cmd["product_ids"] == ["PRD-00002"]
    racks = {r["rack_id"] for r in twin_repo.get_product_locations(["PRD-00002"]) if r["floor_id"] == "WH1-F2"}
    assert racks == {"WH1-F2-Z01-R02", "WH1-F2-Z03-R03"}
    route = twin_repo.get_route("PRD-00002")
    assert len(route["directions"]) == 7
    assert route["directions"][-1]["total_s"] == 57
    assert "Go to shelf 3 (3rd level up from the floor), bin 4" in route["directions"][-1]["instruction"]
    assert route["path"][0]["node_id"] == "WH1-F1-N001" and route["path"][-1]["floor_id"] == "WH1-F2"


@needs_db
def test_where_is_rack_2_asks_which_floor(twin_db):
    cmd = _ask("where is rack 2?")
    assert cmd["action"] == "clarify"
    assert [c["label"] for c in cmd["candidates"]] == ["Rack 2 · Floor 1", "Rack 2 · Floor 2"]


@needs_db
def test_where_is_cold_3(twin_db):
    cmd = _ask("where is cold 3?")
    assert cmd["action"] == "show_location" and cmd["location_ids"] == ["WH1-F3-Z01-R03"]
    route = twin_repo.get_route("WH1-F3-Z01-R03")
    assert route["directions"][-1]["total_s"] == 93
    assert {p["via"] for p in route["path"]} >= {"lift"}


@needs_db
def test_unit_3_by_stairs(twin_db):
    cmd = _ask("take me to unit 3 on floor 3 by stairs")
    assert cmd["action"] == "navigate" and cmd["route"] == {"to_id": "WH1-F3-Z02-R03", "prefer": "stairs"}
    steps = [d["instruction"] for d in twin_repo.get_route("WH1-F3-Z02-R03", None, "stairs")["directions"]]
    assert "Take Stairs 1 up to Floor 3." in steps
    assert steps[-1].startswith("You have arrived. Unit 3") and "is on your right" in steps[-1]


@needs_db
def test_lift_closed_falls_back_to_stairs(twin_db):
    with twin_connection.twin_connection() as conn:
        conn.exec_driver_sql("update nav_edges set blocked = true where edge_type = 'lift'")
    try:
        route = twin_repo.get_route("WH1-F3-Z01-R03")
        assert route["prefer_used"] == "fastest"
        assert all(p["via"] != "lift" for p in route["path"])
        notes = [d["instruction"] for d in route["directions"] if d["kind"] == "note"]
        assert notes == ["No open route using the lift, so this uses the fastest open route."]
    finally:
        with twin_connection.twin_connection() as conn:
            conn.exec_driver_sql("update nav_edges set blocked = false where edge_type = 'lift'")


@needs_db
def test_shelf_racks_on_floor_3(twin_db):
    cmd = _ask("where are the shelf racks on floor 3")
    assert cmd["action"] == "show_location"
    assert cmd["location_ids"] == [f"WH1-F3-Z02-R0{i}" for i in range(1, 6)]


@needs_db
def test_coconut_milk(twin_db):
    cmd = _ask("where is the coconut milk")
    assert cmd["product_ids"] == ["PRD-00008"]
    rows = {(r["rack_id"], r["level_index"], r["position_index"]): r["quantity"]
            for r in twin_repo.get_product_locations(["PRD-00008"])}
    assert rows == {("WH1-F3-Z01-R03", 2, 2): 20, ("WH1-F3-Z01-R03", 3, 1): 5}
    assert "Stock is low" in cmd["answer_text"]


@needs_db
def test_count_rack_2_floor_2(twin_db):
    cmd = _ask("how many products are in rack 2 on floor 2")
    assert cmd["scope"] == {"level": "rack", "id": "WH1-F2-Z01-R02"}
    fill = next(f for f in twin_repo.get_rack_fill("WH1-F2") if f["rack_id"] == "WH1-F2-Z01-R02")
    assert fill["total_units"] == 30


@needs_db
def test_running_low(twin_db):
    assert _ask("what's running low")["action"] == "show_alerts"
    alerts = twin_repo.get_open_alerts()
    assert sorted(a["type"] for a in alerts) == ["low_stock"] * 4 + ["out_of_stock"]
    assert {a["floor_id"] for a in alerts} == {"WH1-F1", "WH1-F2", "WH1-F3"}


@needs_db
def test_live_stock_change_updates_rack_fill(twin_db):
    with twin_connection.twin_connection() as conn:
        conn.exec_driver_sql("select move_stock('PRD-00002', 5, 'pick', 'WH1-F2-Z01-R02-S03-B04')")
    try:
        fill = next(f for f in twin_repo.get_rack_fill("WH1-F2") if f["rack_id"] == "WH1-F2-Z01-R02")
        assert fill["total_units"] == 25
    finally:
        with twin_connection.twin_connection() as conn:
            conn.exec_driver_sql("select move_stock('PRD-00002', 5, 'receive', null, 'WH1-F2-Z01-R02-S03-B04')")


@needs_db
def test_where_is_the_box_asks_which_product(twin_db):
    cmd = _ask("where is the box")
    assert cmd["action"] == "clarify"
    assert all("product_id" in c for c in cmd["candidates"]) and len(cmd["candidates"]) >= 2


@needs_db
def test_bad_location_id_gives_error_step(twin_db):
    directions = twin_repo.get_route("WH1-F9-Z01-R01")["directions"]
    assert directions[0]["kind"] == "error" and "WH1-F9-Z01-R01" in directions[0]["instruction"]


@needs_db
def test_legacy_sku_queries_skip_the_twin(twin_db):
    from agents.inventory_agent.agent import handle_inventory_query
    resp = handle_inventory_query("where is SKU-2045 located?")
    assert resp["ui_command"] is None
