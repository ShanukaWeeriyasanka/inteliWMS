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


# == Heuristic fast-path tests (no LLM needed) =================================

def test_classify_order_status():
    """Heuristic detects ORDER_STATUS from 'status of order' keywords."""
    classifier = FulfillmentIntentClassifier()
    result = classifier.classify("What is the status of ORD-1001?")
    assert result.intent == FulfillmentIntent.ORDER_STATUS
    assert result.confidence >= 0.80

def test_classify_order_delay():
    """Heuristic detects ORDER_DELAY from 'delayed' keyword."""
    classifier = FulfillmentIntentClassifier()
    result = classifier.classify("Why is ORD-1001 delayed?")
    assert result.intent == FulfillmentIntent.ORDER_DELAY
    assert result.confidence >= 0.80

def test_classify_order_details():
    """Heuristic detects ORDER_DETAILS from 'show me details' pattern."""
    classifier = FulfillmentIntentClassifier()
    result = classifier.classify("Show me details for ORD-1003.")
    assert result.intent == FulfillmentIntent.ORDER_DETAILS
    assert result.confidence >= 0.80

def test_classify_shipping_status():
    """Heuristic detects SHIPPING_STATUS from 'shipped' keyword."""
    classifier = FulfillmentIntentClassifier()
    result = classifier.classify("Has ORD-1003 shipped?")
    assert result.intent == FulfillmentIntent.SHIPPING_STATUS
    assert result.confidence >= 0.80

def test_classify_fulfillment_progress():
    """Heuristic detects FULFILLMENT_PROGRESS from 'how far along' pattern."""
    classifier = FulfillmentIntentClassifier()
    result = classifier.classify("How far along is ORD-1001?")
    assert result.intent == FulfillmentIntent.FULFILLMENT_PROGRESS
    assert result.confidence >= 0.80


# == LLM path tests (queries that heuristic does not confidently match) =========

def test_classify_via_llm_high_confidence():
    """LLM path used for ambiguous queries; high-confidence LLM result wins."""
    classifier = FulfillmentIntentClassifier(llm=create_mock_llm("ORDER_STATUS", 0.95))
    result = classifier.classify("Can you help me?")
    assert result.intent == FulfillmentIntent.ORDER_STATUS
    assert result.confidence == 0.95

def test_classify_low_confidence_falls_back_to_unknown():
    """LLM returns low confidence AND heuristic has no match -> UNKNOWN_FULFILLMENT."""
    classifier = FulfillmentIntentClassifier(llm=create_mock_llm("ORDER_STATUS", 0.40))
    result = classifier.classify("Can you help me?")
    assert result.intent == FulfillmentIntent.UNKNOWN_FULFILLMENT
    assert result.confidence == 0.40

def test_classify_unsupported_intent():
    """LLM returns unrecognized intent enum -> UNKNOWN_FULFILLMENT."""
    classifier = FulfillmentIntentClassifier(llm=create_mock_llm("MAGICAL_INTENT", 0.99))
    result = classifier.classify("Do some magic please.")
    assert result.intent == FulfillmentIntent.UNKNOWN_FULFILLMENT

def test_classify_malformed_json_with_heuristic_fallback():
    """Malformed LLM JSON -> heuristic result returned when available."""
    classifier = FulfillmentIntentClassifier(llm=create_mock_llm("ORDER_STATUS", malformed=True))
    result = classifier.classify("What is the status of ORD-1001?")
    assert result.intent == FulfillmentIntent.ORDER_STATUS

def test_classify_malformed_json_no_heuristic():
    """Malformed LLM JSON + no heuristic match -> UNKNOWN_FULFILLMENT."""
    classifier = FulfillmentIntentClassifier(llm=create_mock_llm("ORDER_STATUS", malformed=True))
    result = classifier.classify("Can you help me?")
    assert result.intent == FulfillmentIntent.UNKNOWN_FULFILLMENT
    assert result.confidence == 0.0

def test_classify_exception_with_heuristic_fallback():
    """LLM exception + heuristic match -> heuristic result returned."""
    mock = MagicMock()
    mock.models.generate_content.side_effect = Exception("API down")
    classifier = FulfillmentIntentClassifier(llm=mock)
    result = classifier.classify("What is the status of ORD-1001?")
    assert result.intent == FulfillmentIntent.ORDER_STATUS

def test_classify_exception_no_heuristic():
    """LLM exception + no heuristic match -> UNKNOWN_FULFILLMENT."""
    mock = MagicMock()
    mock.models.generate_content.side_effect = Exception("API down")
    classifier = FulfillmentIntentClassifier(llm=mock)
    result = classifier.classify("Can you help me?")
    assert result.intent == FulfillmentIntent.UNKNOWN_FULFILLMENT
    assert result.confidence == 0.0

def test_classify_empty_query():
    classifier = FulfillmentIntentClassifier(llm=create_mock_llm("ORDER_STATUS"))
    result = classifier.classify("")
    assert result.intent == FulfillmentIntent.UNKNOWN_FULFILLMENT
    assert result.confidence == 0.0
