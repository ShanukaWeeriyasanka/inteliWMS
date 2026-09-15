import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session

from agents.fulfillment.schemas import FulfillmentRequest, FulfillmentResponse, FulfillmentIntent, FulfillmentIntentResult
from agents.fulfillment.fulfillment_agent import FulfillmentAgent
import asyncio

@pytest.fixture
def mock_db():
    return MagicMock(spec=Session)

@pytest.fixture
def mock_classifier():
    classifier = MagicMock()
    return classifier

@pytest.fixture
def fulfillment_agent(mock_classifier):
    return FulfillmentAgent(classifier=mock_classifier)

class MockOrder:
    def __init__(self, id, order_id, customer_name, sku, quantity, status, created_at):
        self.id = id
        self.order_id = order_id
        self.customer_name = customer_name
        self.sku = sku
        self.quantity = quantity
        self.status = status
        self.created_at = created_at

def test_missing_order_id(fulfillment_agent, mock_db):
    fulfillment_agent.classifier.classify.return_value = FulfillmentIntentResult(intent=FulfillmentIntent.ORDER_STATUS, confidence=0.9)
    req = FulfillmentRequest(query="What is the status of my order?")
    
    resp = asyncio.run(fulfillment_agent.handle(req, mock_db))
    
    assert resp.success is False
    assert resp.order_id is None
    assert resp.intent == FulfillmentIntent.ORDER_STATUS
    assert "Please provide a valid order ID" in resp.message

@patch('agents.fulfillment.fulfillment_agent.get_order_by_id')
def test_unknown_intent(mock_get_order, fulfillment_agent, mock_db):
    fulfillment_agent.classifier.classify.return_value = FulfillmentIntentResult(intent=FulfillmentIntent.UNKNOWN_FULFILLMENT, confidence=0.0)
    req = FulfillmentRequest(query="Some weird stuff for ORD-1001")
    
    resp = asyncio.run(fulfillment_agent.handle(req, mock_db))
    
    assert resp.success is False
    assert resp.order_id == "ORD-1001"
    assert "could not confidently determine" in resp.message
    mock_get_order.assert_not_called()

@patch('agents.fulfillment.fulfillment_agent.get_order_by_id')
def test_order_not_found(mock_get_order, fulfillment_agent, mock_db):
    fulfillment_agent.classifier.classify.return_value = FulfillmentIntentResult(intent=FulfillmentIntent.ORDER_STATUS, confidence=0.9)
    mock_get_order.return_value = None
    req = FulfillmentRequest(query="Status of ORD-9999?")
    
    resp = asyncio.run(fulfillment_agent.handle(req, mock_db))
    
    assert resp.success is False
    assert resp.order_id == "ORD-9999"
    assert "not found" in resp.message

@patch('agents.fulfillment.fulfillment_agent.get_order_by_id')
def test_order_status_success(mock_get_order, fulfillment_agent, mock_db):
    fulfillment_agent.classifier.classify.return_value = FulfillmentIntentResult(intent=FulfillmentIntent.ORDER_STATUS, confidence=0.9)
    mock_get_order.return_value = MockOrder(1, "ORD-1001", "John", "SKU1", 5, "pending", "2026-01-01")
    req = FulfillmentRequest(query="Status of ORD-1001?")
    
    resp = asyncio.run(fulfillment_agent.handle(req, mock_db))
    
    assert resp.success is True
    assert resp.order_id == "ORD-1001"
    assert "currently pending" in resp.message

@patch('agents.fulfillment.fulfillment_agent.get_order_by_id')
def test_order_delay_delayed(mock_get_order, fulfillment_agent, mock_db):
    fulfillment_agent.classifier.classify.return_value = FulfillmentIntentResult(intent=FulfillmentIntent.ORDER_DELAY, confidence=0.9)
    mock_get_order.return_value = MockOrder(1, "ORD-1001", "John", "SKU1", 5, "delayed", "2026-01-01")
    req = FulfillmentRequest(query="Why is ORD-1001 delayed?")
    
    resp = asyncio.run(fulfillment_agent.handle(req, mock_db))
    
    assert resp.success is True
    assert "specific delay reason is not available" in resp.message

@patch('agents.fulfillment.fulfillment_agent.get_order_by_id')
def test_order_delay_not_delayed(mock_get_order, fulfillment_agent, mock_db):
    fulfillment_agent.classifier.classify.return_value = FulfillmentIntentResult(intent=FulfillmentIntent.ORDER_DELAY, confidence=0.9)
    mock_get_order.return_value = MockOrder(1, "ORD-1002", "John", "SKU1", 5, "pending", "2026-01-01")
    req = FulfillmentRequest(query="Why is ORD-1002 delayed?")
    
    resp = asyncio.run(fulfillment_agent.handle(req, mock_db))
    
    assert resp.success is True
    assert "is not marked as delayed" in resp.message

@patch('agents.fulfillment.fulfillment_agent.get_order_by_id')
def test_order_details(mock_get_order, fulfillment_agent, mock_db):
    fulfillment_agent.classifier.classify.return_value = FulfillmentIntentResult(intent=FulfillmentIntent.ORDER_DETAILS, confidence=0.9)
    mock_get_order.return_value = MockOrder(1, "ORD-1001", "John Doe", "SKU-999", 5, "pending", "2026-01-01")
    req = FulfillmentRequest(query="Details for ORD-1001")
    
    resp = asyncio.run(fulfillment_agent.handle(req, mock_db))
    
    assert resp.success is True
    assert "John Doe" in resp.message
    assert "SKU-999" in resp.message
    assert "5" in resp.message

@patch('agents.fulfillment.fulfillment_agent.get_order_by_id')
def test_shipping_status_shipped(mock_get_order, fulfillment_agent, mock_db):
    fulfillment_agent.classifier.classify.return_value = FulfillmentIntentResult(intent=FulfillmentIntent.SHIPPING_STATUS, confidence=0.9)
    mock_get_order.return_value = MockOrder(1, "ORD-1001", "John Doe", "SKU-999", 5, "shipped", "2026-01-01")
    req = FulfillmentRequest(query="Has ORD-1001 shipped?")
    
    resp = asyncio.run(fulfillment_agent.handle(req, mock_db))
    
    assert resp.success is True
    assert "marked as shipped" in resp.message

@patch('agents.fulfillment.fulfillment_agent.get_order_by_id')
def test_shipping_status_not_shipped(mock_get_order, fulfillment_agent, mock_db):
    fulfillment_agent.classifier.classify.return_value = FulfillmentIntentResult(intent=FulfillmentIntent.SHIPPING_STATUS, confidence=0.9)
    mock_get_order.return_value = MockOrder(1, "ORD-1001", "John Doe", "SKU-999", 5, "pending", "2026-01-01")
    req = FulfillmentRequest(query="Has ORD-1001 shipped?")
    
    resp = asyncio.run(fulfillment_agent.handle(req, mock_db))
    
    assert resp.success is True
    assert "not marked as shipped" in resp.message

@patch('agents.fulfillment.fulfillment_agent.get_order_by_id')
def test_fulfillment_progress(mock_get_order, fulfillment_agent, mock_db):
    fulfillment_agent.classifier.classify.return_value = FulfillmentIntentResult(intent=FulfillmentIntent.FULFILLMENT_PROGRESS, confidence=0.9)
    mock_get_order.return_value = MockOrder(1, "ORD-1001", "John Doe", "SKU-999", 5, "pending", "2026-01-01")
    req = FulfillmentRequest(query="Progress for ORD-1001")
    
    resp = asyncio.run(fulfillment_agent.handle(req, mock_db))
    
    assert resp.success is True
    assert "Detailed picking, packing, and dispatch progress is not available" in resp.message

@patch('agents.fulfillment.fulfillment_agent.get_order_by_id')
def test_request_order_id_override(mock_get_order, fulfillment_agent, mock_db):
    fulfillment_agent.classifier.classify.return_value = FulfillmentIntentResult(intent=FulfillmentIntent.ORDER_STATUS, confidence=0.9)
    mock_get_order.return_value = MockOrder(1, "ORD-5555", "John Doe", "SKU-999", 5, "pending", "2026-01-01")
    # Even if query says ORD-1001, request.order_id takes precedence
    req = FulfillmentRequest(query="Status of ORD-1001", order_id="ORD-5555")
    
    resp = asyncio.run(fulfillment_agent.handle(req, mock_db))
    
    assert resp.order_id == "ORD-5555"
    assert "ORD-5555 is currently pending" in resp.message

def test_exception_fallback(fulfillment_agent, mock_db):
    fulfillment_agent.classifier.classify.side_effect = Exception("System crash")
    req = FulfillmentRequest(query="Status of ORD-1001")
    
    resp = asyncio.run(fulfillment_agent.handle(req, mock_db))
    
    assert resp.success is False
    assert "Unable to process" in resp.message
