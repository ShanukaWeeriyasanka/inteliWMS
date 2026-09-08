import json
from config.llm_config import llm_config
from config.prompts import COORDINATOR_SYSTEM_PROMPT
from utils.logger import StructuredLogger

logger = StructuredLogger(__name__)

class IntentClassifier:
    """Classifies warehouse queries into specialist agent domains using Gemini."""

    def __init__(self):
        self.client = llm_config.get_client()

    def classify(self, query: str) -> dict:
        """
        Sends query to Gemini with the coordinator system prompt.
        Returns:
            dict: { "domain": "...", "confidence": 0.95, "reasoning": "..." }
        """
        prompt = f"""{COORDINATOR_SYSTEM_PROMPT}

User warehouse query: "{query}"

Analyze the query and return ONLY a valid JSON object:
"""
        try:
            # Call official Gemini SDK
            response = self.client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt
            )

            response_text = response.text.strip()
            
            # Clean possible markdown wrapping (```json ... ```)
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]

            parsed = json.loads(response_text.strip())

            # Log the decision for audit trail
            logger.log_agent_decision(
                agent_name="coordinator",
                input_msg=query,
                decision=parsed.get("domain", "UNKNOWN"),
                reasoning=parsed.get("reasoning", "No reasoning provided")
            )

            return parsed

        except Exception as e:
            # Safe fallback if API errors or JSON parse fails
            logger.log_event("ROUTING_ERROR", {"query": query, "error": str(e)})
            return {
                "domain": "KNOWLEDGE",
                "confidence": 0.50,
                "reasoning": f"Routing fallback triggered due to exception: {str(e)}"
            }

# Singleton instance
intent_classifier = IntentClassifier()
