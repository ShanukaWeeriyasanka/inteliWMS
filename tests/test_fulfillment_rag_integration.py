"""
Integration and End-to-End Tests for Phase 2: Fulfillment Agent Knowledge Base & RAG Integration.

Covers:
1. Packing procedure without order ID.
2. Delay-handling procedure without order ID.
3. Dispatch procedure without order ID.
4. Normal order status without unnecessary SOP content.
5. Combined delay investigation and SOP guidance.
6. Invalid order ID handling.
7. Missing order record handling.
8. Missing relevant SOP handling.
9. ChromaDB failure handling.
10. Correct SOP citations structure.
11. Demonstration disclaimer visibility.
12. Professional independent retrieval.
13. Professional cross-agent collaboration restriction.
14. Enterprise Inventory collaboration.
15. Starter Fulfillment denial.
16. General Knowledge Agent routing remains unchanged (e.g. SOP-RET-004).
17. Fulfillment-specific procedural routing (e.g. packing procedure).
18. Backward compatibility of existing response fields.
"""
import pytest
import asyncio
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
import jwt
import time

from backend.main import app
from config.settings import settings
from agents.fulfillment.schemas import (
    FulfillmentRequest,
    FulfillmentResponse,
    FulfillmentIntent,
    FulfillmentIntentResult,
    SOPSourceCitation
)
from agents.fulfillment.fulfillment_agent import FulfillmentAgent
from agents.fulfillment.knowledge_store import FulfillmentKnowledgeStore
from agents.coordinator.intent_classifier import IntentClassifier

client = TestClient(app)
TEST_SECRET = settings.JWT_SECRET


from security.subscription import set_user_plan, PLAN_STARTER, PLAN_PROFESSIONAL, PLAN_ENTERPRISE

def create_test_token(role="staff", plan="enterprise", user_id="user_admin", username="admin_user"):
    set_user_plan(username, plan)
    payload = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "plan": plan,
        "exp": int(time.time()) + 3600
    }
    return jwt.encode(payload, TEST_SECRET, algorithm="HS256")



class DummyOrder:
    def __init__(self, order_id="ORD-1001", status="pending", sku="SKU-100", delay_reason=None, carrier_name=None, revised_delivery_date=None):
        self.id = 1
        self.order_id = order_id
        self.customer_name = "Acme Corp"
        self.sku = sku
        self.quantity = 10
        self.status = status
        self.delay_reason = delay_reason
        self.carrier_name = carrier_name
        self.revised_delivery_date = revised_delivery_date
        self.created_at = "2026-03-01 10:00:00"


# ==================== 1. Fulfillment Agent Procedural Retrieval Tests ====================

def test_packing_procedure_without_order_id():
    """1. Packing procedure without order ID returns SOP-FLF-001 citations and guidance."""
    agent = FulfillmentAgent()
    mock_db = MagicMock(spec=Session)
    req = FulfillmentRequest(query="What is the packing procedure?")
    
    resp = asyncio.run(agent.handle(req, mock_db))
    
    assert resp.success is True
    assert resp.order_id is None
    assert resp.intent == FulfillmentIntent.FULFILLMENT_PROCEDURE
    assert resp.procedural_guidance is not None
    assert len(resp.citations) > 0
    assert resp.citations[0].sop_id == "SOP-FLF-001"
    assert "SOP-FLF-001" in resp.message
    assert "demonstration" in resp.message.lower() or "approval" in resp.message.lower()


def test_delay_handling_procedure_without_order_id():
    """2. Delay-handling procedure without order ID returns SOP-FLF-002 citations."""
    agent = FulfillmentAgent()
    mock_db = MagicMock(spec=Session)
    req = FulfillmentRequest(query="What should I do when an order is delayed?")
    
    resp = asyncio.run(agent.handle(req, mock_db))
    
    assert resp.success is True
    assert resp.order_id is None
    assert resp.intent == FulfillmentIntent.FULFILLMENT_PROCEDURE
    assert len(resp.citations) > 0
    assert resp.citations[0].sop_id == "SOP-FLF-002"
    assert "Order Delay Investigation" in resp.citations[0].title


def test_dispatch_procedure_without_order_id():
    """3. Dispatch procedure without order ID returns SOP-FLF-003 citations."""
    agent = FulfillmentAgent()
    mock_db = MagicMock(spec=Session)
    req = FulfillmentRequest(query="What are the dispatch verification steps?")
    
    resp = asyncio.run(agent.handle(req, mock_db))
    
    assert resp.success is True
    assert resp.order_id is None
    assert resp.intent == FulfillmentIntent.FULFILLMENT_PROCEDURE
    assert len(resp.citations) > 0
    assert resp.citations[0].sop_id == "SOP-FLF-003"


# ==================== 2. Order Functionality & Combined Queries ====================

@patch('agents.fulfillment.fulfillment_agent.get_order_by_id')
def test_normal_order_status_no_sop_content(mock_get_order):
    """4. Normal order status returns database facts without unnecessary SOP content."""
    mock_get_order.return_value = DummyOrder(order_id="ORD-1001", status="shipped")
    agent = FulfillmentAgent()
    mock_db = MagicMock(spec=Session)
    req = FulfillmentRequest(query="What is the status of ORD-1001?", order_id="ORD-1001")
    
    resp = asyncio.run(agent.handle(req, mock_db))
    
    assert resp.success is True
    assert resp.order_id == "ORD-1001"
    assert resp.intent == FulfillmentIntent.ORDER_STATUS
    assert "Order ORD-1001 is currently shipped." in resp.message
    assert resp.procedural_guidance is None
    assert len(resp.citations) == 0
    assert resp.information_reliability == "confirmed_facts"


@patch('agents.fulfillment.fulfillment_agent.get_order_by_id')
def test_combined_delay_investigation_and_sop(mock_get_order):
    """5. Combined delay investigation and SOP guidance returns both DB facts and SOP."""
    mock_get_order.return_value = DummyOrder(
        order_id="ORD-1004",
        status="delayed",
        delay_reason="Carrier severe weather delay in transit hub",
        carrier_name="FedEx Ground"
    )
    agent = FulfillmentAgent()
    mock_db = MagicMock(spec=Session)
    req = FulfillmentRequest(
        query="Why is ORD-1004 delayed, and what should I do next?",
        order_id="ORD-1004"
    )
    
    resp = asyncio.run(agent.handle(req, mock_db))
    
    assert resp.success is True
    assert resp.order_id == "ORD-1004"
    assert "Carrier severe weather delay" in resp.message
    assert "Recommended Next Steps" in resp.message
    assert resp.procedural_guidance is not None
    assert len(resp.citations) > 0
    assert resp.citations[0].sop_id == "SOP-FLF-002"
    assert resp.information_reliability == "combined"


def test_invalid_order_id_non_procedural():
    """6. Invalid / missing order ID on non-procedural question prompts user."""
    agent = FulfillmentAgent()
    mock_db = MagicMock(spec=Session)
    req = FulfillmentRequest(query="What is the status of the order?")
    
    resp = asyncio.run(agent.handle(req, mock_db))
    
    assert resp.success is False
    assert resp.order_id is None
    assert "Please provide a valid order ID" in resp.message


@patch('agents.fulfillment.fulfillment_agent.get_order_by_id')
def test_missing_order_record(mock_get_order):
    """7. Order not found in database returns safe missing message."""
    mock_get_order.return_value = None
    agent = FulfillmentAgent()
    mock_db = MagicMock(spec=Session)
    req = FulfillmentRequest(query="Status of ORD-9999?", order_id="ORD-9999")
    
    resp = asyncio.run(agent.handle(req, mock_db))
    
    assert resp.success is False
    assert "Order ORD-9999 was not found" in resp.message


def test_missing_relevant_sop():
    """8. Querying unknown procedure returns clear message without inventing SOPs."""
    agent = FulfillmentAgent()
    mock_db = MagicMock(spec=Session)
    agent.classifier = MagicMock()
    agent.classifier.classify.return_value = FulfillmentIntentResult(
        intent=FulfillmentIntent.FULFILLMENT_PROCEDURE,
        confidence=0.95
    )
    req = FulfillmentRequest(query="Explain the procedural protocol for baking cakes on the dock.")
    
    resp = asyncio.run(agent.handle(req, mock_db))
    
    assert resp.success is True
    assert resp.intent == FulfillmentIntent.FULFILLMENT_PROCEDURE
    assert "No matching documented fulfillment procedure was found" in resp.message
    assert len(resp.citations) == 0


def test_chromadb_failure_handling(tmp_path):
    """9. ChromaDB failure falls back to keyword matching without crashing."""
    mock_store = FulfillmentKnowledgeStore(
        persist_dir=tmp_path / "failing_chroma",
        collection_name="fail_coll"
    )
    mock_store._collection = None
    mock_store._client = None
    mock_store.add_sop_document({
        "sop_id": "SOP-FLF-001",
        "title": "Order Picking and Packing Procedure",
        "category": "Picking & Packing",
        "version": "1.0-DEMO",
        "status": "demonstration",
        "sections": [
            {"section_id": "SEC-1.5", "heading": "Packing Guidelines", "content": "Seal cartons using H-taping method."}
        ]
    })
    
    agent = FulfillmentAgent(knowledge_store=mock_store)
    mock_db = MagicMock(spec=Session)
    req = FulfillmentRequest(query="What is the packing procedure?")
    
    resp = asyncio.run(agent.handle(req, mock_db))
    
    assert resp.success is True
    assert "H-taping method" in resp.message
    assert len(resp.citations) > 0
    assert resp.citations[0].sop_id == "SOP-FLF-001"


# ==================== 3. Citations and Disclaimers ====================

def test_sop_citations_structure_and_disclaimer():
    """10 & 11. Citations contain complete schema keys and clear demonstration disclaimer."""
    agent = FulfillmentAgent()
    mock_db = MagicMock(spec=Session)
    req = FulfillmentRequest(query="What checks are required before dispatch?")
    
    resp = asyncio.run(agent.handle(req, mock_db))
    
    assert len(resp.citations) > 0
    cit = resp.citations[0]
    assert cit.sop_id == "SOP-FLF-003"
    assert cit.title == "Shipping and Dispatch Verification Checklist"
    assert cit.section_id.startswith("SEC-")
    assert cit.version == "1.0-DEMO"
    assert cit.status == "demonstration"
    assert "⚠️ Note:" in resp.message
    assert "approval" in resp.message.lower()


# ==================== 4. Subscription & Security Boundary Tests ====================

@patch('agents.fulfillment.fulfillment_agent.get_order_by_id')
def test_starter_fulfillment_denial(mock_get_order):
    """15. Starter tier user is blocked from Fulfillment Agent access."""
    token = create_test_token(role="staff", plan="starter", user_id="user_john", username="john_staff")
    response = client.post(
        "/query",
        json={"token": token, "message": "What is the packing procedure?"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "restricted"
    assert data["error_code"] == "PLAN_RESTRICTED"
    assert data["plan"] == "starter"


@patch('agents.fulfillment.fulfillment_agent.get_order_by_id')
def test_professional_independent_retrieval(mock_get_order):
    """12. Professional user selecting fulfillment_agent can query fulfillment SOPs independently."""
    token = create_test_token(role="staff", plan="professional", user_id="user_sarah", username="sarah_manager")
    response = client.post(
        "/query",
        json={
            "token": token,
            "message": "What is the packing procedure?",
            "selected_agent": "fulfillment_agent"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["agent_used"] == "fulfillment_agent"
    assert "SOP-FLF-001" in data["response"]
    assert "fulfillment_details" in data
    assert len(data["fulfillment_details"]["citations"]) > 0


@patch('agents.fulfillment.fulfillment_agent.get_order_by_id')
def test_professional_cross_agent_collaboration_blocked(mock_get_order):
    """13. Professional user investigating delay without delay reason cannot cross-call Inventory."""
    mock_get_order.return_value = DummyOrder(
        order_id="ORD-1002",
        status="delayed",
        sku="SKU-200",
        delay_reason=None
    )
    token = create_test_token(role="staff", plan="professional", user_id="user_sarah", username="sarah_manager")
    response = client.post(
        "/query",
        json={
            "token": token,
            "message": "Why is ORD-1002 delayed?",
            "selected_agent": "fulfillment_agent"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "Enterprise subscription" in data["response"] or "specific delay reason is not available" in data["response"]


@patch('agents.fulfillment.fulfillment_agent.get_order_by_id')
@patch('agents.coordinator.agent_dispatcher._dispatch_inventory')
def test_enterprise_inventory_collaboration_allowed(mock_dispatch_inv, mock_get_order):
    """14. Enterprise tier user allows Fulfillment to collaborate with Inventory on stock check."""
    mock_get_order.return_value = DummyOrder(
        order_id="ORD-1003",
        status="delayed",
        sku="SKU-300",
        delay_reason=None
    )
    mock_dispatch_inv.return_value = {
        "status": "success",
        "response": "SKU-300 is currently out of stock.",
        "inventory_details": {"items": [{"sku": "SKU-300", "quantity_on_hand": 0}]}
    }
    token = create_test_token(role="staff", plan="enterprise", user_id="user_admin", username="admin_user")
    response = client.post(
        "/query",
        json={
            "token": token,
            "message": "Why is ORD-1003 delayed?"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "out of stock" in data["response"].lower()


# ==================== 5. Routing Discrimination Tests ====================

def test_general_knowledge_agent_routing_preserved():
    """16. General warehouse SOP query (SOP-RET-004) routes to Knowledge Agent."""
    classifier = IntentClassifier()
    result = classifier.classify("What does SOP-RET-004 explain about customer returns?")
    assert result.domain == "KNOWLEDGE"


def test_fulfillment_procedural_routing():
    """17. Fulfillment procedural query routes to Fulfillment Agent."""
    classifier = IntentClassifier()
    
    q1 = classifier.classify("What is the packing procedure?")
    assert q1.domain == "FULFILLMENT"
    
    q2 = classifier.classify("What should I do when an order is delayed?")
    assert q2.domain == "FULFILLMENT"
    
    q3 = classifier.classify("What are the dispatch verification steps?")
    assert q3.domain == "FULFILLMENT"


# ==================== 6. Backward Compatibility Test ====================

@patch('agents.fulfillment.fulfillment_agent.get_order_by_id')
def test_backward_compatibility_response_fields(mock_get_order):
    """18. Existing keys (status, agent_used, fulfillment_details: success, intent, order_id) are intact."""
    mock_get_order.return_value = DummyOrder(order_id="ORD-1005", status="shipped")
    token = create_test_token(role="staff", plan="enterprise", user_id="user_admin", username="admin_user")
    response = client.post(
        "/query",
        json={"token": token, "message": "Status of ORD-1005"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "agent_used" in data
    assert "response" in data
    assert "fulfillment_details" in data
    f_det = data["fulfillment_details"]
    assert "success" in f_det
    assert "intent" in f_det
    assert "order_id" in f_det
    assert f_det["order_id"] == "ORD-1005"


# ==================== 7. Regression Tests for Reported Failures ====================

def test_regression_failure_1_packing_procedure_routes_to_fulfillment():
    """Regression Failure 1: 'What is the packing procedure?' routes to Fulfillment, not Knowledge."""
    token = create_test_token(role="manager", plan="enterprise", user_id="user_admin", username="admin_user")
    response = client.post(
        "/query",
        json={"token": token, "message": "What is the packing procedure?"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["agent_used"] == "fulfillment_agent", f"Expected fulfillment_agent, got {data.get('agent_used')}"
    assert "fulfillment_details" in data
    f_det = data["fulfillment_details"]
    assert f_det["success"] is True
    assert f_det["order_id"] is None
    assert f_det["procedural_guidance"] is not None
    assert len(f_det["citations"]) > 0
    assert any(c["sop_id"] == "SOP-FLF-001" for c in f_det["citations"])
    assert "SOP-FLF-001" in data["response"]


@patch('agents.fulfillment.fulfillment_agent.get_order_by_id')
def test_regression_failure_2_combined_order_delayed_and_next_steps(mock_get_order):
    """Regression Failure 2: 'Why is ORD-1001 delayed, and what should I do next?' returns delay facts + SOP-FLF-002 next steps."""
    mock_get_order.return_value = DummyOrder(
        order_id="ORD-1001",
        status="delayed",
        delay_reason="Carrier dispatch backlog at customs checkpoint",
        carrier_name="DHL Express",
        revised_delivery_date="2026-10-01"
    )
    token = create_test_token(role="manager", plan="enterprise", user_id="user_admin", username="admin_user")
    response = client.post(
        "/query",
        json={"token": token, "message": "Why is ORD-1001 delayed, and what should I do next?"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["agent_used"] == "fulfillment_agent"
    assert "fulfillment_details" in data
    f_det = data["fulfillment_details"]
    assert f_det["success"] is True
    assert f_det["order_id"] == "ORD-1001"
    # Grounded delay facts
    assert "ORD-1001" in data["response"]
    assert "delayed" in data["response"].lower()
    # Recommended Next Steps grounded in SOP-FLF-002
    assert "Recommended Next Steps" in data["response"]
    assert f_det["procedural_guidance"] is not None
    assert len(f_det["citations"]) > 0
    assert any(c["sop_id"] == "SOP-FLF-002" for c in f_det["citations"])


def test_regression_pallet_stacking_and_forklift_route_to_knowledge():
    """General warehouse safety queries route to Knowledge Agent, not Fulfillment."""
    classifier = IntentClassifier()
    r1 = classifier.classify("Explain the forklift safety SOP.")
    assert r1.domain == "KNOWLEDGE"
    
    r2 = classifier.classify("Explain pallet stacking regulations.")
    assert r2.domain == "KNOWLEDGE"
