from google import genai
from config.settings import settings

class LLMConfig:
    """Centralized LLM provider configuration."""
    
    def __init__(self):
        self.primary_provider = settings.LLM_PRIMARY
        self.gemini_key = settings.GEMINI_API_KEY
        self.fulfillment_gemini_key = settings.FULFILLMENT_GEMINI_API_KEY
    
    def get_client(self):
        """Returns the Coordinator Gemini client using GEMINI_API_KEY."""
        if not self.gemini_key:
            raise ValueError("GEMINI_API_KEY not found in .env. Please check your .env file.")
        
        # Initialize official Google GenAI client
        return genai.Client(api_key=self.gemini_key)

    def get_fulfillment_client(self):
        """Returns the Fulfillment-specific Gemini client using FULFILLMENT_GEMINI_API_KEY."""
        if not self.fulfillment_gemini_key:
            raise ValueError("FULFILLMENT_GEMINI_API_KEY not found in .env. Please check your .env file.")
        
        return genai.Client(api_key=self.fulfillment_gemini_key)

# Singleton instance
llm_config = LLMConfig()
