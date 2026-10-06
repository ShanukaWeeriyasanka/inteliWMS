"""
In-process metrics with Prometheus text exposition (served at GET /metrics).

Labels must stay low-cardinality: thread, user, request, trace and session ids,
SKUs and query text are rejected at definition time, and each metric caps the
number of label combinations it will track. Counters are per process.
"""
import math
import threading
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

FORBIDDEN_LABELS = {"thread_id", "user_id", "request_id", "trace_id", "span_id", "session_id", "sku", "query"}
MAX_SERIES_PER_METRIC = 200
OVERFLOW_VALUE = "other"

DEFAULT_BUCKETS_S = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0)


class _Metric:
    kind = "untyped"

    def __init__(self, name: str, help_text: str, labelnames: Sequence[str] = ()):
        bad = FORBIDDEN_LABELS.intersection(labelnames)
        if bad:
            raise ValueError(f"metric {name}: high-cardinality label(s) not allowed: {sorted(bad)}")
        self.name = name
        self.help = help_text
        self.labelnames: Tuple[str, ...] = tuple(labelnames)
        self._lock = threading.Lock()

    def _key(self, labels: Dict[str, object], existing: Iterable[Tuple[str, ...]]) -> Tuple[str, ...]:
        unknown = set(labels) - set(self.labelnames)
        if unknown:
            raise ValueError(f"metric {self.name}: unknown label(s) {sorted(unknown)}")
        key = tuple(str(labels.get(n, "")) for n in self.labelnames)
        existing = set(existing)
        if key not in existing and len(existing) >= MAX_SERIES_PER_METRIC:
            key = tuple(OVERFLOW_VALUE for _ in self.labelnames)
        return key

    def _fmt_labels(self, key: Tuple[str, ...], extra: Optional[Dict[str, str]] = None) -> str:
        pairs = list(zip(self.labelnames, key)) + list((extra or {}).items())
        if not pairs:
            return ""
        body = ",".join(f'{k}="{_escape(v)}"' for k, v in pairs)
        return "{" + body + "}"


def _escape(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


class Counter(_Metric):
    kind = "counter"

    def __init__(self, name: str, help_text: str, labelnames: Sequence[str] = ()):
        super().__init__(name, help_text, labelnames)
        self._values: Dict[Tuple[str, ...], float] = {}

    def inc(self, amount: float = 1.0, **labels: object) -> None:
        with self._lock:
            key = self._key(labels, self._values.keys())
            self._values[key] = self._values.get(key, 0.0) + amount

    def value(self, **labels: object) -> float:
        key = tuple(str(labels.get(n, "")) for n in self.labelnames)
        return self._values.get(key, 0.0)

    def render(self) -> List[str]:
        with self._lock:
            return [f"{self.name}{self._fmt_labels(k)} {_num(v)}" for k, v in sorted(self._values.items())]


class Histogram(_Metric):
    kind = "histogram"

    def __init__(self, name: str, help_text: str, labelnames: Sequence[str] = (),
                 buckets: Sequence[float] = DEFAULT_BUCKETS_S):
        super().__init__(name, help_text, labelnames)
        self.buckets = tuple(sorted(buckets))
        self._series: Dict[Tuple[str, ...], Dict[str, object]] = {}

    def observe(self, value: float, **labels: object) -> None:
        with self._lock:
            key = self._key(labels, self._series.keys())
            s = self._series.setdefault(key, {"counts": [0] * len(self.buckets), "sum": 0.0, "count": 0})
            for i, bound in enumerate(self.buckets):
                if value <= bound:
                    s["counts"][i] += 1
            s["sum"] += value
            s["count"] += 1

    def count(self, **labels: object) -> int:
        key = tuple(str(labels.get(n, "")) for n in self.labelnames)
        return int(self._series.get(key, {}).get("count", 0))

    def render(self) -> List[str]:
        lines = []
        with self._lock:
            for key, s in sorted(self._series.items()):
                for bound, c in zip(self.buckets, s["counts"]):
                    lines.append(f"{self.name}_bucket{self._fmt_labels(key, {'le': _num(bound)})} {c}")
                lines.append(f"{self.name}_bucket{self._fmt_labels(key, {'le': '+Inf'})} {s['count']}")
                lines.append(f"{self.name}_sum{self._fmt_labels(key)} {_num(s['sum'])}")
                lines.append(f"{self.name}_count{self._fmt_labels(key)} {s['count']}")
        return lines


def _num(v: float) -> str:
    if isinstance(v, float) and math.isinf(v):
        return "+Inf"
    return f"{v:g}" if isinstance(v, float) else str(v)


class Registry:
    def __init__(self):
        self._metrics: Dict[str, _Metric] = {}

    def register(self, metric: _Metric) -> _Metric:
        if metric.name in self._metrics:
            return self._metrics[metric.name]
        self._metrics[metric.name] = metric
        return metric

    def counter(self, name: str, help_text: str, labelnames: Sequence[str] = ()) -> Counter:
        return self.register(Counter(name, help_text, labelnames))  # type: ignore[return-value]

    def histogram(self, name: str, help_text: str, labelnames: Sequence[str] = (),
                  buckets: Sequence[float] = DEFAULT_BUCKETS_S) -> Histogram:
        return self.register(Histogram(name, help_text, labelnames, buckets))  # type: ignore[return-value]

    def render(self) -> str:
        out: List[str] = []
        for m in self._metrics.values():
            out.append(f"# HELP {m.name} {m.help}")
            out.append(f"# TYPE {m.name} {m.kind}")
            out.extend(m.render())
        return "\n".join(out) + "\n"


REGISTRY = Registry()

# ── Metrics used across the request path ────────────────────────────────────
HTTP_REQUESTS = REGISTRY.counter("http_requests_total", "HTTP requests handled", ["route", "method", "status"])
HTTP_DURATION = REGISTRY.histogram("http_request_duration_seconds", "HTTP request latency", ["route", "method"])

ROUTING_DECISIONS = REGISTRY.counter(
    "routing_decisions_total", "Coordinator routing decisions", ["domain", "source"])
ROUTING_FAILURES = REGISTRY.counter(
    "routing_failures_total", "Routing problems (LLM errors, low confidence escalations)", ["reason"])

AGENT_REQUESTS = REGISTRY.counter("agent_requests_total", "Specialist agent requests", ["agent", "outcome"])
AGENT_DURATION = REGISTRY.histogram("agent_duration_seconds", "Specialist agent latency", ["agent"])

INVENTORY_REQUESTS = REGISTRY.counter(
    "inventory_requests_total", "Inventory agent requests by outcome and sub-intent", ["outcome", "sub_intent"])

MCP_TOOL_CALLS = REGISTRY.counter(
    "mcp_tool_calls_total", "MCP tool calls by outcome", ["server", "tool", "outcome", "transport"])
MCP_TOOL_DURATION = REGISTRY.histogram(
    "mcp_tool_duration_seconds", "MCP tool call latency", ["server", "tool", "transport"])
MCP_TOOL_RETRIES = REGISTRY.counter("mcp_tool_retries_total", "MCP tool call retries", ["server", "tool"])
MCP_TOOL_TIMEOUTS = REGISTRY.counter("mcp_tool_timeouts_total", "MCP tool calls that timed out", ["server", "tool"])
MCP_TOOL_REJECTIONS = REGISTRY.counter(
    "mcp_tool_rejections_total", "Tool calls blocked by the per-agent allowlist", ["agent", "reason"])
MCP_ERRORS = REGISTRY.counter("mcp_errors_total", "MCP connection / discovery / protocol errors", ["server", "kind"])

THREAD_OPERATIONS = REGISTRY.counter("thread_operations_total", "Chat thread operations", ["op", "outcome"])

# What decided each step: a code rule, the LLM, or a deterministic fallback (rule ids are a fixed set)
DECISIONS = REGISTRY.counter(
    "decisions_total", "Decisions by stage, decider (rule | llm | fallback) and rule id", ["stage", "decided_by", "rule"])
LLM_CALLS = REGISTRY.counter(
    "llm_calls_total", "LLM calls by purpose and outcome (ok | empty | timeout | error | unavailable)",
    ["purpose", "outcome"])
LLM_DURATION = REGISTRY.histogram("llm_call_duration_seconds", "LLM call latency", ["purpose"])
