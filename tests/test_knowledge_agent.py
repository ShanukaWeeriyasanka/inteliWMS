"""
Unit and Integration Tests for Knowledge Agent.
Covers physical location resolver, vector RAG retrieval, NER entity extraction,
fast-path agent execution, and FastAPI microservice endpoints.
"""
import pytest
import io
from fastapi.testclient import TestClient

from agents.knowledge_agent.agent import execute_knowledge_query
from agents.knowledge_agent.location_resolver import resolve_location, get_location_by_sku
from agents.knowledge_agent.knowledge_store import knowledge_store, seed_warehouse_sops
from agents.knowledge_agent.ner import extract_warehouse_entities
from agents.knowledge_agent.server import app
from database.connection import init_db
from agents.knowledge_agent.shift_handoff import (
    record_shift_handoff,
    get_latest_shift_handoff
)
from agents.knowledge_agent.compliance import check_compliance, evaluate_compliance_query
from agents.knowledge_agent.returns_handler import triage_returned_item, evaluate_return_query



client = TestClient(app)


@pytest.fixture(autouse=True)
def ensure_sops_seeded():
    """Ensure vector store has seed SOPs before each test."""
    init_db()
    seed_warehouse_sops(knowledge_store)


# ==================== 1. Physical Location Resolver Tests ====================

def test_resolve_location_by_sku():
    """Test looking up item by exact SKU code."""
    result = resolve_location("where is SKU-4521?")
    assert result["found"] is True
    assert result["sku"] == "SKU-4521"
    assert "stored at" in result["formatted_message"].lower() or "aisle" in result["formatted_message"].lower()


def test_resolve_location_by_nonexistent_sku():
    """Test looking up an invalid or missing SKU."""
    result = resolve_location("check location of SKU-999999")
    assert result["found"] is False
    assert "was not found" in result["formatted_message"]


def test_resolve_location_natural_language_synonym():
    """Test natural language product lookup using ontology synonym (rf gun -> barcode scanner)."""
    result = resolve_location("where is the rf gun?")
    assert result["found"] is True
    # Should resolve to Barcode Scanner
    assert "scanner" in result.get("name", "").lower() or result.get("multiple") is True


def test_resolve_location_empty_query():
    """Test passing empty query to resolver."""
    result = resolve_location("")
    assert result["found"] is False


# ==================== 2. Vector RAG SOP Retrieval Tests ====================

def test_rag_query_safety_protocol():
    """Test retrieving safety protocol for forklift speed."""
    hits = knowledge_store.query("forklift speed limit in aisles", n_results=2)
    assert len(hits) > 0
    best_hit = hits[0]
    assert "Safety Protocol" in best_hit["title"] or "speed" in best_hit["content"].lower()
    assert "5 mph" in best_hit["content"] or "8 km/h" in best_hit["content"]


def test_rag_query_battery_acid():
    """Test retrieving hazardous material / battery spill protocol."""
    hits = knowledge_store.query("battery acid spill procedure", n_results=2)
    assert len(hits) > 0
    content = hits[0]["content"].lower()
    assert "battery" in content or "acid" in content


def test_rag_query_returns_sop():
    """Test retrieving returns documentation and RMA procedure."""
    hits = knowledge_store.query("where is the returns SOP documentation?", n_results=2)
    assert len(hits) > 0
    assert any("Returns" in h["title"] or "RMA" in h["content"] for h in hits)


# ==================== 3. NER Entity Extraction Tests ====================

def test_ner_extracts_skus_and_locations():
    """Test extracting SKU and physical warehouse coordinates."""
    text = "Move SKU-4521 to Aisle 14 and Shelf B2 by tomorrow"
    entities = extract_warehouse_entities(text)
    assert "SKU-4521" in entities["skus"]
    assert any("Aisle 14" in loc for loc in entities["locations"])
    assert any("Shelf B2" in loc for loc in entities["locations"])
    assert len(entities["dates"]) > 0


def test_ner_intent_classification():
    """Test intent detection for SOP enquiries vs location lookups."""
    doc_result = extract_warehouse_entities("Where is the returns SOP documentation?")
    assert doc_result["intent_hint"] == "document_query"

    loc_result = extract_warehouse_entities("Where is SKU-4521?")
    assert loc_result["intent_hint"] == "location_query"


# ==================== 4. Full Query Execution Engine Tests ====================

def test_execute_knowledge_query_location_fastpath():
    """Test end-to-end query routing to database location."""
    res = execute_knowledge_query("Where is SKU-4521?")
    assert res["agent"] == "knowledge_agent"
    assert res["source"] == "database_location"
    assert res["data"]["found"] is True


def test_execute_knowledge_query_sop_fastpath():
    """Test end-to-end query routing to vector RAG SOP."""
    res = execute_knowledge_query("what is the pallet stacking height limit in Zone A?")
    assert res["agent"] == "knowledge_agent"
    assert res["source"] == "vector_rag"
    assert "stacking" in res["response"].lower() or "pallet" in res["response"].lower()


def test_execute_knowledge_query_returns_documentation():
    """Test query for returns documentation returns SOP citation."""
    res = execute_knowledge_query("where is the returns SOP documentation?")
    assert res["agent"] == "knowledge_agent"
    assert res["source"] == "vector_rag"
    assert "SOP" in res["response"] or "Returns" in res["response"]


# ==================== 5. Microservice Endpoint Tests ====================

def test_server_health_endpoint():
    """Test GET /health returns ready status and chunk count."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["service"] == "knowledge_agent"
    assert data["indexed_chunks"] > 0


def test_server_query_endpoint():
    """Test POST /query with valid payload."""
    resp = client.post("/query", json={"query": "safety protocol for forklift speed", "user_role": "staff"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert "Safety Protocol" in data["response"] or "speed" in data["response"].lower()


def test_server_tool_lookup_location():
    """Test POST /tools/lookup_location endpoint."""
    resp = client.post("/tools/lookup_location", json={"query_or_sku": "SKU-4521"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["result"]["found"] is True

# ==================== 6. Shift Handoff Tests ====================

def test_record_and_retrieve_shift_handoff():
    """Test recording a shift handover and retrieving the briefing."""
    rec = record_shift_handoff(
        shift_type="morning",
        supervisor="Marcus Vance",
        summary="Processed 14 freight containers at Dock Door 3.",
        incidents="Reach truck #4 had hydraulic leak at Bay 12.",
        pending_tasks="Putaway 30 pallets of electronics in Zone B."
    )
    assert rec["success"] is True
    assert rec["id"] is not None

    # Retrieve latest briefing
    briefing = get_latest_shift_handoff(shift_type="morning")
    assert briefing["found"] is True
    assert "Marcus Vance" in briefing["formatted_message"]
    assert "hydraulic leak" in briefing["formatted_message"]
    assert "Zone B" in briefing["formatted_message"]


def test_execute_knowledge_query_shift_handoff_fastpath():
    """Test natural language query routing for shift handoff."""
    # Seed a night shift handoff
    record_shift_handoff(
        shift_type="night",
        supervisor="Elena Rostova",
        summary="Night inventory audit completed.",
        incidents=None,
        pending_tasks="Recharge all reach trucks."
    )

    res = execute_knowledge_query("What happened in the night shift handoff?")
    assert res["agent"] == "knowledge_agent"
    assert res["source"] == "shift_handoff"
    assert "Elena Rostova" in res["response"]
    assert "NIGHT Shift" in res["response"] or "Night" in res["response"]


def test_server_shift_handoff_endpoints():
    """Test FastAPI REST endpoints for shift handoff."""
    # 1. POST /tools/shift_handoff/record
    payload = {
        "shift_type": "afternoon",
        "supervisor": "David K.",
        "summary": "Zone C restocking finished.",
        "incidents": "None",
        "pending_tasks": "Inspect receiving dock doors."
    }
    post_resp = client.post("/tools/shift_handoff/record", json=payload)
    assert post_resp.status_code == 200
    assert post_resp.json()["status"] == "success"

    # 2. GET /tools/shift_handoff/latest
    get_resp = client.get("/tools/shift_handoff/latest?shift_type=afternoon")
    assert get_resp.status_code == 200
    assert get_resp.json()["result"]["found"] is True
    assert "David K." in get_resp.json()["result"]["supervisor"]

    # 3. GET /tools/shift_handoff/recent
    recent_resp = client.get("/tools/shift_handoff/recent?limit=3")
    assert recent_resp.status_code == 200
    assert len(recent_resp.json()["entries"]) > 0

# ==================== 7. Compliance Checker Tests ====================

def test_compliance_stacking_limits():
    """Test evaluating pallet stacking limits and damaged pallet detection."""
    # 1. Compliant: 2 tiers in Zone A (limit is 3)
    ok_res = check_compliance(category="stacking", zone="Zone A", value=2)
    assert ok_res["compliant"] is True
    assert "COMPLIANT" in ok_res["formatted_message"]

    # 2. Non-compliant: 4 tiers in Zone A (exceeds limit of 3)
    violation_res = check_compliance(category="stacking", zone="Zone A", value=4)
    assert violation_res["compliant"] is False
    assert violation_res["severity"] == "CRITICAL"
    assert "Reduce stack height by 1" in violation_res["formatted_message"]

    # 3. Non-compliant: Damaged pallet requiring RED TAG
    damaged_res = check_compliance(category="stacking", pallet_condition="cracked")
    assert damaged_res["compliant"] is False
    assert "RED TAG" in damaged_res["formatted_message"]
    assert "Bay 9" in damaged_res["formatted_message"]


def test_compliance_speed_limits():
    """Test forklift speed checking inside warehouse aisles vs corridors."""
    # 1. Speeding in aisle: 7 mph (max is 5 mph)
    speeding_res = check_compliance(category="speed", zone="aisle", value=7.0)
    assert speeding_res["compliant"] is False
    assert "SPEED LIMIT VIOLATION" in speeding_res["formatted_message"]

    # 2. Compliant speed in aisle: 4 mph
    safe_res = check_compliance(category="speed", zone="aisle", value=4.0)
    assert safe_res["compliant"] is True


def test_compliance_battery_ppe():
    """Test battery charging PPE requirement."""
    # Missing PPE
    no_ppe = check_compliance(category="hazard", has_ppe=False)
    assert no_ppe["compliant"] is False
    assert "PPE SAFETY VIOLATION" in no_ppe["formatted_message"]

    # With PPE
    with_ppe = check_compliance(category="hazard", has_ppe=True)
    assert with_ppe["compliant"] is True


def test_execute_knowledge_query_compliance_fastpath():
    """Test natural language compliance query routing."""
    res = execute_knowledge_query("Can we stack 4 tiers of pallets in Zone A?")
    assert res["agent"] == "knowledge_agent"
    assert res["source"] == "compliance_engine"
    assert "NON-COMPLIANT" in res["response"]
    assert "SOP-STG-002" in res["response"]


def test_server_compliance_endpoint():
    """Test POST /tools/check_compliance REST endpoint."""
    resp = client.post("/tools/check_compliance", json={
        "category": "stacking",
        "zone": "Zone C",
        "value": 3
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    # Zone C max is 2 tiers, so 3 is a violation
    assert data["result"]["compliant"] is False
    assert "OVER-STACKING" in data["result"]["formatted_message"]

# ==================== 8. Returns Triage Tests ====================

def test_returns_triage_grade_a():
    """Test unopened returns get Grade A and routed to Zone B active stock."""
    res = triage_returned_item(
        rma_number="RMA-1001",
        sku="SKU-4521",
        condition="unopened",
        package_sealed=True,
        has_accessories=True
    )
    assert res["approved_for_intake"] is True
    assert res["grade"] == "Grade A"
    assert "Zone B" in res["destination"]
    assert "SOP-RET-004" in res["formatted_message"]


def test_returns_triage_grade_b():
    """Test opened box with complete accessories routes to Repackaging."""
    res = triage_returned_item(
        rma_number="RMA-1002",
        sku="SKU-1088",
        condition="opened",
        package_sealed=False,
        has_accessories=True
    )
    assert res["approved_for_intake"] is True
    assert res["grade"] == "Grade B"
    assert "Repackaging Station 4" in res["destination"]


def test_returns_triage_grade_c_quarantine():
    """Test damaged or defective return routed to Bay 11 Quarantine."""
    res = triage_returned_item(
        rma_number="RMA-1003",
        sku="SKU-4521",
        condition="water damage and broken casing",
        package_sealed=False
    )
    assert res["approved_for_intake"] is True
    assert "Grade C" in res["grade"]
    assert "Bay 11" in res["destination"]
    assert "Quarantine" in res["formatted_message"]


def test_returns_triage_missing_rma():
    """Test return without RMA is put on hold at Dock 3."""
    res = triage_returned_item(
        rma_number="",
        sku="SKU-4521",
        condition="unopened"
    )
    assert res["approved_for_intake"] is False
    assert res["grade"] == "Rejected"
    assert "Receiving Dock 3" in res["destination"]
    assert "MISSING RMA" in res["formatted_message"]


def test_execute_knowledge_query_returns_fastpath():
    """Test natural language return triage query routing."""
    res = execute_knowledge_query("Triage return RMA-7788 with water damage")
    assert res["agent"] == "knowledge_agent"
    assert res["source"] == "returns_triage"
    assert "Bay 11" in res["response"]
    assert "RMA-7788" in res["response"]


def test_server_returns_endpoint():
    """Test POST /tools/triage_return REST endpoint."""
    resp = client.post("/tools/triage_return", json={
        "rma_number": "RMA-5544",
        "sku": "SKU-4521",
        "condition": "unopened",
        "package_sealed": True,
        "has_accessories": True
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["result"]["grade"] == "Grade A"

# ==================== 9. Dynamic Upload & Category Filter Tests ====================

def test_rag_query_with_category_filter():
    """Test querying RAG with explicit category filter."""
    # Query with category='Safety'
    safety_hits = knowledge_store.query("stacking rules", n_results=2, category="Safety")
    # All returned hits must have category='Safety'
    for hit in safety_hits:
        assert hit["category"].lower() == "safety"


def test_server_upload_sop_file_endpoint():
    """Test uploading a new markdown SOP file via multipart/form-data."""
    sample_sop_md = (
        "# Cold Storage Temperature Regulations\n\n"
        "1. Temperature Threshold: All perishable dairy and produce in Zone D must be maintained "
        "at 2°C to 4°C continuously. Log temperature every 2 hours.\n\n"
        "2. Alarm Response: If chiller temp exceeds 6°C, immediately notify shift engineer "
        "and activate backup condenser unit Alpha-2."
    )

    file_bytes = io.BytesIO(sample_sop_md.encode("utf-8"))
    resp = client.post(
        "/tools/upload_sop_file",
        data={
            "doc_id": "SOP-CLD-005",
            "title": "Cold Storage Temperature Protocol",
            "category": "Storage"
        },
        files={"file": ("cold_storage_sop.md", file_bytes, "text/markdown")}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["doc_id"] == "SOP-CLD-005"

    # Verify newly uploaded SOP is now retrievable via RAG
    hits = knowledge_store.query("cold storage chiller alarm temp", n_results=1)
    assert len(hits) > 0
    assert "Cold Storage" in hits[0]["title"] or "Zone D" in hits[0]["content"]


def test_server_upload_sop_file_invalid_extension():
    """Test that uploading unsupported file types is rejected with 400."""
    file_bytes = io.BytesIO(b"dummy binary data")
    resp = client.post(
        "/tools/upload_sop_file",
        data={
            "doc_id": "SOP-INV-999",
            "title": "Bad File",
            "category": "General"
        },
        files={"file": ("manual.pdf", file_bytes, "application/pdf")}
    )
    assert resp.status_code == 400
    assert "Only .txt and .md" in resp.json()["detail"]


# ==================== 10. 3D Spatial Digital Twin Tests ====================

def test_resolve_rack_number_and_waypoints():
    """Test resolving Rack #4 returns UCID, 3D coordinates, and corridor waypoints."""
    res = resolve_location("where is rack no 4 located?")
    assert res["found"] is True
    assert res["target_type"] == "rack"
    assert res["ucid"] == "WH-01:FL-01:ZN-A:AISLE-02:BAY-04"
    assert res["floor"] == 1

    assert "coordinates" in res
    assert len(res["waypoints"]) >= 2
    assert "Rack #4" in res["formatted_message"]


def test_resolve_forklift_fleet():
    """Test query 'where are the forklifts' returns all active static pins."""
    res = resolve_location("where are the forklifts stationed?")
    assert res["found"] is True
    assert res["target_type"] == "equipment_fleet"
    assert len(res["all_pins"]) >= 4
    assert any(eq["id"] == "EQ-FL-01" for eq in res["all_pins"])


def test_resolve_special_zone_bay_11():
    """Test query 'where is bay 11' resolves quarantine staging."""
    res = resolve_location("where is bay 11?")
    assert res["found"] is True
    assert res["target_type"] == "special_zone"
    assert "Quarantine" in res["name"]
    assert len(res["waypoints"]) >= 2


def test_server_spatial_layout_endpoint():
    """Test GET /tools/spatial_layout returns full 3D layout for the map viewer."""
    resp = client.get("/tools/spatial_layout")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    layout = data["layout"]
    assert "racks" in layout and len(layout["racks"]) >= 15
    assert "equipment" in layout and len(layout["equipment"]) >= 4
    assert "origin_points" in layout and len(layout["origin_points"]) >= 3

