from pathlib import Path
import os
from dotenv import load_dotenv

# Base workspace directories
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

# Load variables from .env file
load_dotenv(dotenv_path=BASE_DIR / ".env")

class Settings:
    """Centralized configuration loaded from environment variables."""
    
    # Base paths
    BASE_DIR: Path = BASE_DIR
    DATA_DIR: Path = DATA_DIR
    CHROMA_PERSIST_DIR: str = os.getenv("CHROMA_PERSIST_DIR", str(DATA_DIR / "chroma_db"))
    
    # LLM Settings
    LLM_PRIMARY: str = os.getenv("LLM_PRIMARY", "gemini")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    FULFILLMENT_GEMINI_API_KEY: str = os.getenv("FULFILLMENT_GEMINI_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
    KNOWLEDGE_AGENT_MODEL: str = os.getenv("KNOWLEDGE_AGENT_MODEL", "gemini/gemini-2.5-flash")
    
    # Service Ports
    COORDINATOR_PORT: int = int(os.getenv("PORT", "8000"))
    KNOWLEDGE_SERVER_HOST: str = os.getenv("KNOWLEDGE_SERVER_HOST", "0.0.0.0")
    KNOWLEDGE_SERVER_PORT: int = int(os.getenv("KNOWLEDGE_SERVER_PORT", "8002"))
    
    # Database (Defaults to SQLite for local development without Docker)
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./intelliwms.db")
    
    # Warehouse Digital Twin (needs PostgreSQL; disabled when no Postgres URL is set)
    TWIN_DATABASE_URL: str = os.getenv("TWIN_DATABASE_URL", "")
    TWIN_DB_SCHEMA: str = os.getenv("TWIN_DB_SCHEMA", "twin")
    TWIN_SQL_DIR: Path = BASE_DIR / "database" / "twin"
    TWIN_AUTO_SETUP: bool = os.getenv("TWIN_AUTO_SETUP", "true").lower() == "true"
    TWIN_NOTIFY_CHANNEL: str = os.getenv("TWIN_NOTIFY_CHANNEL", "twin_changes")
    TWIN_SSE_KEEPALIVE_S: float = float(os.getenv("TWIN_SSE_KEEPALIVE_S", "15"))
    TWIN_LISTEN_RETRY_S: float = float(os.getenv("TWIN_LISTEN_RETRY_S", "3"))

    # Security / JWT
    JWT_SECRET: str = os.getenv("JWT_SECRET", "dev-secret-minimum-32-characters-long")

    # Subscription plan switching without a payment gateway (university demo only).
    # Upgrades through POST /auth/set-plan are refused unless APP_ENV=development AND
    # DEMO_PLAN_SWITCH_ENABLED=true, and then only for the listed accounts / roles.
    # Downgrades (to a lower or equal tier) never grant anything and are always allowed.
    APP_ENV: str = os.getenv("APP_ENV", "production").strip().lower()
    DEMO_PLAN_SWITCH_ENABLED: bool = os.getenv("DEMO_PLAN_SWITCH_ENABLED", "false").strip().lower() == "true"
    DEMO_PLAN_SWITCH_USERS: frozenset = frozenset(
        u.strip().lower() for u in os.getenv("DEMO_PLAN_SWITCH_USERS", "").split(",") if u.strip())
    DEMO_PLAN_SWITCH_ROLES: frozenset = frozenset(
        r.strip().lower() for r in os.getenv("DEMO_PLAN_SWITCH_ROLES", "admin").split(",") if r.strip())

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    # Per-logger overrides, e.g. "mcp=WARNING,agents.inventory_agent=DEBUG"
    LOG_LEVELS: str = os.getenv("LOG_LEVELS", "mcp=WARNING,httpx=WARNING")
    # Message / response text is omitted from logs unless this is true
    LOG_INCLUDE_CONTENT: bool = os.getenv("LOG_INCLUDE_CONTENT", "false").lower() == "true"
    LOG_MAX_FIELD_LEN: int = int(os.getenv("LOG_MAX_FIELD_LEN", "500"))

    # Metrics (GET /metrics, Prometheus text format; optional bearer token)
    METRICS_ENABLED: bool = os.getenv("METRICS_ENABLED", "true").lower() == "true"
    METRICS_TOKEN: str = os.getenv("METRICS_TOKEN", "")

    # Upper bound for one LLM call made by the coordinator (rewrite / classify / reply text)
    LLM_TIMEOUT_S: float = float(os.getenv("LLM_TIMEOUT_S", "8"))

    # Chat threads
    CHAT_HISTORY_CONTEXT_TURNS: int = int(os.getenv("CHAT_HISTORY_CONTEXT_TURNS", "6"))
    CHAT_MAX_MESSAGE_CHARS: int = int(os.getenv("CHAT_MAX_MESSAGE_CHARS", "4000"))

# Singleton instance for the app to import
settings = Settings()

# Validation
if not settings.DATABASE_URL:
    raise ValueError("DATABASE_URL is not set in .env")

