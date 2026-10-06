"""
Unit tests for Coordinator Agent Task 2: Intent Classification & Routing Engine.
Tests:
- IntentClassifier with mock LLM and rule-based heuristics
- Low-confidence escalation (< 0.60)
- route_to_agent mapping logic
- context_builder entity extraction (SKUs, Order IDs) and audit metadata
"""
import pytest
from unittest.mock import MagicMock

from agents.coordinator.intent_classifier import IntentClassifier, intent_classifier
from agents.coordinator.router import route_to_agent, decide_route
from agents.coordinator.context_builder import build_context, extract_sku, extract_order_id

@pytest.fixture
def mock_llm_inventory():
    """Mock LLM returning an INVENTORY classification JSON."""
    mock = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = '{"domain": "INVENTORY", "confidence": 0.95, "reasoning": "Stock check query"}'
    mock.models.generate_content.return_value = mock_resp
    return mock

@pytest.fixture
def mock_llm_fulfillment():
    """Mock LLM returning a FULFILLMENT classification JSON."""
    mock = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = '{"domain": "FULFILLMENT", "confidence": 0.92, "reasoning": "Order delivery inquiry"}'
    mock.models.generate_content.return_value = mock_resp
    return mock

@pytest.fixture
def mock_llm_knowledge():
    """Mock LLM returning a KNOWLEDGE classification JSON."""
    mock = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = '{"domain": "KNOWLEDGE", "confidence": 0.89, "reasoning": "SOP policy inquiry"}'
    mock.models.generate_content.return_value = mock_resp
    return mock

@pytest.fixture
def mock_llm_low_confidence():
    """Mock LLM returning low confidence (< 0.60)."""
    mock = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = '{"domain": "INVENTORY", "confidence": 0.45, "reasoning": "Ambiguous message"}'
    mock.models.generate_content.return_value = mock_resp
    return mock

# =========================================================================
# 1. INTENT CLASSIFICATION TESTS (Specification from COORDINATOR_AGENT_3PERSON_SPLIT.md)
# =========================================================================

def test_classify_inventory_query(mock_llm_inventory):
    """Test that 'check stock' is classified as INVENTORY (Person B spec)."""
    classifier = IntentClassifier(llm=mock_llm_inventory)
    intent, confidence, reasoning = classifier.classify("check stock for SKU-4521")
    assert intent == "INVENTORY"
    assert confidence > 0.8
    assert "Stock" in reasoning or "INVENTORY" in intent

def test_classify_fulfillment_query(mock_llm_fulfillment):
    """Test that 'order delay' is classified as FULFILLMENT (Person B spec)."""
    classifier = IntentClassifier(llm=mock_llm_fulfillment)
    intent, confidence, reasoning = classifier.classify("why is order #4521 delayed?")
    assert intent == "FULFILLMENT"
    assert confidence > 0.8
    assert "Order" in reasoning or "FULFILLMENT" in intent

def test_classify_knowledge_query(mock_llm_knowledge):
    """Test that 'where is returns SOP' is classified as KNOWLEDGE (Person B spec)."""
    classifier = IntentClassifier(llm=mock_llm_knowledge)
    intent, confidence, reasoning = classifier.classify("where is the returns SOP?")
    assert intent == "KNOWLEDGE"
    assert confidence > 0.8
    assert "SOP" in reasoning or "KNOWLEDGE" in intent

def test_classify_low_confidence_asks_to_clarify(mock_llm_low_confidence):
    """An LLM suggestion with confidence < 0.60 is not used: no rule matched, so the user is asked to clarify."""
    classifier = IntentClassifier(llm=mock_llm_low_confidence)
    res = classifier.classify("maybe something somewhere")
    assert res.domain == "COORDINATOR"
    assert res.rule_id == "clarify.domain"
    assert res.decided_by == "fallback" and res.llm_status == "low_confidence"

def test_classify_heuristic_fallback_stock():
    """Test rule heuristic classifies stock queries correctly without LLM."""
    classifier = IntentClassifier(llm=None)
    intent, confidence, _ = classifier.classify("how many units of SKU-7788 are on hand?")
    assert intent == "INVENTORY"
    assert confidence >= 0.85

def test_classify_heuristic_fallback_tracking():
    """Test rule heuristic classifies tracking queries correctly without LLM."""
    classifier = IntentClassifier(llm=None)
    intent, confidence, _ = classifier.classify("track shipment for order #1002")
    assert intent == "FULFILLMENT"
    assert confidence >= 0.85

def test_classify_heuristic_fallback_sop():
    """Test rule heuristic classifies warehouse procedures correctly without LLM."""
    classifier = IntentClassifier(llm=None)
    intent, confidence, _ = classifier.classify("what is the forklift safety speed limit protocol?")
    assert intent == "KNOWLEDGE"
    assert confidence >= 0.85

def test_classify_empty_query():
    """Test empty query gracefully defaults to COORDINATOR."""
    classifier = IntentClassifier(llm=None)
    intent, confidence, reasoning = classifier.classify("")
    assert intent == "COORDINATOR"
    assert "Empty" in reasoning

# =========================================================================
# 2. ROUTING LOGIC TESTS
# =========================================================================

def test_route_to_agent_mappings():
    """Test standard mapping from intent string to specialist agent name."""
    assert route_to_agent("INVENTORY") == "inventory_agent"
    assert route_to_agent("inventory") == "inventory_agent"
    assert route_to_agent("FULFILLMENT") == "fulfillment_agent"
    assert route_to_agent("fulfillment") == "fulfillment_agent"
    assert route_to_agent("KNOWLEDGE") == "knowledge_agent"
    assert route_to_agent("knowledge") == "knowledge_agent"

def test_route_to_agent_unknown_defaults_to_knowledge():
    """Test unknown or malformed intent safely defaults to knowledge_agent."""
    assert route_to_agent("UNKNOWN_DOMAIN") == "knowledge_agent"
    assert route_to_agent("") == "knowledge_agent"
    assert route_to_agent(None) == "knowledge_agent"

def test_decide_route_end_to_end(mock_llm_inventory):
    """Test decide_route produces a complete decision dict with target agent."""
    classifier = IntentClassifier(llm=mock_llm_inventory)
    decision = decide_route("stock level for battery", classifier=classifier)
    assert decision["target_agent"] == "inventory_agent"
    assert decision["domain"] == "INVENTORY"
    assert decision["confidence"] >= 0.8
    assert "reasoning" in decision

# =========================================================================
# 3. CONTEXT BUILDER & ENTITY EXTRACTION TESTS
# =========================================================================

def test_extract_sku():
    """Test extraction of SKU codes in various formats."""
    assert extract_sku("where is SKU-4521 located?") == "SKU-4521"
    assert extract_sku("check stock on SKU7788 in bay 3") == "SKU7788"
    assert extract_sku("general question without any item code") is None

def test_extract_order_id():
    """Test extraction of order identifiers — all formats normalize to ORD-XXXX."""
    assert extract_order_id("what is the status of order #4521?") == "ORD-4521"
    assert extract_order_id("dispatch status for ORD-1001") == "ORD-1001"
    assert extract_order_id("why is order 9012 delayed?") == "ORD-9012"
    assert extract_order_id("where is the safety manual?") is None

def test_build_context_full_payload():
    """Test build_context packages message, entities, user role, and audit log."""
    context = build_context(
        user_id="user_123",
        message="why is order #4521 delayed?",
        intent="FULFILLMENT",
        role="staff"
    )
    assert context["user_id"] == "user_123"
    assert context["user_role"] == "staff"
    assert context["original_message"] == "why is order #4521 delayed?"
    assert context["intent"] == "FULFILLMENT"
    assert context["extracted_order_id"] == "ORD-4521"  # Normalized to ORD-XXXX format
    assert context["audit_log"] == "routed_by_coordinator"
    assert "timestamp" in context
