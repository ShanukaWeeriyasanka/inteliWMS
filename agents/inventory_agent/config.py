import os
from pathlib import Path
from dataclasses import dataclass
from config.settings import settings

# Base directory for the inventory agent
INVENTORY_AGENT_DIR = Path(__file__).resolve().parent

@dataclass(frozen=True)
class InventoryConfig:
    """Centralized configuration for the Inventory Specialist Agent."""
    
    # Microservice Server Networking
    HOST: str = os.getenv("INVENTORY_SERVER_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("INVENTORY_SERVER_PORT", "8001"))
    
    # LLM Settings (Inherited from global settings with agent overrides)
    MODEL_NAME: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    TEMPERATURE: float = float(os.getenv("INVENTORY_LLM_TEMPERATURE", "0.2"))
    MAX_TOKENS: int = int(os.getenv("INVENTORY_MAX_TOKENS", "1024"))
    
    # Data Paths
    SEED_DATA_PATH: Path = INVENTORY_AGENT_DIR / "data" / "inventory_seed.json"
    
    # Inventory Thresholds & Business Rules
    DEFAULT_SAFETY_STOCK: int = int(os.getenv("INVENTORY_DEFAULT_SAFETY_STOCK", "15"))
    DEFAULT_REORDER_POINT: int = int(os.getenv("INVENTORY_DEFAULT_REORDER_POINT", "30"))
    DEFAULT_REORDER_QUANTITY: int = int(os.getenv("INVENTORY_DEFAULT_REORDER_QTY", "100"))
    LOW_STOCK_RATIO_ALERT: float = float(os.getenv("INVENTORY_LOW_STOCK_RATIO", "0.25"))
    MAX_QUERY_RESULTS: int = int(os.getenv("INVENTORY_MAX_RESULTS", "10"))
    REQUEST_TIMEOUT_SECONDS: int = int(os.getenv("INVENTORY_TIMEOUT_SEC", "15"))

    # Warehouse Digital Twin — choosing between resolve_product / resolve_location candidates
    TWIN_ENABLED: bool = os.getenv("INVENTORY_TWIN_ENABLED", "true").lower() == "true"
    TWIN_COMMAND_VERSION: str = os.getenv("INVENTORY_TWIN_COMMAND_VERSION", "1.1")
    TWIN_PICK_MIN_SCORE: float = float(os.getenv("INVENTORY_TWIN_PICK_MIN_SCORE", "0.9"))
    TWIN_PICK_MARGIN: float = float(os.getenv("INVENTORY_TWIN_PICK_MARGIN", "0.1"))
    TWIN_DEFAULT_PREFER: str = os.getenv("INVENTORY_TWIN_DEFAULT_PREFER", "lift")
    TWIN_MAX_CANDIDATES: int = int(os.getenv("INVENTORY_TWIN_MAX_CANDIDATES", "5"))
    TWIN_ANSWER_STEPS: int = int(os.getenv("INVENTORY_TWIN_ANSWER_STEPS", "3"))

# Global singleton
inventory_config = InventoryConfig()
