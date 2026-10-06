"""
Unit and Integration Tests for Member 1 — Inventory Agent.

Tests all 5 key components + Warehouse Spatial Engine:
  1. Document Parser (Inbound supplier email & PDF NER, draft restock orders)
  2. Reorder Predictor (Daily burn rates, depletion velocity, days-to-stockout)
  3. Anomaly Watcher (Physical shrinkage, movement discrepancies, financial loss)
  4. Transfer Advisor (Sibling warehouse surplus evaluation vs external vendor POs)
  5. Equipment Health (Informal complaint logs NLP, breakdown prevention)
  6. Warehouse Spatial Map (Exact rack coordinates, tier, and occupancy)
"""
import pytest
from agents.inventory_agent.document_parser import document_parser
from agents.inventory_agent.reorder_predictor import reorder_predictor
from agents.inventory_agent.anomaly_watcher import anomaly_watcher
from agents.inventory_agent.transfer_advisor import transfer_advisor
from agents.inventory_agent.equipment_health import equipment_health_analyzer
from agents.inventory_agent.warehouse_map import get_sku_map_coordinates, get_full_warehouse_layout
from agents.inventory_agent.agent import handle_inventory_query, inventory_agent
from agents.inventory_agent.schemas import InventoryQueryRequest


def test_document_parser_supplier_email():
    """Verify Document Parser extracts SKU, quantity, delivery date, and drafts PO from email."""
    email_text = """
    From: Apex Automotive Supplies <orders@apexauto.com>
    Subject: Inbound Delivery Confirmation PO-88321
    Hi warehouse team,
    We have dispatched 150 units of Wireless Barcode Scanner (SKU-4521).
    Expected delivery date is 2026-10-15.
    Please ensure loading bay 04 is clear.
    """
    res = document_parser.parse_document(email_text)
    assert res.extracted_sku == "SKU-4521"
    assert res.extracted_quantity == 150
    assert "2026-10-15" in res.extracted_delivery_date
    assert res.supplier_name == "Apex Automotive Supplies"
    assert res.draft_order is not None
    assert res.draft_order.sku == "SKU-4521"
    assert res.draft_order.quantity == 150
    assert res.draft_order.status == "DRAFT_PENDING_APPROVAL"


def test_document_parser_fallback_product_name():
    """Verify Document Parser handles missing SKU by inferring from product synonym."""
    raw_note = "Supplier notification: Zebra Technologies shipped 60 thermal label printers arriving tomorrow."
    res = document_parser.parse_document(raw_note)
    assert res.extracted_sku == "SKU-7788"
    assert res.extracted_quantity == 60


def test_reorder_predictor_velocity():
    """Verify depletion trends and runout velocity calculations."""
    pred = reorder_predictor.predict_depletion("SKU-9012", current_stock=10, item_name="Heavy Duty Pallet Wrap")
    assert pred.sku == "SKU-9012"
    assert pred.daily_burn_rate > 0
    assert pred.days_until_stockout < 1.0  # 10 / 32 = 0.3 days
    assert pred.urgency == "CRITICAL"
    assert pred.recommended_reorder_qty > 0


def test_reorder_predictor_regulated_compliance():
    """Verify regulated items (Lithium batteries) flag compliance requirement."""
    pred = reorder_predictor.predict_depletion("SKU-2045", current_stock=40, item_name="Heavy Duty Forklift Battery Lithium")
    assert pred.compliance_check_required is True


def test_anomaly_watcher_shrinkage():
    """Verify shrinkage anomaly detection and financial loss exposure calculation."""
    # No live transactions in the dev DB: the curated scenario is opt-in and flagged as demo data
    assert anomaly_watcher.check_sku_anomalies("SKU-9012", include_demo=False) is None
    alert = anomaly_watcher.check_sku_anomalies("SKU-9012", include_demo=True)
    assert alert is not None
    assert alert.is_demo is True
    assert alert.anomaly_type == "UNEXPLAINED_SHRINKAGE"
    assert alert.variance == -20
    assert alert.loss_value_est > 0
    assert alert.severity == "HIGH"
    assert "Audit" in alert.recommended_action


def test_transfer_advisor_sibling_hubs():
    """Verify Transfer Advisor compares sibling warehouses and calculates logistics savings."""
    rec = transfer_advisor.evaluate_transfer("SKU-4521", needed_quantity=50)
    assert rec.sku == "SKU-4521"
    assert len(rec.sibling_options) > 0
    assert rec.recommended_source_warehouse is not None
    assert rec.cost_savings_est > 0
    assert "Transfer" in rec.advisory_verdict


def test_equipment_health_informal_log_grinding():
    """Verify informal complaint triage extracts breakdown risk without sensors."""
    complaint = "Shift 1 handoff note: operator said forklift 3 is making loud grinding noise when raising pallets"
    report = equipment_health_analyzer.analyze_log(complaint)
    assert report.equipment_type == "Forklift"
    assert "Bearing" in report.detected_failure_mode or "Gear" in report.detected_failure_mode
    assert report.breakdown_risk in ("HIGH", "IMMINENT")
    assert report.action_required != ""


def test_equipment_health_conveyor_slipping():
    """Verify conveyor slipping complaint triage."""
    complaint = "Parcel sorting conveyor line A-02 belt slipping and squealing"
    report = equipment_health_analyzer.analyze_log(complaint)
    assert report.equipment_type == "Conveyor"
    assert "Tension" in report.detected_failure_mode or "Belt" in report.detected_failure_mode


def test_warehouse_spatial_map():
    """Verify warehouse spatial map returns exact aisle, tier, and coordinates."""
    coords = get_sku_map_coordinates("SKU-4521")
    assert coords["aisle"] == 12
    assert coords["shelf"] == "B3"
    assert coords["tier"] == "B"

    full_map = get_full_warehouse_layout()
    assert len(full_map["aisles"]) == 14
    assert len(full_map["agv_fleet"]) >= 3


def test_inventory_agent_end_to_end_dispatcher(monkeypatch):
    """Test unified agent dispatch across all Member 1 sub-intents."""
    monkeypatch.setenv("INVENTORY_DEMO_DATA", "true")  # anomaly scenarios are demo data, labelled as such
    # 1. Document parser query
    resp1 = handle_inventory_query("supplier email: Apex shipped 200 units of SKU-4521 arriving tomorrow")
    assert resp1["sub_intent"] == "document_parser"
    assert resp1["document_result"] is not None
    assert resp1["document_result"]["extracted_sku"] == "SKU-4521"

    # 2. Equipment health query
    resp2 = handle_inventory_query("forklift 3 is making a grinding noise on mast")
    assert resp2["sub_intent"] == "equipment_health"
    assert resp2["equipment_health_result"] is not None

    # 3. Anomaly query
    resp3 = handle_inventory_query("detect inventory shrinkage for SKU-9012")
    assert resp3["sub_intent"] == "anomaly_watcher"
    assert resp3["anomaly_result"] is not None
    assert resp3["anomaly_result"]["is_demo"] is True
    assert "Demo scenario" in resp3["response"]

    # 4. Transfer query
    resp4 = handle_inventory_query("can we transfer surplus stock of SKU-4521 from sibling warehouse?")
    assert resp4["sub_intent"] == "transfer_advisor"
    assert resp4["transfer_result"] is not None

    # 5. Reorder depletion predictor
    resp5 = handle_inventory_query("what is the stock burn rate and depletion prediction for SKU-9012?")
    assert resp5["sub_intent"] == "reorder_predictor"
    assert resp5["prediction_result"] is not None

    # 6. SKU Location lookup (dynamic map attached)
    resp6 = handle_inventory_query("where is SKU-2045 located?")
    assert len(resp6["items"]) == 1
    assert resp6["items"][0]["aisle"] == 4
    assert resp6["items"][0]["tier"] == "B"
    assert resp6["warehouse_layout"] is not None
