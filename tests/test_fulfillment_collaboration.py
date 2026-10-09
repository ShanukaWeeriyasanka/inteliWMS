import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from sqlalchemy.orm import Session

from agents.fulfillment.schemas import FulfillmentRequest, FulfillmentResponse, FulfillmentIntent, FulfillmentIntentResult
from agents.fulfillment.fulfillment_agent import FulfillmentAgent

@pytest.fixture
def mock_db():
    return MagicMock(spec=Session)

@pytest.fixture
def mock_classifier():
    classifier = MagicMock()
    return classifier

@pytest.fixture
def mock_dispatcher():
    return AsyncMock()

@pytest.fixture
def fulfillment_agent(mock_classifier, mock_dispatcher):
    return FulfillmentAgent(classifier=mock_classifier, dispatcher=mock_dispatcher)

class MockOrder:
    def __init__(self, id, order_id, customer_name, sku, quantity, status, created_at):
        self.id = id
        self.order_id = order_id
        self.customer_name = customer_name
        self.sku = sku
        self.quantity = quantity
        self.status = status
        self.created_at = created_at

@pytest.mark.parametrize("details", [None, {"items": [{"sku": "SKU-4521"}]}])
@patch('agents.fulfillment.fulfillment_agent.get_order_by_id')
def test_missing_inventory_quantity_preserves_text_fallback(mock_get_order, fulfillment_agent, mock_db, details):
    fulfillment_agent.classifier.classify.return_value = FulfillmentIntentResult(intent=FulfillmentIntent.ORDER_DELAY, confidence=0.9)
    mock_get_order.return_value = MockOrder(1, "ORD-1001", "John", "SKU-4521", 5, "delayed", "2026-01-01")
    fulfillment_agent.dispatcher.return_value = {"response": "42 units available; 0 reserved", "inventory_details": details}
    resp = asyncio.run(fulfillment_agent.handle(FulfillmentRequest(query="Why delayed?", order_id="ORD-1001"), mock_db))
    assert "currently has stock available" in resp.message

@patch('agents.fulfillment.fulfillment_agent.get_order_by_id')
def test_structured_inventory_matches_order_sku(mock_get_order, fulfillment_agent, mock_db):
    fulfillment_agent.classifier.classify.return_value = FulfillmentIntentResult(intent=FulfillmentIntent.ORDER_DELAY, confidence=0.9)
    mock_get_order.return_value = MockOrder(1, "ORD-1001", "John", "SKU-4521", 5, "delayed", "2026-01-01")
    fulfillment_agent.dispatcher.return_value = {"response": "Stock: 0", "inventory_details": {"items": [
        {"sku": "OTHER", "quantity_on_hand": 0}, {"sku": "SKU-4521", "quantity_on_hand": 42}]}}
    resp = asyncio.run(fulfillment_agent.handle(FulfillmentRequest(query="Why delayed?", order_id="ORD-1001"), mock_db))
    assert "currently has stock available" in resp.message

@patch('agents.fulfillment.fulfillment_agent.get_order_by_id')
def test_recorded_delay_reason_skips_inventory(mock_get_order, fulfillment_agent, mock_db):
    from datetime import datetime, timezone
    fulfillment_agent.classifier.classify.return_value = FulfillmentIntentResult(intent=FulfillmentIntent.ORDER_DELAY, confidence=0.9)
    order = MockOrder(1, "ORD-1001", "John", "SKU-4521", 5, "delayed", "2026-01-01")
    order.delay_reason = "Customs backlog"
    order.carrier_name = "DHL"
    order.revised_delivery_date = datetime(2026, 10, 12, tzinfo=timezone.utc)
    mock_get_order.return_value = order
    resp = asyncio.run(fulfillment_agent.handle(FulfillmentRequest(query="Why delayed?", order_id="ORD-1001"), mock_db))
    assert "Reason: Customs backlog" in resp.message
    assert "Carrier: DHL" in resp.message
    assert "2026-10-12" in resp.message
    fulfillment_agent.dispatcher.assert_not_called()

@patch('agents.fulfillment.fulfillment_agent.get_order_by_id')
def test_delayed_order_out_of_stock(mock_get_order, fulfillment_agent, mock_db):
    fulfillment_agent.classifier.classify.return_value = FulfillmentIntentResult(intent=FulfillmentIntent.ORDER_DELAY, confidence=0.9)
    mock_get_order.return_value = MockOrder(1, "ORD-1001", "John", "SKU-4521", 5, "delayed", "2026-01-01")
    fulfillment_agent.dispatcher.return_value = {"response": "SKU-4521 is out of stock"}
    
    req = FulfillmentRequest(query="Why is ORD-1001 delayed?", order_id="ORD-1001")
    resp = asyncio.run(fulfillment_agent.handle(req, mock_db))
    
    fulfillment_agent.dispatcher.assert_called_once()
    assert "currently out of stock" in resp.message
    assert "may be contributing to the delay" in resp.message
    assert "does not contain a specific delay reason" in resp.message

@patch('agents.fulfillment.fulfillment_agent.get_order_by_id')
def test_delayed_order_inventory_available(mock_get_order, fulfillment_agent, mock_db):
    fulfillment_agent.classifier.classify.return_value = FulfillmentIntentResult(intent=FulfillmentIntent.ORDER_DELAY, confidence=0.9)
    mock_get_order.return_value = MockOrder(1, "ORD-1001", "John", "SKU-4521", 5, "delayed", "2026-01-01")
    fulfillment_agent.dispatcher.return_value = {"response": "SKU-4521 has 42 units available"}
    
    req = FulfillmentRequest(query="Why is ORD-1001 delayed?", order_id="ORD-1001")
    resp = asyncio.run(fulfillment_agent.handle(req, mock_db))
    
    fulfillment_agent.dispatcher.assert_called_once()
    assert "currently has stock available" in resp.message
    assert "does not by itself explain the delay" in resp.message

@patch('agents.fulfillment.fulfillment_agent.get_order_by_id')
def test_delayed_order_sku_missing(mock_get_order, fulfillment_agent, mock_db):
    fulfillment_agent.classifier.classify.return_value = FulfillmentIntentResult(intent=FulfillmentIntent.ORDER_DELAY, confidence=0.9)
    # sku is None
    mock_get_order.return_value = MockOrder(1, "ORD-1001", "John", None, 5, "delayed", "2026-01-01")
    
    req = FulfillmentRequest(query="Why is ORD-1001 delayed?", order_id="ORD-1001")
    resp = asyncio.run(fulfillment_agent.handle(req, mock_db))
    
    fulfillment_agent.dispatcher.assert_not_called()
    assert "is currently delayed" in resp.message
    assert "A specific delay reason is not available" in resp.message

@patch('agents.fulfillment.fulfillment_agent.get_order_by_id')
def test_inventory_agent_exception(mock_get_order, fulfillment_agent, mock_db):
    fulfillment_agent.classifier.classify.return_value = FulfillmentIntentResult(intent=FulfillmentIntent.ORDER_DELAY, confidence=0.9)
    mock_get_order.return_value = MockOrder(1, "ORD-1001", "John", "SKU-4521", 5, "delayed", "2026-01-01")
    fulfillment_agent.dispatcher.side_effect = Exception("Inventory agent down")
    
    req = FulfillmentRequest(query="Why is ORD-1001 delayed?", order_id="ORD-1001")
    resp = asyncio.run(fulfillment_agent.handle(req, mock_db))
    
    fulfillment_agent.dispatcher.assert_called_once()
    assert "is currently delayed" in resp.message
    assert "A specific delay reason is not available" in resp.message

@patch('agents.fulfillment.fulfillment_agent.get_order_by_id')
def test_inventory_response_malformed(mock_get_order, fulfillment_agent, mock_db):
    fulfillment_agent.classifier.classify.return_value = FulfillmentIntentResult(intent=FulfillmentIntent.ORDER_DELAY, confidence=0.9)
    mock_get_order.return_value = MockOrder(1, "ORD-1001", "John", "SKU-4521", 5, "delayed", "2026-01-01")
    # Missing 'response' key or no keywords triggered
    fulfillment_agent.dispatcher.return_value = {"weird_key": "weird_value"}
    
    req = FulfillmentRequest(query="Why is ORD-1001 delayed?", order_id="ORD-1001")
    resp = asyncio.run(fulfillment_agent.handle(req, mock_db))
    
    fulfillment_agent.dispatcher.assert_called_once()
    assert "A specific delay reason is not available" in resp.message

@patch('agents.fulfillment.fulfillment_agent.get_order_by_id')
def test_order_status_does_not_call_inventory(mock_get_order, fulfillment_agent, mock_db):
    fulfillment_agent.classifier.classify.return_value = FulfillmentIntentResult(intent=FulfillmentIntent.ORDER_STATUS, confidence=0.9)
    mock_get_order.return_value = MockOrder(1, "ORD-1001", "John", "SKU-4521", 5, "delayed", "2026-01-01")
    
    req = FulfillmentRequest(query="Status of ORD-1001", order_id="ORD-1001")
    resp = asyncio.run(fulfillment_agent.handle(req, mock_db))
    
    fulfillment_agent.dispatcher.assert_not_called()

@patch('agents.fulfillment.fulfillment_agent.get_order_by_id')
def test_order_details_does_not_call_inventory(mock_get_order, fulfillment_agent, mock_db):
    fulfillment_agent.classifier.classify.return_value = FulfillmentIntentResult(intent=FulfillmentIntent.ORDER_DETAILS, confidence=0.9)
    mock_get_order.return_value = MockOrder(1, "ORD-1001", "John", "SKU-4521", 5, "delayed", "2026-01-01")
    
    req = FulfillmentRequest(query="Details of ORD-1001", order_id="ORD-1001")
    resp = asyncio.run(fulfillment_agent.handle(req, mock_db))
    
    fulfillment_agent.dispatcher.assert_not_called()

@patch('agents.fulfillment.fulfillment_agent.get_order_by_id')
def test_shipping_status_does_not_call_inventory(mock_get_order, fulfillment_agent, mock_db):
    fulfillment_agent.classifier.classify.return_value = FulfillmentIntentResult(intent=FulfillmentIntent.SHIPPING_STATUS, confidence=0.9)
    mock_get_order.return_value = MockOrder(1, "ORD-1001", "John", "SKU-4521", 5, "delayed", "2026-01-01")
    
    req = FulfillmentRequest(query="Has ORD-1001 shipped?", order_id="ORD-1001")
    resp = asyncio.run(fulfillment_agent.handle(req, mock_db))
    
    fulfillment_agent.dispatcher.assert_not_called()

@patch('agents.fulfillment.fulfillment_agent.get_order_by_id')
def test_non_delayed_order_delay_request(mock_get_order, fulfillment_agent, mock_db):
    fulfillment_agent.classifier.classify.return_value = FulfillmentIntentResult(intent=FulfillmentIntent.ORDER_DELAY, confidence=0.9)
    mock_get_order.return_value = MockOrder(1, "ORD-1001", "John", "SKU-4521", 5, "pending", "2026-01-01")
    
    req = FulfillmentRequest(query="Why is ORD-1001 delayed?", order_id="ORD-1001")
    resp = asyncio.run(fulfillment_agent.handle(req, mock_db))
    
    fulfillment_agent.dispatcher.assert_not_called()
    assert "not marked as delayed" in resp.message
