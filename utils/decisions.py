"""
Decision records — which step decided what, and how.

Every branching point in a request records one Decision:
  decided_by = "rule"      a code rule decided (rule_id names the rule)
             = "llm"       the LLM's suggestion was validated and accepted
             = "fallback"  the LLM was unusable (invalid / low confidence / timeout / unavailable)
                           and a fixed rule decided instead
Each record is logged as a DECISION event (no message text), counted in
decisions_total{stage, decided_by, rule}, and collected per request so the API
response can show the full decision path (routing.decisions).
"""
from contextvars import ContextVar, Token
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from utils.logger import StructuredLogger
from utils.metrics import DECISIONS

RULE, LLM, FALLBACK = "rule", "llm", "fallback"

logger = StructuredLogger("decisions")
_collected: ContextVar[Optional[List[Dict[str, Any]]]] = ContextVar("decisions", default=None)


@dataclass
class Decision:
    stage: str
    outcome: str
    decided_by: str
    rule_id: Optional[str] = None
    llm_consulted: bool = False
    llm_status: Optional[str] = None
    confidence: Optional[float] = None


def start_collecting() -> Token:
    """Begin collecting this request's decisions (worker threads share the same list)."""
    return _collected.set([])


def stop_collecting(token: Token) -> None:
    _collected.reset(token)


def collected() -> List[Dict[str, Any]]:
    return list(_collected.get() or [])


def record_decision(stage: str, outcome: str, decided_by: str, rule_id: Optional[str] = None, *,
                    llm_consulted: bool = False, llm_status: Optional[str] = None,
                    confidence: Optional[float] = None, **details: Any) -> Decision:
    decision = Decision(stage=stage, outcome=str(outcome), decided_by=decided_by, rule_id=rule_id,
                        llm_consulted=llm_consulted, llm_status=llm_status,
                        confidence=round(confidence, 3) if confidence is not None else None)
    DECISIONS.inc(stage=stage, decided_by=decided_by, rule=rule_id or "none")
    logger.log_event("DECISION", {**asdict(decision), **details},
                     level="WARNING" if decided_by == FALLBACK else "INFO")
    bucket = _collected.get()
    if bucket is not None:
        bucket.append(asdict(decision))
    return decision
