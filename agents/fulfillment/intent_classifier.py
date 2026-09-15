import json
from typing import Optional, Any
from config.llm_config import llm_config
from config.prompts import FULFILLMENT_CLASSIFIER_SYSTEM_PROMPT
from utils.logger import StructuredLogger
from agents.fulfillment.schemas import FulfillmentIntent, FulfillmentIntentResult

logger = StructuredLogger(__name__)

class FulfillmentIntentClassifier:
    """Classifies fulfillment queries into specific intents."""
    
    CONFIDENCE_THRESHOLD = 0.60
    
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

    def classify(self, query: str) -> FulfillmentIntentResult:
        """
        Sends query to LLM to determine the specific fulfillment intent.
        Returns FulfillmentIntentResult with safe fallbacks.
        """
        if not query or not query.strip():
            return FulfillmentIntentResult(
                intent=FulfillmentIntent.UNKNOWN_FULFILLMENT,
                confidence=0.0
            )

        try:
            client = self.client
            if client is None:
                return FulfillmentIntentResult(
                    intent=FulfillmentIntent.UNKNOWN_FULFILLMENT,
                    confidence=0.0
                )
                
            prompt = f"""{FULFILLMENT_CLASSIFIER_SYSTEM_PROMPT}\n\nUser warehouse query: "{query}"\n\nAnalyze the query and return ONLY a valid JSON object:\n"""
            
            # Match existing Coordinator invocation pattern
            if hasattr(client, "models") and hasattr(client.models, "generate_content"):
                response = client.models.generate_content(
                    model="gemini-3.6-flash",
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

        # Safest fallback
        return FulfillmentIntentResult(
            intent=FulfillmentIntent.UNKNOWN_FULFILLMENT,
            confidence=0.0
        )

# Singleton instance
fulfillment_intent_classifier = FulfillmentIntentClassifier()
