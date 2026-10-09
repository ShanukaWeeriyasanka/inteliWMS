"""
Intent Classifier for IntelliWMS Coordinator Agent (Task 2).
Classifies warehouse queries into:
- INVENTORY
- FULFILLMENT
- KNOWLEDGE
- COORDINATOR  (meta/system questions answered directly by the coordinator)

Rules decide first, in code. Every rule has an id (e.g. "inventory.strong"), so each
routing decision can be traced to the exact rule that made it. The LLM is consulted
only when no rule decides; it may only *suggest* one of the four domains as strict
JSON, and code accepts the suggestion only when it is valid and confident. Anything
else (invalid output, low confidence, timeout, no API key) falls back to a fixed rule:
the weak hint's domain if one matched, otherwise a clarification question.
"""
import json
import re
from typing import Any, List, Optional, Tuple

from agents.coordinator.llm_calls import OK, UNAVAILABLE, call_llm
from config.llm_config import llm_config
from config.prompts import COORDINATOR_SYSTEM_PROMPT
from utils.logger import StructuredLogger
from utils.metrics import ROUTING_FAILURES

logger = StructuredLogger(__name__)

RULE, LLM, FALLBACK = "rule", "llm", "fallback"


class IntentResult(tuple):
    """
    Hybrid Result object supporting both 3-tuple unpacking:
    (intent, confidence, reasoning) = classifier.classify(...)
    and dictionary access: res["domain"], res.get("confidence")
    """
    def __new__(cls, intent: str, confidence: float, reasoning: str, source: str = "heuristic", *,
                rule_id: Optional[str] = None, decided_by: Optional[str] = None,
                llm_status: Optional[str] = None, llm_consulted: bool = False):
        obj = super().__new__(cls, (intent, float(confidence), str(reasoning)))
        obj._source = source  # meta | social | heuristic | context | llm | llm_low_confidence | fallback
        obj._rule_id = rule_id
        obj._decided_by = decided_by or (LLM if source == "llm" else
                                         FALLBACK if source in ("fallback", "llm_low_confidence") else RULE)
        obj._llm_status = llm_status
        obj._llm_consulted = llm_consulted
        return obj

    @property
    def source(self) -> str:
        return getattr(self, "_source", "heuristic")

    @property
    def rule_id(self) -> Optional[str]:
        return getattr(self, "_rule_id", None)

    @property
    def decided_by(self) -> str:
        return getattr(self, "_decided_by", RULE)

    @property
    def llm_status(self) -> Optional[str]:
        return getattr(self, "_llm_status", None)

    @property
    def llm_consulted(self) -> bool:
        return getattr(self, "_llm_consulted", False)

    @property
    def intent(self) -> str:
        return self[0]

    @property
    def domain(self) -> str:
        return self[0]

    @property
    def confidence(self) -> float:
        return self[1]

    @property
    def reasoning(self) -> str:
        return self[2]

    def get(self, key: str, default: Any = None) -> Any:
        mapping = {
            "intent": self.intent,
            "domain": self.domain,
            "confidence": self.confidence,
            "reasoning": self.reasoning
        }
        return mapping.get(key, default)

    def __getitem__(self, item):
        if isinstance(item, str):
            val = self.get(item)
            if val is None:
                raise KeyError(item)
            return val
        return super().__getitem__(item)

    def to_dict(self) -> dict:
        return {
            "domain": self.domain,
            "intent": self.intent,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "source": self.source,
            "rule_id": self.rule_id,
            "decided_by": self.decided_by,
            "llm_status": self.llm_status,
            "llm_consulted": self.llm_consulted,
        }


def _any(patterns, text: str) -> bool:
    return any(re.search(p, text) for p in patterns)


# ── Rule patterns ────────────────────────────────────────────────────────────

# Ids that always mean a real warehouse question, never a meta/greeting one
_ENTITY_ID = re.compile(r"\b(sku[-\s]?\d{3,6}|prd-\d{5}|ord-\d+)\b|#\d+", re.I)

# Coordinator conversation (whole-message patterns; shared with router's reply table)
GREETING_PATTERNS = [
    r"^(hi+|hello+|hey+|yo+|greetings|sup|howdy|hiya)( there| team| all| everyone| guys)?[\s\!\?\.,]*$",
    r"^good (morning|afternoon|evening|day)( there| team| all| everyone)?[\s\!\?\.,]*$",
]
CAPABILITY_PATTERNS = [
    r"\bhow many agents\b", r"\bhow many subagents\b", r"\bwhat agents\b", r"\bwhat subagents\b",
    r"\bwhich agents\b", r"\blist.*agents\b", r"\bwhat can you do\b", r"\bwhat are you\b", r"\bwho are you\b",
    r"\bintroduce yourself\b", r"\bwhat is intelliwms\b", r"\bwhat do you do\b",
    r"\byour (agents|subagents|capabilities|features)\b", r"\btell me about yourself\b",
]
HELP_PATTERNS = [
    r"^\s*(can you |could you |please )?help( me)?( please)?[\s\!\?\.]*$",
    r"^what\?*$",
]
# Words that also occur in real questions ("help me find SKU-4521", "stock in the cooling system"):
# treated as meta only when no warehouse rule matched.
WEAK_META_PATTERNS = [r"\bhelp\b", r"\bbruh\b", r"\bwhat.*system\b"]
ACK_PATTERN = re.compile(
    r"^\s*(thanks?( a lot| so much)?|thank you( so much| very much)?|thx|ty|ok(ay)?|cool|great|nice|got it|"
    r"perfect|awesome|cheers|noted|understood|sounds good|alright|yes|yep|yeah|no|nope)\b[\s!.,]*$", re.I)
BYE_PATTERN = re.compile(r"^\s*(bye|goodbye|good bye|see you|see ya|cya|good night)\b[\s!.,]*$", re.I)

_KNOWLEDGE_STRONG = [
    r"\b(sop|sop-\d+|standard operating procedure|procedures?|policy|policies|guidelines?|protocol|sp-\d+)\b",
    r"\b(returns|how to return|compliance|shift handover|shift notes|speed limit)\b",
    r"\bmanual\b(?!\s+(count|counts|adjustment|adjustments|stock))",
    r"\b(building\s*#?[1-7]|bld-0[1-7]|cold vault|cold storage|quarantine yard|quarantine bay\s*11|high-bay hub|high-bay|bulk distribution|tech mezzanine|fleet depot|gatehouse|weighbridge|60t scale|airlock port|spill berm|freight lift)\b",
    r"\b(campus layout|campus map|site plan|campus plan|campus facilities|all buildings)\b",
    r"\b(where is|locate|find|position of)\b.*\b(forklift|reach truck|pallet jack|agv|shunt truck|tugger|scale|charger)\b",
    r"\b(fl-01|rt-01|rt-02|pj-01|agv-01)\b",
]
_FULFILLMENT_STRONG = [
    r"\b(order|orders|ord-\d+|delay|delayed|dispatch|dispatched|tracking|track|courier|carrier)\b|#\d+",
]
# Inventory: stock quantities, availability, locations, low stock, movements (meaning-level phrases)
_INVENTORY_STRONG = [
    r"\bsku[-\s]?\d{3,6}\b", r"\bprd-\d{5}\b",
    r"\b(in stock|out of stock|low stock|low on stock|stock ?(level|levels|count|counts|status|movements?|history|on hand)|"
    r"on hand|safety stock|reorder (point|level|quantity|threshold)|restock\w*|replenish\w*|inventory)\b",
    r"\b(stock|units?|items?|pieces) (left|remaining|available)\b",
    r"\b(how (many|much)\b.*\bavailable|available (stock|units?|quantity|qty|inventory)|"
    r"(stock|inventory) availability|availability of)\b",
    r"\bhow many (units|pieces|pcs|boxes|cases|cartons|pallets|rolls|items|of (the|our|those|these))\b",
    r"\b(running (low|out)|what'?s low|anything low|do we (have|stock|carry))\b",
    r"\b(inbound (shipment|delivery|deliveries|stock|receipt)s?|supplier (email|pdf|delivery|shipment))\b",
    r"\b(forklift|conveyor|agv(-\d+)?|pallet jack|reach truck|label printer|printer|scanner|wrapper)s?\b.*"
    r"\b(grind\w*|leak\w*|noise|squeal\w*|slipping|shaking|vibrat\w*|overheat\w*|breakdown|broke\w*|not working|"
    r"stopped working|won'?t start|fault\w*|jam\w*|stuck|keeps (stopping|failing|crashing|freezing))\b",
    r"\b(equipment health|complaint log)\b",
]
# The original keyword lists, checked after the strong signals
_KNOWLEDGE_KEYWORDS = [
    r"\b(sop|sop-\d+|standard operating procedure|policy|policies|guideline|manual|safety|protocol|sp-\d+)\b",
    r"\b(returns|how to return|compliance|shift handover|shift notes|speed limit|vest)\b",
]
_FULFILLMENT_KEYWORDS = [
    r"\b(order|orders|ord-\d+|#\d+|delay|delayed|dispatch|tracking|track|shipment|courier|carrier)\b",
    r"\b(complaint|shipping|packing slip|transit)\b",
]
_INVENTORY_KEYWORDS = [
    r"\b(stock|inventory|quantity|sku|sku-\d+|reorder|restock|battery|label rolls|pallet wrap)\b",
    r"\b(how many|on hand|in stock|warehouse aisle|shelf|bin location|bay map)\b",
    r"\b(supplier email|supplier pdf|parse email|inbound invoice|manifest|po-\d+|we shipped)\b",
    r"\b(grinding|hydraulic leak|conveyor slip|belt squeal|agv-\d+|equipment health|machine breakdown|informal log)\b",
    r"\b(forklift.*(grind|leak|noise|break|service|repair|shaking))\b",
    r"\b(shrinkage|anomaly|missing stock|discrepancy|unauthorized adjustment|loss prevention)\b",
    r"\b(transfer|sibling warehouse|other warehouse|surplus stock|wh-beta|wh-gamma|wh-delta)\b",
    r"\b(burn rate|depletion|velocity|days until stockout|predict reorder)\b",
]
# Warehouse Digital Twin places and product numbers ("rack 2", "cold 3", PRD-00002, WH1-F2-...)
_TWIN_ENTITY = [
    r"\b(rack|crate|cold|freezer)\s*#?\s*\d+\b",
    r"\b(product|item)\s*(no\.?|number|num)\s*\d+\b",
    r"\bprd-\d{5}\b",
    r"\bwh\d+-f\d+",
    # Rack fill on the map ("which rack is the emptiest on floor 1", "fullest racks", "rack heatmap")
    r"\b(fullest|emptiest|least full|busiest|quietest|heat ?map)\b.*\b(racks?|crates?|shel(f|ves)|bins?|floor \d+)\b",
    r"\b(racks?|crates?|shel(f|ves)|bins?)\b.*\b(fullest|emptiest|least full|busiest|quietest|most (free )?space)\b",
    # Map controls
    r"^\s*(clear|reset|close)( the)? (warehouse )?(map|twin)\W*$",
]
# Generic map wording: a weak hint only — the LLM is consulted and the hint is its fallback
_TWIN_HINT = [
    r"\b(where (is|are)|where's|locate|find)\b",
    r"\b(how (do|can|should) (i|we) (get|go|reach)|take me|directions?|route to|navigate|guide me)\b",
    r"\b(cold storage|heat ?map|running (low|out)|busiest|fullest|racks?|crates?|freezers?|floor \d+)\b",
    r"\bunit\s*#?\s*\d+\b",  # "unit 4" may also be equipment
]

# Follow-ups to an inventory answer
_POINTS_BACK = re.compile(r"\b(it|its|it's|that|this|those|these|them|they|same|the one|that one|this one|there)\b|"
                          r"^\s*(and|also|what about|how about)\b", re.I)
_ORDINAL_REPLY = re.compile(r"^\s*(#?\d{1,2}|(the )?(first|second|third|fourth|fifth|last)( one)?|"
                            r"(number|option|no\.?) ?\d{1,2})\s*[.!?]?\s*$", re.I)
_INVENTORY_OPENER = re.compile(r"^\s*(how (many|much)|where|which one|any (left|more)|is there|are there)\b", re.I)
_WORD = re.compile(r"[a-z0-9]+")

# Kept for compatibility: every whole-message meta pattern
META_PATTERNS = GREETING_PATTERNS + CAPABILITY_PATTERNS + HELP_PATTERNS


class IntentClassifier:
    """Classifies warehouse queries into specialist agent domains (rules first, LLM last)."""

    VALID_DOMAINS = {"INVENTORY", "FULFILLMENT", "KNOWLEDGE", "COORDINATOR"}
    CONFIDENCE_THRESHOLD = 0.60
    # Rule results at or above this are decisions; below it they are only hints
    HEURISTIC_CONFIDENCE_THRESHOLD = 0.80
    META_PATTERNS = META_PATTERNS
    WEAK_META_PATTERNS = WEAK_META_PATTERNS

    def __init__(self, llm: Optional[Any] = None):
        self._llm = llm

    @property
    def client(self):
        if self._llm is not None:
            return self._llm
        return llm_config.get_client()

    # ── Public API ──────────────────────────────────────────────────────────

    def classify(self, query: str, context: Optional[dict] = None) -> IntentResult:
        """
        Rules decide when they can; otherwise the LLM may suggest a domain, and code
        accepts it only when valid and confident. Never raises.

        Args:
            query: the (sanitized) user message
            context: optional thread context {last_domain, pending_clarification, history}
        """
        decided, hint = self._evaluate(query, context)
        if decided is not None:
            return decided
        return self._consult_llm(query, context, hint)

    def match_rules(self, query: str, context: Optional[dict] = None) -> Optional[IntentResult]:
        """The decision of the code rules alone, or None when no rule decides. Never calls an LLM."""
        return self._evaluate(query, context)[0]

    def weak_hint(self, query: str) -> Optional[IntentResult]:
        hit = self._heuristic_match((query or "").lower())
        return hit if hit is not None and hit.confidence < self.HEURISTIC_CONFIDENCE_THRESHOLD else None

    # ── Rules ───────────────────────────────────────────────────────────────

    def _evaluate(self, query: str, context: Optional[dict]) -> Tuple[Optional[IntentResult], Optional[IntentResult]]:
        """(decision, weak_hint) — decision is None when no rule decides."""
        q = (query or "").strip()
        ql = q.lower()
        if not q:
            return IntentResult("COORDINATOR", 1.0, "Empty query handled by coordinator", "meta",
                                rule_id="empty"), None

        names_id = bool(_ENTITY_ID.search(ql))
        if not names_id:
            if _any(GREETING_PATTERNS, ql):
                return self._meta("meta.greeting", "Greeting."), None
            if _any(CAPABILITY_PATTERNS, ql):
                return self._meta("meta.capability", "Question about the assistant itself."), None
            if _any(HELP_PATTERNS, ql):
                return self._meta("meta.help", "Request for help with no warehouse question."), None
            if ACK_PATTERN.match(q):
                return IntentResult("COORDINATOR", 0.99, "Acknowledgement.", "social", rule_id="social.ack"), None
            if BYE_PATTERN.match(q):
                return IntentResult("COORDINATOR", 0.99, "Goodbye.", "social", rule_id="social.bye"), None

        if self._is_clarification_reply(q, context):
            return IntentResult("INVENTORY", 0.9, "Answer to the inventory clarification just offered.", "context",
                                rule_id="context.clarification_reply"), None

        hit = self._heuristic_match(ql)
        if hit is not None and hit.confidence >= self.HEURISTIC_CONFIDENCE_THRESHOLD:
            return hit, None
        hint = hit  # weak (below threshold) or None

        if hint is None and not names_id and _any(WEAK_META_PATTERNS, ql):
            return self._meta("meta.weak", "Meta/system wording with no warehouse question.", 0.9), None

        follow_up = self._context_follow_up(q, context)
        if follow_up is not None:
            return follow_up, hint
        return None, hint

    @staticmethod
    def _meta(rule_id: str, reasoning: str, confidence: float = 0.99) -> IntentResult:
        return IntentResult("COORDINATOR", confidence, reasoning, "meta", rule_id=rule_id)

    def _heuristic_match(self, ql: str) -> Optional[IntentResult]:
        """Domain keyword rules in priority order; None when nothing matches."""
        table = [
            (_KNOWLEDGE_STRONG, "KNOWLEDGE", 0.91, "knowledge.strong", "Warehouse SOP, policy or protocol signal."),
            (_FULFILLMENT_STRONG, "FULFILLMENT", 0.94, "fulfillment.strong", "Order id, dispatch or tracking signal."),
            (_INVENTORY_STRONG, "INVENTORY", 0.95, "inventory.strong", "Stock quantity, availability or product id."),
            (_KNOWLEDGE_KEYWORDS, "KNOWLEDGE", 0.91, "knowledge.keywords", "Warehouse SOP / safety keywords."),
            (_FULFILLMENT_KEYWORDS, "FULFILLMENT", 0.94, "fulfillment.keywords", "Order / shipping keywords."),
            (_INVENTORY_KEYWORDS, "INVENTORY", 0.93, "inventory.keywords", "Stock, SKU and inventory keywords."),
            (_TWIN_ENTITY, "INVENTORY", 0.95, "inventory.twin_entity", "Warehouse place or product number."),
            (_TWIN_HINT, "INVENTORY", 0.75, "inventory.twin_hint", "Warehouse map wording (weak hint)."),
        ]
        for patterns, domain, confidence, rule_id, reasoning in table:
            if _any(patterns, ql):
                return IntentResult(domain, confidence, f"Heuristic match: {reasoning}", "heuristic", rule_id=rule_id)
        return None

    def _heuristic_fallback(self, query: str) -> IntentResult:
        """Keyword rules only (kept for callers and tests); COORDINATOR 0.50 when nothing matches."""
        hit = self._heuristic_match((query or "").lower())
        return hit or IntentResult("COORDINATOR", 0.50,
                                   "Query did not match any warehouse domain — coordinator will respond directly.",
                                   rule_id="no_match")

    @staticmethod
    def _is_clarification_reply(q: str, context: Optional[dict]) -> bool:
        """A pick from the inventory clarification just offered: a number, an ordinal or a candidate's name."""
        labels: List[str] = (context or {}).get("pending_clarification") or []
        if not labels:
            return False
        if _ORDINAL_REPLY.match(q):
            return True
        label_words = {w for label in labels for w in _WORD.findall(label.lower()) if len(w) > 2 and not w.isdigit()}
        return bool(label_words & set(_WORD.findall(q.lower())))

    @staticmethod
    def _context_follow_up(q: str, context: Optional[dict]) -> Optional[IntentResult]:
        """A follow-up to an inventory answer: points back ("it", "and…"), a bare pick, or an inventory opener."""
        if not context or context.get("last_domain") != "INVENTORY":
            return None
        if _POINTS_BACK.search(q) or _ORDINAL_REPLY.match(q) or _INVENTORY_OPENER.match(q):
            return IntentResult("INVENTORY", 0.85, "Follow-up to the previous inventory answer in this conversation.",
                                "context", rule_id="context.inventory_follow_up")
        return None

    # ── LLM (only when no rule decided) ─────────────────────────────────────

    def _consult_llm(self, query: str, context: Optional[dict], hint: Optional[IntentResult]) -> IntentResult:
        prompt = f"""{COORDINATOR_SYSTEM_PROMPT}
{self._history_block(context)}
User warehouse query: "{query}"

Analyze the query and return ONLY a valid JSON object:
"""

        def ask() -> str:
            client = self.client
            if hasattr(client, "models") and hasattr(client.models, "generate_content"):
                response = client.models.generate_content(model=llm_config.GEMINI_MODEL, contents=prompt)
                return str(getattr(response, "text", "") or "")
            if callable(client):
                return str(client(prompt))
            if hasattr(client, "generate"):
                return str(client.generate(prompt))
            return ""

        available = self._llm is not None or bool(llm_config.gemini_key)
        status, raw = call_llm("classify", ask, available=available)
        llm_status = status
        if status == OK:
            parsed = self._parse_llm(raw)
            if parsed is None:
                llm_status = "invalid"
            else:
                domain, confidence, reasoning = parsed
                if confidence >= self.CONFIDENCE_THRESHOLD:
                    return IntentResult(domain, confidence, reasoning, "llm", rule_id="llm.classify",
                                        decided_by=LLM, llm_status="ok", llm_consulted=True)
                llm_status = "low_confidence"

        ROUTING_FAILURES.inc(reason=f"llm_{llm_status}")
        consulted = status != UNAVAILABLE
        source = "llm_low_confidence" if llm_status == "low_confidence" else "fallback"
        if hint is not None:
            return IntentResult(hint.domain, hint.confidence,
                                f"{hint.reasoning} LLM result {llm_status}; the matching rule was applied.", source,
                                rule_id=hint.rule_id, decided_by=FALLBACK, llm_status=llm_status,
                                llm_consulted=consulted)
        return IntentResult("COORDINATOR", 0.5,
                            f"No rule matched and the LLM result was {llm_status}; asking the user to clarify.",
                            source, rule_id="clarify.domain", decided_by=FALLBACK, llm_status=llm_status,
                            llm_consulted=consulted)

    def _parse_llm(self, raw: str) -> Optional[Tuple[str, float, str]]:
        """Strict: a JSON object with a known domain and an explicit confidence; anything else is invalid."""
        text = self._extract_json(raw or "")
        try:
            parsed = json.loads(text)
        except ValueError:
            match = re.search(r"\{.*\}", text, re.S)
            if not match:
                return None
            try:
                parsed = json.loads(match.group(0))
            except ValueError:
                return None
        if not isinstance(parsed, dict):
            return None
        domain = str(parsed.get("domain") or parsed.get("intent") or "").strip().upper()
        if domain not in self.VALID_DOMAINS or parsed.get("confidence") is None:
            return None
        try:
            confidence = min(1.0, max(0.0, float(parsed["confidence"])))
        except (TypeError, ValueError):
            return None
        return domain, confidence, str(parsed.get("reasoning") or "LLM classified intent")[:300]

    @staticmethod
    def _history_block(context: Optional[dict]) -> str:
        """Recent turns for the LLM, so follow-ups are classified with their conversation."""
        if not context:
            return ""
        lines = []
        for turn in (context.get("history") or [])[-4:]:
            who = turn.get("role", "user")
            if turn.get("agent"):
                who += f" ({turn['agent']})"
            lines.append(f"- {who}: {str(turn.get('content', ''))[:200]}")
        if context.get("last_domain"):
            lines.append(f"The previous answer was handled by the {context['last_domain']} domain. If the new "
                         f"query is a follow-up about the same item, keep that domain.")
        return ("Recent conversation (oldest first):\n" + "\n".join(lines) + "\n") if lines else ""

    def _extract_json(self, text: str) -> str:
        """Strips markdown code fences and returns clean JSON string."""
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()


# Singleton instance
intent_classifier = IntentClassifier()
