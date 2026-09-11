import os
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

from pathlib import Path

# Base workspace directories
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

class Settings:
    """Centralized configuration loaded from environment variables."""
    
    # Base paths
    BASE_DIR: Path = BASE_DIR
    DATA_DIR: Path = DATA_DIR
    CHROMA_PERSIST_DIR: str = os.getenv("CHROMA_PERSIST_DIR", str(DATA_DIR / "chroma_db"))
    
    # LLM Settings
    LLM_PRIMARY: str = os.getenv("LLM_PRIMARY", "gemini")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
    KNOWLEDGE_AGENT_MODEL: str = os.getenv("KNOWLEDGE_AGENT_MODEL", "gemini/gemini-2.5-flash")
    
    # Service Ports
    COORDINATOR_PORT: int = int(os.getenv("PORT", "8000"))
    KNOWLEDGE_SERVER_HOST: str = os.getenv("KNOWLEDGE_SERVER_HOST", "0.0.0.0")
    KNOWLEDGE_SERVER_PORT: int = int(os.getenv("KNOWLEDGE_SERVER_PORT", "8002"))
    
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

