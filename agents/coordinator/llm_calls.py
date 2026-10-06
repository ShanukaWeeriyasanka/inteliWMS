"""
Bounded, observable LLM calls for the coordinator.

The LLM is only consulted after every code rule has had its turn, and only for
three purposes:
  normalize — rewrite broken text so the rules can try again
  classify  — suggest one of the four domains for free text no rule matched
  reply     — word a reply to unrecognised small talk
Each call runs on a small shared thread pool with a hard timeout, and returns a
status instead of raising, so the caller's deterministic fallback always applies:
  ok | empty | timeout | error | unavailable (no API key configured)
Every call is counted (llm_calls_total, llm_call_duration_seconds), traced
(span llm.call) and logged (LLM_CALL) without the prompt or the completion.
"""
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from typing import Any, Callable, Optional, Tuple

from config.settings import settings
from utils import request_context
from utils.logger import StructuredLogger
from utils.metrics import LLM_CALLS, LLM_DURATION
from utils.tracing import span

OK, EMPTY, TIMEOUT, ERROR, UNAVAILABLE = "ok", "empty", "timeout", "error", "unavailable"

logger = StructuredLogger(__name__)
_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="llm")


def _run(correlation: dict, fn: Callable[[], Any]) -> Any:
    tokens = request_context.bind(**correlation)
    try:
        return fn()
    finally:
        request_context.reset(tokens)


def call_llm(purpose: str, fn: Callable[[], Any], *, available: bool = True,
             timeout_s: Optional[float] = None) -> Tuple[str, Any]:
    """Run `fn` (the provider call) with a timeout. Returns (status, value)."""
    if not available:
        LLM_CALLS.inc(purpose=purpose, outcome=UNAVAILABLE)
        logger.log_event("LLM_CALL", {"purpose": purpose, "outcome": UNAVAILABLE, "duration_ms": 0})
        return UNAVAILABLE, None

    timeout = timeout_s or settings.LLM_TIMEOUT_S
    start = time.perf_counter()
    error_type = None
    with span("llm.call", purpose=purpose) as sp:
        future = _POOL.submit(_run, request_context.current(), fn)
        try:
            value = future.result(timeout=timeout)
            status = OK if (value.strip() if isinstance(value, str) else value) else EMPTY
        except FutureTimeout:
            # The provider call keeps running in its pool thread, but nobody waits for it
            status, value = TIMEOUT, None
        except Exception as exc:
            status, value, error_type = ERROR, None, type(exc).__name__
        sp.set(status="error" if status in (TIMEOUT, ERROR) else "ok", outcome=status)

    duration = time.perf_counter() - start
    LLM_CALLS.inc(purpose=purpose, outcome=status)
    LLM_DURATION.observe(duration, purpose=purpose)
    logger.log_event("LLM_CALL", {"purpose": purpose, "outcome": status, "duration_ms": round(duration * 1000, 2),
                                  "timeout_s": timeout, "error_type": error_type},
                     level="WARNING" if status in (TIMEOUT, ERROR) else "INFO")
    return status, value
