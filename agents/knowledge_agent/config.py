"""
Configuration settings for Knowledge Agent.
Centralizes all paths, constants, model names, compliance rule constants,
and service metadata to avoid hardcoding anywhere in feature modules.
"""
import os
from pathlib import Path
from config.settings import settings

# Directory references
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = settings.BASE_DIR
DATA_DIR = settings.DATA_DIR


class KnowledgeAgentConfig:
    """Agent-specific settings and operational parameters."""

    # Model configuration
    MODEL_NAME: str = os.getenv("KNOWLEDGE_AGENT_MODEL", settings.KNOWLEDGE_AGENT_MODEL)

    # Storage and paths
    CHROMA_PERSIST_DIR: Path = Path(os.getenv("CHROMA_PERSIST_DIR", str(DATA_DIR / "chroma_db")))
    SEED_SOPS_PATH: Path = CURRENT_DIR / "data" / "sops.json"
    ONTOLOGY_PATH: Path = Path(os.getenv("ONTOLOGY_PATH", str(DATA_DIR / "warehouse_ontology.json")))

    # ChromaDB Vector Store settings
    COLLECTION_NAME: str = os.getenv("KNOWLEDGE_COLLECTION_NAME", "warehouse_knowledge")
    DEFAULT_RAG_TOP_K: int = int(os.getenv("KNOWLEDGE_RAG_TOP_K", "2"))
    MIN_PARAGRAPH_LENGTH: int = int(os.getenv("KNOWLEDGE_MIN_CHUNK_LEN", "30"))

    # Location resolution settings
    LOCATION_SEARCH_LIMIT: int = int(os.getenv("KNOWLEDGE_LOC_SEARCH_LIMIT", "5"))

    # Microservice server settings
    HOST: str = settings.KNOWLEDGE_SERVER_HOST
    PORT: int = settings.KNOWLEDGE_SERVER_PORT
    SERVICE_VERSION: str = os.getenv("KNOWLEDGE_SERVICE_VERSION", "1.1.0")
    CORS_ORIGINS: list = os.getenv("KNOWLEDGE_CORS_ORIGINS", "*").split(",")

    # ─── Compliance Rule Constants (SOP-STG-002) ─────────────────────────────
    # Zone pallet stacking tier limits  (overridable via env for new warehouses)
    ZONE_STACKING_LIMITS: dict = {
        "zone a": int(os.getenv("COMPLIANCE_STACK_ZONE_A", "3")),   # Heavy Goods
        "zone c": int(os.getenv("COMPLIANCE_STACK_ZONE_C", "2")),   # High Turnover
        "default": int(os.getenv("COMPLIANCE_STACK_DEFAULT", "3")),
    }

    # Vehicle speed limits by location type  (SOP-SAF-003)
    SPEED_LIMITS: dict = {
        "aisle":      float(os.getenv("COMPLIANCE_SPEED_AISLE", "5")),       # 5 mph (8 km/h)
        "corridor":   float(os.getenv("COMPLIANCE_SPEED_CORRIDOR", "8")),    # 8 mph (12.8 km/h)
        "cross-dock": float(os.getenv("COMPLIANCE_SPEED_CROSSDOCK", "8")),
    }

    # Fallback defaults when NLP parser cannot extract a numeric value
    COMPLIANCE_DEFAULT_TIERS: float = float(os.getenv("COMPLIANCE_DEFAULT_TIERS", "4"))
    COMPLIANCE_DEFAULT_SPEED: float = float(os.getenv("COMPLIANCE_DEFAULT_SPEED", "6"))


knowledge_config = KnowledgeAgentConfig()
