import pytest
from unittest.mock import MagicMock
from agents.fulfillment.intent_classifier import FulfillmentIntentClassifier
from agents.fulfillment.schemas import FulfillmentIntent

def create_mock_llm(intent: str, confidence: float = 0.95, malformed: bool = False):
    mock = MagicMock()
    mock_resp = MagicMock()
    if malformed:
        mock_resp.text = '{"some_other_field": "test"'
    else:
        mock_resp.text = f'{{"intent": "{intent}", "confidence": {confidence}}}'
    mock.models.generate_content.return_value = mock_resp
    return mock

def test_classify_order_status():
    classifier = FulfillmentIntentClassifier(llm=create_mock_llm("ORDER_STATUS", 0.95))
    result = classifier.classify("What is the status of ORD-1001?")
    assert result.intent == FulfillmentIntent.ORDER_STATUS
    assert result.confidence == 0.95

def test_classify_order_delay():
    classifier = FulfillmentIntentClassifier(llm=create_mock_llm("ORDER_DELAY", 0.92))
    result = classifier.classify("Why is ORD-1001 delayed?")
    assert result.intent == FulfillmentIntent.ORDER_DELAY

def test_classify_order_details():
    classifier = FulfillmentIntentClassifier(llm=create_mock_llm("ORDER_DETAILS", 0.88))
    result = classifier.classify("Show me details for ORD-1003.")
    assert result.intent == FulfillmentIntent.ORDER_DETAILS

def test_classify_shipping_status():
    classifier = FulfillmentIntentClassifier(llm=create_mock_llm("SHIPPING_STATUS", 0.90))
    result = classifier.classify("Has ORD-1003 shipped?")
    assert result.intent == FulfillmentIntent.SHIPPING_STATUS

def test_classify_fulfillment_progress():
    classifier = FulfillmentIntentClassifier(llm=create_mock_llm("FULFILLMENT_PROGRESS", 0.85))
    result = classifier.classify("How far along is ORD-1001?")
    assert result.intent == FulfillmentIntent.FULFILLMENT_PROGRESS

def test_classify_low_confidence():
    classifier = FulfillmentIntentClassifier(llm=create_mock_llm("ORDER_STATUS", 0.40))
    result = classifier.classify("Is ORD-1002 still pending?")
    assert result.intent == FulfillmentIntent.UNKNOWN_FULFILLMENT
    assert result.confidence == 0.40

def test_classify_unsupported_intent():
    classifier = FulfillmentIntentClassifier(llm=create_mock_llm("MAGICAL_INTENT", 0.99))
    result = classifier.classify("Do magic on ORD-1001")
    assert result.intent == FulfillmentIntent.UNKNOWN_FULFILLMENT

def test_classify_malformed_json():
    classifier = FulfillmentIntentClassifier(llm=create_mock_llm("ORDER_STATUS", malformed=True))
    result = classifier.classify("What is the status of ORD-1001?")
    assert result.intent == FulfillmentIntent.UNKNOWN_FULFILLMENT
    assert result.confidence == 0.0

def test_classify_exception_fallback():
    mock = MagicMock()
    mock.models.generate_content.side_effect = Exception("API down")
    classifier = FulfillmentIntentClassifier(llm=mock)
    result = classifier.classify("What is the status of ORD-1001?")
    assert result.intent == FulfillmentIntent.UNKNOWN_FULFILLMENT
    assert result.confidence == 0.0

def test_classify_empty_query():
    classifier = FulfillmentIntentClassifier(llm=create_mock_llm("ORDER_STATUS"))
    result = classifier.classify("")
    assert result.intent == FulfillmentIntent.UNKNOWN_FULFILLMENT
    assert result.confidence == 0.0
