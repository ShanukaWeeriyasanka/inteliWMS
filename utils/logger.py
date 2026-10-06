import logging
import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Union

from config.settings import settings
from utils import request_context

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


def _apply_logger_levels(spec: str) -> None:
    """LOG_LEVELS="mcp=WARNING,agents.inventory_agent=DEBUG" → per-logger levels."""
    for part in (spec or "").split(","):
        name, _, level = part.partition("=")
        if name.strip() and level.strip():
            logging.getLogger(name.strip()).setLevel(level.strip().upper())


_apply_logger_levels(settings.LOG_LEVELS)

# ── Redaction ────────────────────────────────────────────────────────────────

_SECRET_KEY = re.compile(r"(token|password|passwd|secret|authorization|api[_-]?key|credential|jwt|cookie)", re.I)
# Free text (user questions, answers, raw payloads) — omitted unless LOG_INCLUDE_CONTENT=true
_CONTENT_KEYS = {
    "query", "message", "response", "original_query", "normalized_query", "query_preview",
    "input", "content", "context", "text", "original", "normalized", "falling_back_to_original",
    "arguments", "payload", "query_text", "llm_reasoning", "prompt", "completion",
}
_SECRET_VALUE_PATTERNS = [
    (re.compile(r"eyJ[\w-]+\.[\w-]+\.[\w-]+"), "[REDACTED_JWT]"),
    (re.compile(r"(?i)bearer\s+[\w.~+/=-]+"), "Bearer [REDACTED]"),
    (re.compile(r"(?i)(access_token|token|api_key|apikey|password)=([^&\s]+)"), r"\1=[REDACTED]"),
    (re.compile(r"(://[^:/@\s]+):([^@\s]+)@"), r"\1:[REDACTED]@"),  # credentials inside URLs
]
_MAX_DEPTH = 4


def redact_text(value: str) -> str:
    for pattern, repl in _SECRET_VALUE_PATTERNS:
        value = pattern.sub(repl, value)
    limit = settings.LOG_MAX_FIELD_LEN
    if limit and len(value) > limit:
        value = value[:limit] + f"…[+{len(value) - limit} chars]"
    return value


def redact(value: Any, key: str = "", depth: int = 0) -> Any:
    """Recursively scrub secrets and (by default) free-text content from a log payload."""
    if key and _SECRET_KEY.search(key) and not key.endswith(("_count", "_len")):
        return "[REDACTED]" if value not in (None, "") else value
    if key in _CONTENT_KEYS and not settings.LOG_INCLUDE_CONTENT and value not in (None, ""):
        size = len(value) if isinstance(value, (str, list, dict)) else None
        return {"omitted": True, "len": size} if size is not None else {"omitted": True}
    if depth >= _MAX_DEPTH:
        return "[TRUNCATED]"
    if isinstance(value, dict):
        return {k: redact(v, str(k), depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v, "", depth + 1) for v in value[:50]]
    if isinstance(value, str):
        return redact_text(value)
    return value


class _AccessLogRedactionFilter(logging.Filter):
    """uvicorn.access prints full paths; the twin SSE stream carries ?access_token=<JWT>."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(redact_text(a) if isinstance(a, str) else a for a in record.args)
        if isinstance(record.msg, str):
            record.msg = redact_text(record.msg)
        return True


logging.getLogger("uvicorn.access").addFilter(_AccessLogRedactionFilter())


class StructuredLogger:
    """Outputs structured JSON logs for audit trails & agent decisions."""

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)

    def log_event(self, event_type: str, details: dict, level: Union[int, str] = logging.INFO):
        """Log an event as structured JSON, with correlation ids and secrets redacted."""
        lvl = logging.getLevelName(level.upper()) if isinstance(level, str) else level
        if not self.logger.isEnabledFor(lvl):
            return
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            **request_context.current(),
            **redact(details or {}),
        }
        self.logger.log(lvl, json.dumps(entry, default=str, ensure_ascii=False))

    def log_agent_decision(self, agent_name: str, input_msg: str, decision: str, reasoning: str):
        """Logs what an agent decided and why (for audit and evaluation)."""
        self.log_event("AGENT_DECISION", {
            "agent": agent_name,
            "input": input_msg,
            "decision": decision,
            "reasoning": reasoning
        })
