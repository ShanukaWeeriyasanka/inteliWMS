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
    # Local frontends only by default ("*" with credentials let any site call the service from a browser)
    CORS_ORIGINS: list = os.getenv("KNOWLEDGE_CORS_ORIGINS",
                                   "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173").split(",")
    # Shared secret for every endpoint except /health (header X-API-Key). Unset = open, for local development
    # only; set it wherever the service is reachable by anyone else.
    SERVICE_API_KEY: str = os.getenv("KNOWLEDGE_SERVICE_API_KEY", "")

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

    # No numeric defaults: when a question gives no tier count or speed, the documented limit is stated
    # instead of checking an assumed value (compliance.evaluate_compliance_query).

    # ─── Retrieval relevance (a chunk below these is "no matching SOP", not an answer) ─────
    # ChromaDB default embedding, L2 distance on normalised vectors: d = 2 − 2·cos, so 1.3 ≈ cosine 0.35
    RAG_MAX_DISTANCE: float = float(os.getenv("KNOWLEDGE_RAG_MAX_DISTANCE", "1.3"))
    # Keyword fallback: share of the question's content words found in the chunk or its title
    RAG_MIN_KEYWORD_SCORE: float = float(os.getenv("KNOWLEDGE_RAG_MIN_KEYWORD_SCORE", "0.4"))


knowledge_config = KnowledgeAgentConfig()
