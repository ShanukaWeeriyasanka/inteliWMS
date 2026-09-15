"""
LLM Configuration — Hybrid Gemini + Groq provider.
Gemini is primary (smartest). Groq is automatic fallback (fastest, free tier).
All LLM calls in IntelliWMS go through hybrid_complete() for resilience.
"""
from google import genai
from config.settings import settings
from utils.logger import StructuredLogger

logger = StructuredLogger(__name__)


class LLMConfig:
    """Centralized Gemini + Groq hybrid LLM provider configuration with key isolation."""

    GEMINI_MODEL: str = "gemini-3.6-flash"
    GROQ_MODEL: str = "llama3-70b-8192"  # Best free Groq model for reasoning

    def __init__(self):
        self.primary_provider = settings.LLM_PRIMARY
        self.gemini_key = settings.GEMINI_API_KEY
        self.fulfillment_gemini_key = settings.FULFILLMENT_GEMINI_API_KEY
        self.groq_key = settings.GROQ_API_KEY

    # ------------------------------------------------------------------ #
    # Individual Clients                                                   #
    # ------------------------------------------------------------------ #

    def get_client(self):
        """Returns the Coordinator Gemini client using GEMINI_API_KEY."""
        if not self.gemini_key:
            raise ValueError("GEMINI_API_KEY not found in .env. Please check your .env file.")
        try:
            return genai.Client(api_key=self.gemini_key)
        except Exception as e:
            logger.log_event("GEMINI_CLIENT_INIT_FAILED", {"error": str(e)})
            raise

    def get_fulfillment_client(self):
        """Returns the Fulfillment-specific Gemini client using FULFILLMENT_GEMINI_API_KEY."""
        if not self.fulfillment_gemini_key:
            raise ValueError("FULFILLMENT_GEMINI_API_KEY not found in .env. Please check your .env file.")
        
        return genai.Client(api_key=self.fulfillment_gemini_key)

    def get_groq_client(self):
        """Returns a Groq client (used as fallback or standalone)."""
        if not self.groq_key:
            return None
        try:
            from groq import Groq
            return Groq(api_key=self.groq_key)
        except Exception as e:
            logger.log_event("GROQ_CLIENT_INIT_FAILED", {"error": str(e)})
            return None

    # ------------------------------------------------------------------ #
    # Unified Hybrid Complete (Gemini → Groq fallback)                   #
    # ------------------------------------------------------------------ #

    def hybrid_complete(self, prompt: str, system: str = "", max_tokens: int = 1024) -> str:
        """
        Send a prompt to Gemini first. If Gemini fails or key is missing,
        automatically falls back to Groq.

        Args:
            prompt: User message / query to send
            system: System instruction / persona
            max_tokens: Maximum tokens to generate

        Returns:
            str: LLM response text, or empty string if both fail.
        """
        full_prompt = f"{system}\n\n{prompt}".strip() if system else prompt

        # 1. Try Gemini
        if self.gemini_key:
            try:
                client = self.get_client()
                if client:
                    response = client.models.generate_content(
                        model=self.GEMINI_MODEL,
                        contents=full_prompt
                    )
                    text = getattr(response, "text", "").strip()
                    if text:
                        logger.log_event("LLM_GEMINI_SUCCESS", {"tokens": len(text.split())})
                        return text
            except Exception as e:
                logger.log_event("LLM_GEMINI_FAILED", {"error": str(e), "falling_back": "groq"})

        # 2. Fallback to Groq
        if self.groq_key:
            try:
                groq_client = self.get_groq_client()
                if groq_client:
                    messages = []
                    if system:
                        messages.append({"role": "system", "content": system})
                    messages.append({"role": "user", "content": prompt})

                    chat = groq_client.chat.completions.create(
                        model=self.GROQ_MODEL,
                        messages=messages,
                        max_tokens=max_tokens,
                        temperature=0.3
                    )
                    text = chat.choices[0].message.content.strip()
                    if text:
                        logger.log_event("LLM_GROQ_FALLBACK_SUCCESS", {"tokens": len(text.split())})
                        return text
            except Exception as e:
                logger.log_event("LLM_GROQ_FAILED", {"error": str(e)})

        logger.log_event("LLM_ALL_PROVIDERS_FAILED", {})
        return ""


# Singleton instance
llm_config = LLMConfig()
