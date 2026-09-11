import logging
import json
import os
from datetime import datetime, timezone
from config.settings import settings

# Make sure logs directory exists
os.makedirs("logs", exist_ok=True)

# Configure standard logger
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/app.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

class StructuredLogger:
    """Outputs structured JSON logs for audit trails & agent decisions."""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
    
    def log_event(self, event_type: str, details: dict):
        """Log an event as structured JSON."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            **details
        }
        self.logger.info(json.dumps(entry))
    
    def log_agent_decision(self, agent_name: str, input_msg: str, decision: str, reasoning: str):
        """Logs what an agent decided and why (for audit and evaluation)."""
        self.log_event("AGENT_DECISION", {
            "agent": agent_name,
            "input": input_msg,
            "decision": decision,
            "reasoning": reasoning
        })
