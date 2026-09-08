from google import genai
from config.settings import settings

class LLMConfig:
    """Centralized LLM provider configuration."""
    
    def __init__(self):
        self.primary_provider = settings.LLM_PRIMARY
        self.gemini_key = settings.GEMINI_API_KEY
    
    def get_client(self):
        """Returns the configured Gemini client."""
        if not self.gemini_key:
            raise ValueError("GEMINI_API_KEY not found in .env. Please check your .env file.")
        
        # Initialize official Google GenAI client
        return genai.Client(api_key=self.gemini_key)

# Singleton instance
llm_config = LLMConfig()
