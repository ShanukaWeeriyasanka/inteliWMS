"""
Inventory routing (unit tests, no network: the LLM is mocked or made to fail).

Checks meaning-level inventory phrasings, that meta words no longer swallow inventory
questions, that strong SOP / order signals still win, conversation follow-ups, and
that unrelated questions keep reaching their existing agents.
"""
from unittest.mock import MagicMock, patch

import pytest

from agents.coordinator.intent_classifier import IntentClassifier
from agents.coordinator.query_normalizer import normalize_query
from agents.coordinator.router import decide_route


class _NoLLM:
    """Any LLM call is a test failure path: classification must fall back to heuristics."""
    class models:
        @staticmethod
        def generate_content(**_):
            raise RuntimeError("LLM disabled in tests")


def _llm(domain: str, confidence: float):
    mock = MagicMock()
    mock.models.generate_content.return_value = MagicMock(
        text=f'{{"domain": "{domain}", "confidence": {confidence}, "reasoning": "mock"}}')
    return mock


@pytest.fixture
def clf():
    return IntentClassifier(llm=_NoLLM())


@pytest.mark.parametrize("query", [
    "how many units of SKU-7788 are on hand?",           # quantity
    "is the pallet wrap in stock?",                       # availability
    "do we have any thermal label printers?",             # availability, no keyword 'stock'
    "how many rolls of label tape are left?",             # quantity, plain words
    "which items are running low?",                       # low stock
    "what's below the reorder point",                     # low stock
    "show stock movements for SKU-4521",                  # movements
    "where is SKU-2045 located?",                         # location
    "what's the safety stock for SKU-4521?",              # used to go to KNOWLEDGE ("safety")
    "is the safety vest in stock?",                       # used to go to KNOWLEDGE ("safety", "vest")
    "inbound shipment from supplier for SKU-9012",        # used to go to FULFILLMENT ("shipment")
    "help me find SKU-4521",                              # used to be a META reply ("help")
    "what stock is in the cooling system",                # used to be a META reply ("what ... system")
    "forklift 3 is making a grinding noise",              # equipment health lives in the inventory agent
])
def test_inventory_phrasings_route_to_inventory(clf, query):
    res = clf.classify(query)
    assert res.domain == "INVENTORY", (query, res)
    assert res.confidence >= clf.HEURISTIC_CONFIDENCE_THRESHOLD


@pytest.mark.parametrize("query", ["help", "can you help me?", "hello", "what can you do", "what is this system",
                                   "how many agents do you have"])
def test_meta_questions_still_answered_by_coordinator(clf, query):
    assert clf.classify(query).domain == "COORDINATOR"


@pytest.mark.parametrize("query, domain", [
    ("where is the returns SOP?", "KNOWLEDGE"),
    ("what is the forklift safety speed limit protocol?", "KNOWLEDGE"),
    ("what's the policy for low stock escalation?", "KNOWLEDGE"),       # strong SOP signal beats 'low stock'
    ("where is the forklift safety manual?", "KNOWLEDGE"),
    ("why is order #4521 delayed?", "FULFILLMENT"),
    ("track shipment for order #1002", "FULFILLMENT"),
    # Multi-domain: names an order → fulfillment, which checks stock through the inventory agent
    ("is SKU-4521 in stock for order ORD-1001?", "FULFILLMENT"),
])
def test_unrelated_and_multi_domain_questions_keep_existing_routes(clf, query, domain):
    assert clf.classify(query).domain == domain


def test_follow_up_uses_thread_context(clf):
    ctx = {"last_domain": "INVENTORY"}
    for query in ("where is it?", "and the printer?", "how about the other one", "2"):
        res = clf.classify(query, context=ctx)
        assert (res.domain, res.source) == ("INVENTORY", "context"), query


def test_pending_clarification_answer_stays_with_inventory(clf):
    ctx = {"last_domain": "INVENTORY", "pending_clarification": ["Printer (SKU-1001)", "Rolls (SKU-1002)"]}
    assert clf.classify("the rolls please, thank you very much", context=ctx).domain == "INVENTORY"


def test_no_context_means_no_follow_up_guess(clf):
    res = clf.classify("where is it?")
    assert res.source != "context"


def test_follow_up_after_other_domain_is_not_forced_to_inventory(clf):
    assert clf.classify("and that one?", context={"last_domain": "KNOWLEDGE"}).source != "context"


@pytest.mark.parametrize("query", ["thanks", "ok", "thank you!"])
def test_social_reply_is_not_a_follow_up(clf, query):
    assert clf.classify(query, context={"last_domain": "INVENTORY"}).source != "context"


def test_strong_other_domain_beats_inventory_context(clf):
    res = clf.classify("what is the returns policy?", context={"last_domain": "INVENTORY"})
    assert res.domain == "KNOWLEDGE"


def test_low_confidence_llm_keeps_inventory_when_heuristic_agrees():
    # "where is the coconut milk" is only a map hint (0.75) → LLM decides; it says INVENTORY at 0.5
    res = IntentClassifier(llm=_llm("INVENTORY", 0.5)).classify("where is the coconut milk")
    assert res.domain == "INVENTORY" and res.source == "llm_low_confidence"


def test_low_confidence_llm_falls_back_to_the_weak_rule():
    # The LLM's low-confidence FULFILLMENT guess is not used; the map-wording rule decides
    res = IntentClassifier(llm=_llm("FULFILLMENT", 0.4)).classify("where is the coconut milk")
    assert (res.domain, res.rule_id, res.decided_by) == ("INVENTORY", "inventory.twin_hint", "fallback")


def test_llm_prompt_includes_recent_conversation():
    llm = _llm("INVENTORY", 0.9)
    IntentClassifier(llm=llm).classify("could you check the one we discussed earlier for tomorrow",
                                       context={"last_domain": "KNOWLEDGE",
                                                "history": [{"role": "user", "content": "returns SOP"}]})
    prompt = llm.models.generate_content.call_args.kwargs["contents"]
    assert "Recent conversation" in prompt and "returns SOP" in prompt


def test_decide_route_reports_source_and_follow_up():
    with patch("agents.coordinator.router.intent_classifier", IntentClassifier(llm=_NoLLM())):
        d = decide_route("where is it?", context={"last_domain": "INVENTORY"})
    assert d["target_agent"] == "inventory_agent" and d["follow_up"] is True and d["source"] == "context"


def test_decide_route_accepts_classifiers_without_context_param():
    legacy = MagicMock()
    legacy.classify = lambda q: IntentClassifier(llm=_NoLLM()).classify(q)
    d = decide_route("check stock for SKU-4521", classifier=legacy, context={"last_domain": "INVENTORY"})
    assert d["target_agent"] == "inventory_agent"


def test_normalizer_keeps_follow_ups_as_typed():
    with patch("agents.coordinator.query_normalizer.llm_config") as cfg:
        cfg.gemini_key = "x"
        cfg.hybrid_complete.side_effect = AssertionError("follow-ups must not be rewritten without context")
        assert normalize_query("the second", context={"last_domain": "INVENTORY"}) == "the second"
        assert normalize_query("2", context={"last_domain": "INVENTORY"}) == "2"
