import os
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

class Settings:
    """Centralized configuration loaded from environment variables."""
    
    # LLM Settings
    LLM_PRIMARY: str = os.getenv("LLM_PRIMARY", "gemini")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
    
    # Database (Defaults to SQLite for local development without Docker)
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./intelliwms.db")
    
    # Security / JWT
    JWT_SECRET: str = os.getenv("JWT_SECRET", "dev-secret-minimum-32-characters-long")
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# Singleton instance for the app to import
settings = Settings()

# Validation
if not settings.DATABASE_URL:
    raise ValueError("DATABASE_URL is not set in .env")
