import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from backend.main import app
from agents.fulfillment.schemas import FulfillmentIntent, FulfillmentIntentResult
import time
import jwt

from config.settings import settings

client = TestClient(app)
TEST_SECRET = settings.JWT_SECRET

@pytest.fixture
def valid_staff_token():
    payload = {
        "user_id": "user_123",
        "username": "john_staff",
        "role": "staff",
        "exp": int(time.time()) + 3600
    }
    return jwt.encode(payload, TEST_SECRET, algorithm="HS256")

class MockOrder:
    def __init__(self, status="pending"):
        self.status = status

@patch('agents.fulfillment.fulfillment_agent.fulfillment_intent_classifier.classify')
@patch('agents.fulfillment.fulfillment_agent.get_order_by_id')
def test_integration_routing_to_fulfillment(mock_get_order, mock_classify, valid_staff_token):
    mock_classify.return_value = FulfillmentIntentResult(intent=FulfillmentIntent.ORDER_STATUS, confidence=0.95)
    mock_get_order.return_value = MockOrder(status="shipped")
    
    response = client.post(
        "/query",
        json={"token": valid_staff_token, "message": "What is the status of ORD-1001?"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["agent_used"] == "fulfillment_agent"
    assert "ORD-1001" in data["response"]
    assert "shipped" in data["response"]
    assert data["fulfillment_details"]["success"] is True

@patch('agents.fulfillment.fulfillment_agent.fulfillment_intent_classifier.classify')
def test_integration_missing_order_id(mock_classify, valid_staff_token):
    mock_classify.return_value = FulfillmentIntentResult(intent=FulfillmentIntent.ORDER_STATUS, confidence=0.95)
    
    response = client.post(
        "/query",
        json={"token": valid_staff_token, "message": "What is the status of my order?"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["fulfillment_details"]["success"] is False
    assert "Please provide a valid order ID" in data["response"]

@patch('agents.fulfillment.fulfillment_agent.fulfillment_intent_classifier.classify')
@patch('agents.fulfillment.fulfillment_agent.get_order_by_id')
def test_integration_missing_order(mock_get_order, mock_classify, valid_staff_token):
    mock_classify.return_value = FulfillmentIntentResult(intent=FulfillmentIntent.ORDER_STATUS, confidence=0.95)
    mock_get_order.return_value = None
    
    response = client.post(
        "/query",
        json={"token": valid_staff_token, "message": "What is the status of ORD-9999?"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["fulfillment_details"]["success"] is False
    assert "not found" in data["response"]

@patch('agents.fulfillment.fulfillment_agent.fulfillment_intent_classifier.classify')
def test_integration_unknown_fulfillment(mock_classify, valid_staff_token):
    mock_classify.return_value = FulfillmentIntentResult(intent=FulfillmentIntent.UNKNOWN_FULFILLMENT, confidence=0.0)
    
    response = client.post(
        "/query",
        json={"token": valid_staff_token, "message": "Do some magic on ORD-1001"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["fulfillment_details"]["success"] is False
    assert "could not confidently determine" in data["response"]

@patch('agents.fulfillment.fulfillment_agent.FulfillmentAgent.handle')
def test_integration_fulfillment_exception(mock_handle, valid_staff_token):
    mock_handle.side_effect = Exception("Simulated crash")
    
    response = client.post(
        "/query",
        json={"token": valid_staff_token, "message": "Status of ORD-1001"}
    )
    # Coordinator catches and returns safe error
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success" # The API request succeeds, but the fulfillment failed
    assert data["fulfillment_details"]["success"] is False
    assert "Unable to process" in data["response"]

def test_integration_inventory_routing_preserved(valid_staff_token):
    response = client.post(
        "/query",
        json={"token": valid_staff_token, "message": "check stock for SKU-1088"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["agent_used"] == "inventory_agent"
    assert "fulfillment_details" not in data

def test_integration_knowledge_routing_preserved(valid_staff_token):
    response = client.post(
        "/query",
        json={"token": valid_staff_token, "message": "where is the returns SOP?"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["agent_used"] == "knowledge_agent"

def test_integration_security_preserved():
    response = client.post(
        "/query",
        json={"token": "invalid_jwt", "message": "Status of ORD-1001"}
    )
    assert response.status_code == 401
    assert response.json()["status"] == "error"
