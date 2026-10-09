"""
Inventory question understanding: sub-intent, product ids, and follow-ups.

Pure functions (no I/O) so they are cheap to test. Matching uses word
boundaries, not substrings ("bin" no longer matches "cabinet"), and a stock
question about equipment ("is the forklift battery in stock?") is not mistaken
for an equipment complaint — that needs a symptom word.
"""
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from agents.inventory_agent.tool_contracts import canonical_sku


def _rx(*parts: str) -> re.Pattern:
    return re.compile("|".join(parts), re.I)


_DOCUMENT = _rx(r"supplier (email|pdf|note|notification)", r"parse (this |the )?(email|document|pdf)",
                r"inbound invoice", r"shipping manifest", r"delivery confirmation", r"\bfrom (apex|zebra)\b",
                r"\bsubject:", r"attached document")
_EQUIPMENT = _rx(r"\b(grinding|grind|squeal\w*|hydraulic leak|leak(ing|s)?|break(s|ing)? ?down|broke(n)? down|"
                 r"slipping|shaking|vibrat\w*|overheat\w*|sensor fault|agv stopped|won'?t start|"
                 r"strange noise|loud noise|making (a )?(\w+ )?noise)\b",
                 r"\b(equipment (health|issue)|complaint log|maintenance (log|ticket))\b",
                 # A named machine with a fault ("the label printer keeps jamming", "scanner not working")
                 r"\b(forklift|conveyor|agv|pallet jack|reach truck|printer|scanner|wrapper|dock door)s?\b.*"
                 r"\b(jam\w*|stuck|not working|stopped working|keeps (stopping|failing|crashing|freezing)|"
                 r"error code|fault\w*|smok\w*|spark\w*|rattl\w*)\b")
_ANOMALY = _rx(r"\b(anomal\w*|shrinkage|stolen|theft|loss prevention|discrepanc\w*|missing stock|"
               r"unauthori[sz]ed adjustment|unexplained drop)\b")
_MOVEMENTS = _rx(r"\b(stock |inventory )?movements?\b", r"\b(stock|transaction|movement) history\b",
                 r"\btransactions?\b", r"\b(was|were|got|been) moved\b", r"\bins and outs\b",
                 r"\b(came in|went out)\b")
_TRANSFER = _rx(r"\btransfer\w*\b", r"sibling warehouse", r"other warehouse", r"inter-warehouse",
                r"\bwh-(beta|gamma|delta)\b", r"surplus (stock|in other)")
_PREDICT = _rx(r"burn rate", r"depletion", r"velocity", r"days until stockout", r"\brun out\b", r"\bwhen will\b",
               r"predict reorder", r"consumption trend", r"\bforecast\w*\b", r"how long (will|until)")
_REORDER = _rx(r"\breorder\b", r"\breplenish\w*\b", r"\brestock\w*\b", r"need to order", r"running (low|out)",
               r"\blow (stock|on)\b", r"\bout of stock\b", r"\bbelow (the )?(safety|reorder)\b",
               r"what'?s (low|running low)", r"anything low")
_LOCATION = _rx(r"\bwhere\b", r"\blocat\w*\b", r"\baisle\b", r"\bshelf\b", r"\bbin\b", r"\bbay\b", r"\bfind\b",
                r"\brack\b")
_AVAILABILITY = _rx(r"\bavailab\w*\b", r"\bin stock\b", r"\bdo we (have|stock|carry)\b", r"\bhave any\b",
                    r"\bany left\b", r"\bleft in stock\b", r"\bcan i (get|pick)\b")

# Sub-intents that need a specific product to answer
PRODUCT_SUB_INTENTS = {"stock_check", "availability", "location_lookup", "stock_movements",
                       "reorder_predictor", "transfer_advisor"}
# Sub-intents the Digital Twin map can answer
TWIN_SUB_INTENTS = {"location_lookup", "stock_check", "reorder_check", "availability"}


# Ordered rules: (pattern, sub_intent, rule_id)
_SUB_INTENT_RULES = [
    (_DOCUMENT, "document_parser", "sub_intent.document"),
    (_EQUIPMENT, "equipment_health", "sub_intent.equipment"),
    (_ANOMALY, "anomaly_watcher", "sub_intent.anomaly"),
    (_MOVEMENTS, "stock_movements", "sub_intent.movements"),
    (_TRANSFER, "transfer_advisor", "sub_intent.transfer"),
    (_PREDICT, "reorder_predictor", "sub_intent.forecast"),
    (_REORDER, "reorder_check", "sub_intent.reorder"),
    (_AVAILABILITY, "availability", "sub_intent.availability"),
    (_LOCATION, "location_lookup", "sub_intent.location"),
]


def detect_sub_intent_with_rule(query: str) -> Tuple[str, str]:
    """(sub_intent, rule_id) — the first matching rule wins; stock_check is the default."""
    q = query or ""
    for pattern, sub_intent, rule_id in _SUB_INTENT_RULES:
        if pattern.search(q):
            return sub_intent, rule_id
    return "stock_check", "sub_intent.default_stock_check"


def detect_sub_intent(query: str) -> str:
    return detect_sub_intent_with_rule(query)[0]


_SKU_IN_TEXT = re.compile(r"\bSKU[-\s]?\d{3,6}\b", re.I)
_SKU_ANY_DIGITS = re.compile(r"\bSKU[-\s]?(\d+)\b", re.I)
_PRD_IN_TEXT = re.compile(r"\bPRD-\d{5}\b", re.I)


@dataclass
class Entities:
    skus: List[str] = field(default_factory=list)
    product_ids: List[str] = field(default_factory=list)
    # SKU-shaped codes with the wrong number of digits ("SKU-4521000"): reported as not found
    invalid_skus: List[str] = field(default_factory=list)

    @property
    def any(self) -> bool:
        return bool(self.skus or self.product_ids)


def extract_entities(query: str) -> Entities:
    skus = [canonical_sku(m.group(0)) for m in _SKU_IN_TEXT.finditer(query or "")]
    prds = [m.group(0).upper() for m in _PRD_IN_TEXT.finditer(query or "")]
    invalid = [f"SKU-{m.group(1)}" for m in _SKU_ANY_DIGITS.finditer(query or "") if not 3 <= len(m.group(1)) <= 6]
    return Entities(skus=list(dict.fromkeys(s for s in skus if s)), product_ids=list(dict.fromkeys(prds)),
                    invalid_skus=list(dict.fromkeys(invalid)))


# ── Quantities ("transfer 500 units of SKU-4521") ────────────────────────────

_QTY_UNITS = r"units?|pcs|pieces?|rolls?|boxes|box|cases?|cartons?|pallets?|items?|kits?|packs?|crates?"
_QTY_WITH_UNIT = re.compile(rf"(?<![\w-])(-?\d[\d,]*)\s*(?:{_QTY_UNITS})\b", re.I)
_QTY_AFTER_VERB = re.compile(r"\b(?:transfer|move|send|ship|need|get|bring|order)\s+(-?\d[\d,]*)\b(?!\s*%)", re.I)


def requested_quantity(query: str) -> Optional[int]:
    """The quantity the user asked for (signed, so 0 and negatives can be rejected), or None."""
    text = _SKU_ANY_DIGITS.sub(" ", _PRD_IN_TEXT.sub(" ", query or ""))  # SKU / PRD digits are not quantities
    m = _QTY_WITH_UNIT.search(text) or _QTY_AFTER_VERB.search(text)
    if not m:
        return None
    try:
        return int(m.group(1).replace(",", ""))
    except ValueError:
        return None


# ── Follow-ups ───────────────────────────────────────────────────────────────

_PRONOUN = re.compile(r"\b(it|its|it's|that|this|those|these|them|they|same( one| item| product)?|"
                      r"the one|that one|this one|(take me|get|go|navigate|directions?) there)\b", re.I)
_CONTINUATION = re.compile(r"^\s*(and|also|what about|how about|ok(ay)?,? (and|what about))\b", re.I)
_ORDINALS = {"first": 0, "1st": 0, "one": 0, "second": 1, "2nd": 1, "two": 1, "third": 2, "3rd": 2, "three": 2,
             "fourth": 3, "4th": 3, "four": 3, "fifth": 4, "5th": 4, "five": 4}
_ORDINAL = re.compile(r"\b(first|1st|second|2nd|third|3rd|fourth|4th|fifth|5th|last)\b|"
                      r"^\s*#?([1-5])\s*[.!?]?\s*$|\b(?:number|option|no\.?)\s*([1-5])\b", re.I)
# "two" / "the third one" only when that is the whole reply (avoid "is there one left?")
_BARE_NUMBER_WORD = re.compile(r"^\s*(the\s+)?(one|two|three|four|five)(\s+one)?\s*[.!?]?\s*$", re.I)
_WORD = re.compile(r"[a-z0-9]+")


@dataclass
class FollowUp:
    skus: List[str] = field(default_factory=list)
    product_ids: List[str] = field(default_factory=list)
    location_ids: List[str] = field(default_factory=list)  # a map place picked from a clarification
    picked_from_clarification: bool = False
    assumed: bool = False  # carried over from the previous answer, not named in this message
    pending_query: Optional[str] = None  # the question the clarification was asked for

    @property
    def any(self) -> bool:
        return bool(self.skus or self.product_ids or self.location_ids)


def _pick_candidate(query: str, candidates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    q = query.lower()
    m = _ORDINAL.search(q)
    bare = _BARE_NUMBER_WORD.match(q)
    if m or bare:
        word = (bare.group(2) if bare else (m.group(1) or "")).lower()
        if word == "last":
            return candidates[-1]
        idx = _ORDINALS.get(word) if word else int(m.group(2) or m.group(3)) - 1
        if idx is not None and 0 <= idx < len(candidates):
            return candidates[idx]
    q_words = set(_WORD.findall(q))
    best, best_hits = None, 0
    for c in candidates:
        label_words = {w for w in _WORD.findall(str(c.get("label", "")).lower()) if len(w) > 2}
        hits = len(label_words & q_words)
        if hits > best_hits:
            best, best_hits = c, hits
    return best


# Words that say what is being asked (or point back), not which product
STOPWORDS = {
    "a", "about", "again", "all", "also", "an", "and", "any", "anything", "are", "at", "available", "availability",
    "be", "can", "check", "could", "count", "current", "currently", "did", "do", "does", "else", "enough", "for",
    "find", "from", "get", "give", "go", "got", "hand", "has", "have", "here", "history", "how", "i", "in",
    "inventory", "is", "it", "item", "items", "its", "just", "left", "level", "levels", "list", "locate",
    "located", "location", "low", "many", "me", "movement", "movements", "much", "my", "need", "now", "of", "ok",
    "okay", "on", "one", "ones", "or", "our", "out", "please", "product", "products", "qty", "quantity", "recent",
    "remaining", "reorder", "running", "same", "show", "sku", "status", "still", "stock", "stocked", "stocks", "take",
    "tell", "that", "the", "them", "then", "there", "these", "they", "this", "those", "to", "today", "unit",
    "units", "us", "warehouse", "we", "what", "whats", "where", "wheres", "which", "with", "you", "your",
}


def _norm(word: str) -> str:
    return word[:-1] if len(word) > 3 and word.endswith("s") and not word.endswith("ss") else word


def meaningful_terms(text: str) -> List[str]:
    """Normalised words that could name a product (question words and pronouns removed)."""
    return [_norm(w) for w in _WORD.findall((text or "").lower()) if w not in STOPWORDS and len(w) > 1]


def points_back(query: str) -> bool:
    """Strong follow-up signal: a pronoun or a continuation ("and ...", "what about ...")."""
    return bool(_PRONOUN.search(query or "") or _CONTINUATION.search(query or ""))


def is_short(query: str, max_words: int = 4) -> bool:
    return len(_WORD.findall((query or "").lower())) <= max_words


def resolve_follow_up(query: str, conversation: Optional[Dict[str, Any]], allow_short: bool = False) -> FollowUp:
    """
    Product(s) a follow-up refers to: a pick from the clarification just offered
    ("the second one", "2", "the printer"), or the product of the previous answer
    when the message points back at it ("how many of those?", "and where is it?").
    allow_short also accepts a short message with no product named ("how many?"); the
    agent only uses that after a name search found nothing.
    """
    conv = conversation or {}
    pending = conv.get("pending_clarification") or []
    if pending:
        choice = _pick_candidate(query, pending)
        if choice:
            return FollowUp(skus=[choice["sku"]] if choice.get("sku") else [],
                            product_ids=[choice["product_id"]] if choice.get("product_id") else [],
                            location_ids=[choice["location_id"]] if choice.get("location_id") else [],
                            picked_from_clarification=True, pending_query=conv.get("pending_query"))
    skus, prds = list(conv.get("skus") or []), list(conv.get("product_ids") or [])
    if (skus or prds) and (points_back(query) or (allow_short and is_short(query))):
        return FollowUp(skus=skus[:1], product_ids=prds[:1], assumed=True)
    return FollowUp()
