"""
Per-request correlation context (request_id, trace_id, span_id, thread_id, agent).

Held in contextvars so every log line, span and MCP call made while serving a
request carries the same identifiers without passing them through every function.
The four ids are deliberately separate:
  - request_id: one HTTP request (X-Request-ID)
  - trace_id:   one distributed trace (W3C traceparent), spans hang off it
  - thread_id:  one chat conversation, stable across many requests
  - agent:      the agent currently doing the work
Kept free of logger imports so utils.logger can depend on it.
"""
from contextvars import ContextVar, Token
from typing import Any, Dict, List, Optional, Tuple

FIELDS = ("request_id", "trace_id", "span_id", "thread_id", "agent")

_vars: Dict[str, ContextVar] = {name: ContextVar(name, default=None) for name in FIELDS}


def bind(**values: Optional[str]) -> List[Tuple[ContextVar, Token]]:
    """Set some context fields; returns tokens for reset()."""
    tokens = []
    for name, value in values.items():
        if name not in _vars:
            raise KeyError(f"unknown request context field '{name}'")
        tokens.append((_vars[name], _vars[name].set(value)))
    return tokens


def reset(tokens: List[Tuple[ContextVar, Token]]) -> None:
    for var, token in reversed(tokens):
        try:
            var.reset(token)
        except ValueError:
            # Token created in another context (e.g. a worker thread copy) — just clear it
            var.set(None)


def get(name: str) -> Optional[str]:
    return _vars[name].get()


def current() -> Dict[str, Any]:
    """Non-empty correlation fields, for log lines and response bodies."""
    return {name: var.get() for name, var in _vars.items() if var.get() is not None}
