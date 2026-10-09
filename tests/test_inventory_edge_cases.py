"""
Inventory agent edge cases found in the QA pass (frontend E2E + backend, October 2026).

Runs the real agent over the in-memory inventory MCP server and the seeded throwaway
database (tests/inventory_testkit.py). Digital Twin answers are replaced by fakes, so
no PostgreSQL is needed and nothing touches intelliwms.db.
"""
import asyncio
from datetime import date

import anyio
import pytest
from sqlalchemy import text

from agents.inventory_agent import tool_contracts as C
from agents.inventory_agent.agent import handle_inventory_query_async
from agents.inventory_agent.document_parser import document_parser
from agents.inventory_agent.equipment_health import equipment_health_analyzer
from agents.inventory_agent.intents import extract_entities, requested_quantity
from backend.threads.schemas import InventoryThreadContext, PendingCandidate

pytestmark = pytest.mark.mcp_inmemory


def ask(query, **kw):
    return anyio.run(lambda: handle_inventory_query_async(query, **kw))


def set_row(factory, sku, **fields):
    with factory() as s:
        sets = ", ".join(f"{k} = :{k}" for k in fields)
        s.execute(text(f"update products set {sets} where sku = :sku"), {**fields, "sku": sku})
        s.commit()


def fake_twin(monkeypatch, answer):
    """Replace the twin tool: `answer(query)` returns a command dict (or None for not_found)."""
    import agents.inventory_agent.tools as T
    seen = []

    def twin(query):
        seen.append(query)
        cmd = answer(query)
        if cmd is None:
            return C.TwinAnswerResult(status="not_found")
        return C.TwinAnswerResult(status="ok", command=cmd, chat_text=cmd["answer_text"])
    monkeypatch.setattr(T, "twin_answer", twin)
    return seen


# ── Transfers (INV-4, INV-5) ─────────────────────────────────────────────────

def test_transfer_uses_the_quantity_the_user_asked_for(inventory_server):
    r = ask("can we transfer 120 units of SKU-1001 from a sibling warehouse?")
    assert r["transfer_result"]["required_quantity"] == 120
    assert "No quantity was given" not in r["response"]


def test_transfer_quantity_must_be_positive_and_bounded(inventory_server):
    for q in ("transfer 0 units of SKU-1001 from another warehouse",
              "transfer -50 units of SKU-1001 from another warehouse",
              "transfer 200000 units of SKU-1001 from another warehouse"):
        r = ask(q)
        assert r["outcome"] == "invalid_request" and r["transfer_result"] is None, q
        assert "from 1 to 100,000" in r["response"]


def test_transfer_without_quantity_falls_back_to_reorder_quantity(inventory_server):
    r = ask("can we transfer surplus stock of SKU-1001 from a sibling warehouse?")
    assert r["transfer_result"]["required_quantity"] == 50
    assert "reorder quantity (50)" in r["response"]
    assert "No transfer is needed" not in r["response"]  # SKU-1001 is low: a transfer makes sense


def test_transfer_for_an_overstocked_item_says_none_is_needed_first(inventory_server):
    r = ask("can we transfer stock of SKU-1004 from a sibling warehouse?")  # 340 on hand, reorder point 60
    assert r["response"].startswith("ℹ️ **No transfer is needed**")
    assert "overstocked" in r["response"] and "340 on hand vs reorder point 60" in r["response"]


def test_transfer_larger_than_the_sibling_surplus_says_how_much_to_buy(inventory_server):
    from agents.inventory_agent.transfer_advisor import transfer_advisor
    with inventory_server() as db:  # sibling_warehouses.json lists SKU-7788 with a surplus of 45–60
        rec = transfer_advisor.evaluate_transfer("SKU-7788", needed_quantity=500, db=db)
    best = next(o for o in rec.sibling_options if o.is_recommended)
    assert f"only **{best.available_surplus}** spare of the **500** requested" in rec.advisory_verdict
    assert f"order the remaining **{500 - best.available_surplus}**" in rec.advisory_verdict


def test_a_jammed_printer_is_an_equipment_report(inventory_server):
    r = ask("the label printer near dock 2 keeps jamming")
    assert r["sub_intent"] == "equipment_health"
    assert r["equipment_health_result"]["equipment_id"] == "Label Printer"


def test_requested_quantity_ignores_sku_digits():
    assert requested_quantity("transfer SKU-4521 please") is None
    assert requested_quantity("move 1,200 units of SKU-4521") == 1200
    assert requested_quantity("transfer -5 pallets of SKU-4521") == -5


# ── Forecasts (INV-8) ────────────────────────────────────────────────────────

def test_forecast_with_zero_burn_rate_projects_no_stockout(inventory_server):
    set_row(inventory_server, "SKU-1002", daily_burn_rate=0)
    r = ask("depletion forecast for SKU-1002")
    pred = r["prediction_result"]
    assert r["outcome"] == "answered" and pred["days_until_stockout"] is None and pred["urgency"] == "NORMAL"
    assert "no stockout projected" in r["response"]


def test_forecast_with_negative_burn_rate_is_flagged_not_critical(inventory_server):
    set_row(inventory_server, "SKU-1004", daily_burn_rate=-5)
    r = ask("depletion forecast for SKU-1004")
    pred = r["prediction_result"]
    assert pred["urgency"] != "CRITICAL" and pred["days_until_stockout"] is None and pred["burn_rate_valid"] is False
    assert "burn rate is negative" in r["response"]


def test_forecast_quantity_matches_its_wording(inventory_server):
    r = ask("depletion forecast for SKU-1001")  # 15 on hand, 6.2/day, 6-day lead time
    pred = r["prediction_result"]
    assert pred["recommended_reorder_qty"] == 109  # ceil(6.2 × (6 + 14) − 15)
    assert "6-day lead time plus 14 days of use" in r["response"]


def test_hazmat_named_item_needs_compliance_sign_off(inventory_server):
    r = ask("depletion forecast for SKU-1005")  # "Hazmat Spill Kit"
    assert r["prediction_result"]["compliance_check_required"] is True


# ── Stock answers and odd input (INV-12, INV-14) ─────────────────────────────

def test_more_than_three_skus_names_the_ones_left_out(inventory_server):
    r = ask("stock levels for SKU-1001, SKU-1002, SKU-1003 and SKU-1004")
    assert [i["sku"] for i in r["items"]] == ["SKU-1001", "SKU-1002", "SKU-1003"]
    assert "weren't checked: `SKU-1004`" in r["response"]


def test_seven_digit_sku_is_not_found(inventory_server):
    r = ask("stock level for SKU-1001000")
    assert r["outcome"] == "not_found" and "SKU-1001000" in r["response"] and r["items"] == []
    assert extract_entities("SKU-1001000").invalid_skus == ["SKU-1001000"]


def test_empty_question_asks_for_a_product_instead_of_raising(inventory_server):
    for q in ("", "   "):
        r = ask(q)
        assert r["outcome"] == "needs_product", repr(q)


def test_negative_stock_and_over_reservation_never_go_below_zero(inventory_server):
    set_row(inventory_server, "SKU-1001", quantity=-7)
    set_row(inventory_server, "SKU-1002", reserved_quantity=500)
    assert ask("stock level for SKU-1001")["items"][0]["status"] == "OUT_OF_STOCK"
    assert ask("is SKU-1002 in stock?")["items"][0]["available_quantity"] == 0


def test_many_concurrent_questions_do_not_mix_answers(inventory_server):
    async def run():
        qs = [f"stock level for SKU-100{(i % 5) + 1}" for i in range(25)]
        return list(zip(qs, await asyncio.gather(*(handle_inventory_query_async(q) for q in qs))))
    for q, r in anyio.run(run):
        assert r["items"][0]["sku"] == q.split()[-1]


# ── Supplier documents (INV-6) ───────────────────────────────────────────────

TODAY = date(2026, 10, 7)  # a Wednesday


def test_document_quantity_unit_and_weekday_are_read():
    r = document_parser.parse_document("Supplier email: Zebra shipping 40 cartons of label rolls on Friday", TODAY)
    assert r.extracted_quantity == 40 and r.quantity_unit == "cartons"
    assert r.extracted_delivery_date == "Friday (2026-10-09)"
    assert "**40** cartons" in r.raw_summary


@pytest.mark.parametrize("phrase, expected", [
    ("arriving tomorrow", "tomorrow (2026-10-08)"),
    ("arriving next Monday", "Monday (2026-10-12)"),
    ("arriving in 3 days", "in 3 days (2026-10-10)"),
    ("arriving Oct 12", "2026-10-12"),
    ("arriving 2026-10-15", "2026-10-15"),
])
def test_document_dates(phrase, expected):
    r = document_parser.parse_document(f"Supplier email: 10 units of SKU-7788 {phrase}", TODAY)
    assert r.extracted_delivery_date == expected


def test_document_states_missing_facts_instead_of_inventing_them():
    r = document_parser.parse_document("Supplier email: shipment of crates arriving soon", TODAY)
    assert r.extracted_sku is None and r.extracted_quantity is None and r.extracted_delivery_date is None
    assert r.po_reference is None and r.draft_order is None
    assert "No restock request was drafted" in r.raw_summary and "PO Reference: not stated" in r.raw_summary


def test_document_without_po_and_draft_ids_are_unique():
    a = document_parser.parse_document("Supplier email: 10 units of SKU-7788 arriving tomorrow", TODAY)
    b = document_parser.parse_document("Supplier email: 20 units of SKU-9012 arriving tomorrow", TODAY)
    assert a.po_reference is None and b.po_reference is None
    assert a.draft_order.draft_id != b.draft_order.draft_id


def test_document_words_are_not_po_numbers_and_codes_are_not_quantities():
    r = document_parser.parse_document("Supplier email: Order confirmed, 30 units of SKU-9012 arriving tomorrow", TODAY)
    assert r.po_reference is None and r.extracted_quantity == 30
    r = document_parser.parse_document("Supplier email: PO-88321 for SKU-4521, qty 75", TODAY)
    assert r.po_reference == "88321" and r.extracted_quantity == 75


def test_document_for_an_unknown_sku_drafts_nothing(inventory_server):
    r = ask("supplier email: Apex shipped 20 units of SKU-77777 arriving tomorrow")
    assert r["document_result"]["draft_order"] is None
    assert "SKU-77777 isn't in the inventory records" in r["response"]


def test_document_for_a_known_sku_uses_the_catalogue_name(inventory_server):
    r = ask("supplier email: Apex shipped 200 units of SKU-1001 arriving tomorrow")
    assert r["document_result"]["draft_order"]["item_name"] == "Thermal Label Printer"
    assert "drafted for Floor Manager approval" in r["response"]


# ── Equipment health (INV-7) ─────────────────────────────────────────────────

def test_unknown_equipment_is_not_reported_as_forklift_3():
    r = equipment_health_analyzer.analyze_log("the label printer near dock 2 keeps jamming")
    assert r.equipment_id == "Label Printer" and r.equipment_type == "Printer"
    assert r.recurrence_count == 1 and r.breakdown_risk != "IMMINENT"
    assert r.detected_failure_mode.startswith("Unclassified")


def test_no_named_machine_says_so():
    r = equipment_health_analyzer.analyze_log("something is making a weird noise near the dock")
    assert r.equipment_id.startswith("Unidentified equipment")


@pytest.mark.parametrize("log, equipment_id, equipment_type", [
    ("conveyor belt 2 is overheating", "Conveyor Belt 2", "Conveyor"),
    ("Parcel sorting conveyor line A-02 belt slipping", "Conveyor Line A-02", "Conveyor"),
    ("forklift 7 is overheating badly", "Forklift 7", "Forklift"),
    ("AGV-08 keeps stopping on the runway", "AGV-08", "AGV"),
])
def test_equipment_unit_and_type_come_from_the_named_machine(log, equipment_id, equipment_type):
    r = equipment_health_analyzer.analyze_log(log)
    assert (r.equipment_id, r.equipment_type) == (equipment_id, equipment_type)


def test_recurrence_counts_the_same_unit_only():
    assert equipment_health_analyzer.analyze_log("forklift 3 grinding noise").recurrence_count == 3
    assert equipment_health_analyzer.analyze_log("forklift 30 grinding noise").recurrence_count == 1


# ── Digital Twin answers (INV-1, INV-2, INV-3) ───────────────────────────────

PALLET_RACKS = {"version": "1.1", "action": "show_location", "location_ids": ["WH1-F1-Z01-R01", "WH1-F2-Z01-R01"],
                "floor_id": "WH1-F1", "answer_text": "There are 2 pallet racks — Floor 1: Rack 1; Floor 2: Rack 1."}


def test_product_named_like_a_rack_type_is_answered_from_the_catalogue(inventory_server, monkeypatch):
    fake_twin(monkeypatch, lambda q: PALLET_RACKS)
    r = ask("where is the pallet wrap?")  # SKU-1003 "Stretch Pallet Wrap"
    assert r["source"] == "database" and r["items"][0]["sku"] == "SKU-1003"
    r = ask("is the pallet wrap in stock?")
    assert r["items"][0]["sku"] == "SKU-1003" and "pallet racks" not in r["response"]


def test_a_real_rack_question_still_gets_the_map(inventory_server, monkeypatch):
    fake_twin(monkeypatch, lambda q: PALLET_RACKS)
    r = ask("where are the pallet racks?")
    assert r["source"] == "digital_twin" and r["ui_command"]["action"] == "show_location"


def test_running_low_includes_the_sku_catalogue(inventory_server, monkeypatch):
    alerts = {"version": "1.1", "action": "show_alerts", "alert_types": ["low_stock", "out_of_stock"],
              "answer_text": "2 products are running low."}
    fake_twin(monkeypatch, lambda q: alerts)
    r = ask("what's running low?")
    assert r["source"] == "digital_twin" and "SKU catalogue" in r["response"]
    for sku in ("SKU-1003", "SKU-1001", "SKU-1005"):  # out of stock, low, low on default thresholds
        assert sku in r["response"]
    assert "SKU-1004" not in r["response"]


RACK_2_CLARIFY = {"version": "1.1", "action": "clarify", "answer_text": "There's a Rack 2 on Floor 1 and on Floor 2.",
                  "candidates": [{"label": "Rack 2 · Floor 1", "location_id": "WH1-F1-Z01-R02"},
                                 {"label": "Rack 2 · Floor 2", "location_id": "WH1-F2-Z01-R02"}]}


def _rack_answers(q):
    if "WH1-F2-Z01-R02" in q:
        action = "count" if "how many" in q else "show_location"
        cmd = {"version": "1.1", "action": action, "answer_text": f"{action} rack 2 floor 2",
               "floor_id": "WH1-F2", "location_ids": ["WH1-F2-Z01-R02"]}
        if action == "count":
            cmd = {**cmd, "scope": {"level": "rack", "id": "WH1-F2-Z01-R02"}, "metric": "total_units"}
            cmd.pop("location_ids")
        return cmd
    return RACK_2_CLARIFY


def test_picking_a_place_by_number_answers_for_that_place(inventory_server, monkeypatch):
    seen = fake_twin(monkeypatch, _rack_answers)
    first = ask("where is rack 2?")
    assert first["outcome"] == "clarification_needed"
    assert first["context_update"]["pending_clarification"][1]["location_id"] == "WH1-F2-Z01-R02"
    assert first["context_update"]["pending_query"] == "where is rack 2?"
    r = ask("2", conversation=first["context_update"])
    assert seen[-1] == "where is rack 2? WH1-F2-Z01-R02"
    assert r["ui_command"]["action"] == "show_location" and r["ui_command"]["location_ids"] == ["WH1-F2-Z01-R02"]


def test_a_place_pick_keeps_the_original_question(inventory_server, monkeypatch):
    seen = fake_twin(monkeypatch, _rack_answers)
    first = ask("how many products are in rack 2?")
    r = ask("the second one", conversation=first["context_update"])
    assert seen[-1].startswith("how many products are in rack 2?") and r["ui_command"]["action"] == "count"


def test_thread_context_accepts_place_picks_and_rejects_bad_ids():
    ctx = InventoryThreadContext.model_validate({
        "pending_clarification": [{"label": "Rack 2 · Floor 2", "location_id": "WH1-F2-Z01-R02"}],
        "pending_query": "where is rack 2?"})
    assert ctx.pending_clarification[0].location_id == "WH1-F2-Z01-R02"
    with pytest.raises(ValueError):
        PendingCandidate(label="x", location_id="../../etc")
