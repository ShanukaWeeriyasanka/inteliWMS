"""
Intent Classifier for IntelliWMS Coordinator Agent (Task 2).
Uses LLM (Gemini or configured provider) to classify warehouse queries into:
- INVENTORY
- FULFILLMENT
- KNOWLEDGE
- COORDINATOR  (meta/system questions answered directly by the coordinator)
Includes confidence scoring, fallback logic for confidence < 0.60, and heuristic rules.
"""
import json
import re
from typing import Optional, Any
from config.llm_config import llm_config
from config.prompts import COORDINATOR_SYSTEM_PROMPT
from utils.logger import StructuredLogger

logger = StructuredLogger(__name__)

class IntentResult(tuple):
    """
    Hybrid Result object supporting both 3-tuple unpacking:
    (intent, confidence, reasoning) = classifier.classify(...)
    and dictionary access: res["domain"], res.get("confidence")
    """
    def __new__(cls, intent: str, confidence: float, reasoning: str):
        return super().__new__(cls, (intent, float(confidence), str(reasoning)))

    @property
    def intent(self) -> str:
        return self[0]

    @property
    def domain(self) -> str:
        return self[0]

    @property
    def confidence(self) -> float:
        return self[1]

    @property
    def reasoning(self) -> str:
        return self[2]

    def get(self, key: str, default: Any = None) -> Any:
        mapping = {
            "intent": self.intent,
            "domain": self.domain,
            "confidence": self.confidence,
            "reasoning": self.reasoning
        }
        return mapping.get(key, default)

    def __getitem__(self, item):
        if isinstance(item, str):
            val = self.get(item)
            if val is None:
                raise KeyError(item)
            return val
        return super().__getitem__(item)

    def to_dict(self) -> dict:
        return {
            "domain": self.domain,
            "intent": self.intent,
            "confidence": self.confidence,
            "reasoning": self.reasoning
        }

class IntentClassifier:
    """Classifies warehouse queries into specialist agent domains."""

    VALID_DOMAINS = {"INVENTORY", "FULFILLMENT", "KNOWLEDGE", "COORDINATOR"}
    CONFIDENCE_THRESHOLD = 0.60

    # Meta/system questions the coordinator answers directly without delegation
    META_PATTERNS = [
        r"\bhow many agents\b",
        r"\bhow many subagents\b",
        r"\bwhat agents\b",
        r"\bwhat subagents\b",
        r"\bwhich agents\b",
        r"\blist.*agents\b",
        r"\bwhat can you do\b",
        r"\bwhat are you\b",
        r"\bwho are you\b",
        r"\bintroduce yourself\b",
        r"^(hi+|hello+|hey+|yo+|greetings|sup|howdy)[\s\!\?\.]*$",  # Only whole-query greetings
        r"\bhelp\b",
        r"\bbruh\b",
        r"\bwhat is intelliwms\b",
        r"\bwhat do you do\b",
        r"\bwhat.*system\b",
        r"\byour (agents|subagents|capabilities|features)\b",
    ]

    def __init__(self, llm: Optional[Any] = None):
        self._llm = llm

    @property
    def client(self):
        if self._llm is not None:
            return self._llm
        return llm_config.get_client()

    # Minimum heuristic confidence to skip LLM — queries above this threshold
    # are routed instantly without any API call.
    HEURISTIC_CONFIDENCE_THRESHOLD = 0.80

    def classify(self, query: str) -> IntentResult:
        """
        Classifies a query using a heuristic-first strategy for minimal latency.

        Order of operations:
          0. Meta/system fast-path (greetings, capability questions) — instant
          1. Deterministic heuristic classifier — instant (< 1ms)
          2. LLM classification — only when heuristic confidence < 0.80

        Returns:
            IntentResult: unpackable as (intent, confidence, reasoning)
        """
        if not query or not query.strip():
            return IntentResult("COORDINATOR", 1.0, "Empty query handled by coordinator")

        # 0. Fast-path: meta/system questions handled directly — no API call needed
        meta_result = self._detect_meta_query(query)
        if meta_result:
            return meta_result

        # 1. Run heuristic classifier first — instant, no API call
        heuristic_result = self._heuristic_fallback(query)
        if heuristic_result.confidence >= self.HEURISTIC_CONFIDENCE_THRESHOLD:
            # High-confidence heuristic result — return immediately, skip LLM
            logger.log_event("HEURISTIC_CLASSIFICATION", {
                "query": query[:60],
                "domain": heuristic_result.domain,
                "confidence": heuristic_result.confidence
            })
            return heuristic_result

        # 2. Low-confidence heuristic — try LLM for ambiguous queries
        try:
            client = self.client
            if client is not None:
                prompt = f"""{COORDINATOR_SYSTEM_PROMPT}

User warehouse query: "{query}"

Analyze the query and return ONLY a valid JSON object:
"""
                if hasattr(client, "models") and hasattr(client.models, "generate_content"):
                    response = client.models.generate_content(
                        model=llm_config.GEMINI_MODEL,
                        contents=prompt
                    )
                    raw_text = getattr(response, "text", "").strip()
                elif callable(client):
                    raw_text = str(client(prompt)).strip()
                elif hasattr(client, "generate"):
                    raw_text = str(client.generate(prompt)).strip()
                else:
                    raw_text = ""

                if raw_text:
                    clean_json = self._extract_json(raw_text)
                    parsed = json.loads(clean_json)

                    domain = str(parsed.get("domain") or parsed.get("intent") or "").upper()
                    confidence = float(parsed.get("confidence", 0.85))
                    reasoning = str(parsed.get("reasoning", "LLM classified intent"))

                    if confidence < self.CONFIDENCE_THRESHOLD or domain not in self.VALID_DOMAINS:
                        logger.log_event("LOW_CONFIDENCE_ESCALATION", {
                            "query": query,
                            "original_domain": domain,
                            "confidence": confidence
                        })
                        return IntentResult(
                            "KNOWLEDGE",
                            confidence,
                            f"Escalated to KNOWLEDGE due to low confidence ({confidence:.2f}): {reasoning}"
                        )

                    logger.log_agent_decision("coordinator", query, domain, reasoning)
                    return IntentResult(domain, confidence, reasoning)

        except Exception as e:
            logger.log_event("LLM_CLASSIFICATION_EXCEPTION", {"query": query, "error": str(e)})

        # 3. LLM failed — fall back to heuristic result regardless of confidence
        return heuristic_result

    def _heuristic_fallback(self, query: str) -> IntentResult:
        """Rule-based heuristic classifier when LLM is unavailable or for testing."""
        q_lower = query.lower()

        # INVENTORY indicators (Stock, Location, Doc Parser, Depletion, Anomaly, Transfer, Equipment Health)
        inventory_patterns = [
            r"\b(stock|inventory|quantity|sku|sku-\d+|reorder|restock|battery|label rolls|pallet wrap)\b",
            r"\b(how many|on hand|in stock|warehouse aisle|shelf|bin location|bay map)\b",
            r"\b(supplier email|supplier pdf|parse email|inbound invoice|manifest|po-\d+|we shipped)\b",
            r"\b(grinding|hydraulic leak|conveyor slip|belt squeal|agv-\d+|equipment health|machine breakdown|informal log)\b",
            r"\b(forklift.*(grind|leak|noise|break|service|repair|shaking))\b",
            r"\b(shrinkage|anomaly|missing stock|discrepancy|unauthorized adjustment|loss prevention)\b",
            r"\b(transfer|sibling warehouse|other warehouse|surplus stock|wh-beta|wh-gamma|wh-delta)\b",
            r"\b(burn rate|depletion|velocity|days until stockout|predict reorder)\b"
        ]
        # FULFILLMENT indicators
        fulfillment_patterns = [
            r"\b(order|orders|ord-\d+|#\d+|delay|delayed|dispatch|tracking|track|shipment|courier|carrier)\b",
            r"\b(complaint|shipping|packing slip|transit)\b"
        ]
        # KNOWLEDGE indicators
        knowledge_patterns = [
            r"\b(sop|sop-\d+|standard operating procedure|policy|policies|guideline|manual|safety|protocol|sp-\d+)\b",
            r"\b(returns|how to return|compliance|shift handover|shift notes|speed limit|vest)\b"
        ]

        if any(re.search(p, q_lower) for p in knowledge_patterns):
            return IntentResult("KNOWLEDGE", 0.91, "Heuristic match: warehouse SOP, safety, and protocol signals.")

        if any(re.search(p, q_lower) for p in fulfillment_patterns):
            return IntentResult("FULFILLMENT", 0.94, "Heuristic match: order status, dispatch, and tracking signals.")

        if any(re.search(p, q_lower) for p in inventory_patterns):
            return IntentResult("INVENTORY", 0.93, "Heuristic match: stock, SKU, and inventory signals.")

        # Default: tell the user we didn't understand rather than hallucinating
        return IntentResult(
            "COORDINATOR",
            0.50,
            "Query did not match any warehouse domain — coordinator will respond directly."
        )

    def _detect_meta_query(self, query: str) -> Optional[IntentResult]:
        """Detects system/meta questions that the coordinator handles itself."""
        q_lower = query.lower().strip()
        if any(re.search(p, q_lower) for p in self.META_PATTERNS):
            logger.log_event("COORDINATOR_META_QUERY_DETECTED", {"query": query[:80]})
            return IntentResult(
                "COORDINATOR",
                0.99,
                "Meta/system query detected — answered directly by coordinator without agent delegation."
            )
        return None

    def _extract_json(self, text: str) -> str:
        """Strips markdown code fences and returns clean JSON string."""
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()

# Singleton instance
intent_classifier = IntentClassifier()
