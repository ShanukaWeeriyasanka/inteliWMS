import json
import re
from typing import Optional, Any
from config.llm_config import llm_config
from config.prompts import FULFILLMENT_CLASSIFIER_SYSTEM_PROMPT
from utils.logger import StructuredLogger
from agents.fulfillment.schemas import FulfillmentIntent, FulfillmentIntentResult

logger = StructuredLogger(__name__)

class FulfillmentIntentClassifier:
    """Classifies fulfillment queries into specific intents."""
    
    CONFIDENCE_THRESHOLD = 0.60
    # Heuristic confidence above this → skip LLM call entirely
    HEURISTIC_CONFIDENCE_THRESHOLD = 0.80

    # ── Heuristic keyword patterns (ordered from most to least specific) ──
    _ORDER_DELAY_PATTERNS = [
        r"\b(delay|delayed|late|behind|slow|stuck|not arrived|overdue)\b",
        r"\bwhy (is|was|has)\b.*\border\b",
    ]
    _ORDER_STATUS_PATTERNS = [
        r"\b(status|state|update|progress|where is|what is).*(order|ord-)\b",
        r"\b(ord-\d+|#\d+)\b.*\b(status|state|update|how|what)\b",
        r"\bwhat.*status\b",
        r"\bstatus.*\b(ord-\d+|order)\b",
    ]
    _SHIPPING_STATUS_PATTERNS = [
        r"\b(ship|shipped|dispatched|courier|carrier|tracking|transit|delivered)\b",
        r"\bhas.*order.*ship\b",
        r"\bship.*status\b",
    ]
    _ORDER_DETAILS_PATTERNS = [
        r"\b(details|show me|info|information|tell me about|summary)\b.*(order|ord-\d+)",
        r"(order|ord-\d+).*(details|info|show|summary)\b",
    ]
    _FULFILLMENT_PROGRESS_PATTERNS = [
        r"\b(progress|how far|stage|pick|pack|packing|picking|process|fulfil)\b",
        r"\bhow far along\b",
        r"\bfulfill.*progress\b",
    ]

    def __init__(self, llm: Optional[Any] = None):
        self._llm = llm

    @property
    def client(self):
        if self._llm is not None:
            return self._llm
        return llm_config.get_fulfillment_client()
        
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

    def _heuristic_classify(self, query: str) -> Optional[FulfillmentIntentResult]:
        """
        Rule-based instant classifier — no API calls.
        Returns a high-confidence result if patterns match, else None.
        Priority order (most to least specific): delay > shipping > progress > details > status > generic order.
        """
        q = query.lower()

        if any(re.search(p, q) for p in self._ORDER_DELAY_PATTERNS):
            return FulfillmentIntentResult(intent=FulfillmentIntent.ORDER_DELAY, confidence=0.92)

        if any(re.search(p, q) for p in self._SHIPPING_STATUS_PATTERNS):
            return FulfillmentIntentResult(intent=FulfillmentIntent.SHIPPING_STATUS, confidence=0.91)

        if any(re.search(p, q) for p in self._FULFILLMENT_PROGRESS_PATTERNS):
            return FulfillmentIntentResult(intent=FulfillmentIntent.FULFILLMENT_PROGRESS, confidence=0.90)

        # ORDER_DETAILS must come before ORDER_STATUS — 'show me details for ORD-x' is more specific
        if any(re.search(p, q) for p in self._ORDER_DETAILS_PATTERNS):
            return FulfillmentIntentResult(intent=FulfillmentIntent.ORDER_DETAILS, confidence=0.88)

        if any(re.search(p, q) for p in self._ORDER_STATUS_PATTERNS):
            return FulfillmentIntentResult(intent=FulfillmentIntent.ORDER_STATUS, confidence=0.90)

        # Generic order mention → default to ORDER_STATUS
        if re.search(r"\b(order|ord-\d+|#\d+)\b", q):
            return FulfillmentIntentResult(intent=FulfillmentIntent.ORDER_STATUS, confidence=0.82)

        return None

    def classify(self, query: str) -> FulfillmentIntentResult:
        """
        Classifies a fulfillment query using a heuristic-first strategy.

        Order of operations:
          1. Heuristic keyword classifier — instant (<1ms), no API call
          2. LLM classification — only when heuristic confidence < 0.80
          3. Safe fallback — UNKNOWN_FULFILLMENT on any failure

        Returns FulfillmentIntentResult with safe fallbacks.
        """
        if not query or not query.strip():
            return FulfillmentIntentResult(
                intent=FulfillmentIntent.UNKNOWN_FULFILLMENT,
                confidence=0.0
            )

        # 1. Fast-path: heuristic classifier — instant, no API call
        heuristic_result = self._heuristic_classify(query)
        if heuristic_result and heuristic_result.confidence >= self.HEURISTIC_CONFIDENCE_THRESHOLD:
            logger.log_event("FULFILLMENT_HEURISTIC_CLASSIFICATION", {
                "query": query[:60],
                "intent": heuristic_result.intent.value,
                "confidence": heuristic_result.confidence
            })
            return heuristic_result

        try:
            client = self.client
            if client is None:
                # No LLM available — use heuristic result if we have one, else UNKNOWN
                if heuristic_result:
                    return heuristic_result
                return FulfillmentIntentResult(
                    intent=FulfillmentIntent.UNKNOWN_FULFILLMENT,
                    confidence=0.0
                )
                
            prompt = f"""{FULFILLMENT_CLASSIFIER_SYSTEM_PROMPT}\n\nUser warehouse query: "{query}"\n\nAnalyze the query and return ONLY a valid JSON object:\n"""
            
            # Match existing Coordinator invocation pattern
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

                # Parse and validate intent string
                intent_str = str(parsed.get("intent", "UNKNOWN_FULFILLMENT")).upper()
                
                # Extract and clamp confidence
                try:
                    confidence = float(parsed.get("confidence", 0.0))
                    confidence = max(0.0, min(1.0, confidence))
                except (ValueError, TypeError):
                    confidence = 0.0

                # Validate against Enum
                try:
                    intent = FulfillmentIntent(intent_str)
                except ValueError:
                    intent = FulfillmentIntent.UNKNOWN_FULFILLMENT

                # Apply threshold escalation
                if confidence < self.CONFIDENCE_THRESHOLD or intent == FulfillmentIntent.UNKNOWN_FULFILLMENT:
                    logger.log_event("FULFILLMENT_LOW_CONFIDENCE_ESCALATION", {
                        "query": query,
                        "original_intent": intent_str,
                        "confidence": confidence
                    })
                    # Fall back to heuristic if LLM is low confidence
                    if heuristic_result:
                        return heuristic_result
                    return FulfillmentIntentResult(
                        intent=FulfillmentIntent.UNKNOWN_FULFILLMENT,
                        confidence=confidence
                    )
                
                return FulfillmentIntentResult(
                    intent=intent,
                    confidence=confidence
                )
                
        except Exception as e:
            logger.log_event("FULFILLMENT_CLASSIFICATION_EXCEPTION", {"query": query, "error": str(e)})

        # Safest fallback: use heuristic if available, else UNKNOWN
        if heuristic_result:
            return heuristic_result
        return FulfillmentIntentResult(
            intent=FulfillmentIntent.UNKNOWN_FULFILLMENT,
            confidence=0.0
        )

# Singleton instance
fulfillment_intent_classifier = FulfillmentIntentClassifier()
