"""
Question autocomplete for the Inventory Agent.

Turns partly typed chat text into 3-5 complete questions the Inventory Agent can answer.
Everything here is read-only and deterministic: no LLM, no MCP tools, no writes.

- Templates only cover sub-intents the agent supports (see intents.py / report_queries.py).
- Product, category and floor names come from the live catalog; nothing is invented.
- A question never states a stock fact ("X is low"); it only asks ("Is X available?").
- Every suggestion is checked against the coordinator's own routing rules, so sending it
  reaches the Inventory Agent with the sub-intent the template was written for.
"""
import difflib
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

from agents.coordinator.intent_classifier import IntentClassifier
from agents.inventory_agent.intents import detect_sub_intent
from agents.inventory_agent.tool_contracts import SKU_PATTERN
from utils.logger import StructuredLogger

logger = StructuredLogger(__name__)

MAX_SUGGESTIONS = 5
MIN_SUGGESTIONS = 3
MIN_CHARS = 2
_MAX_PRODUCTS = 2           # products expanded into questions per keystroke
_CATALOG_TTL_S = 30.0
_LEGACY_ROW_LIMIT = 500

# ── Vocabulary: typed word → topics it signals (synonyms share topics) ──────

_VOCAB: Dict[str, Tuple[str, ...]] = {}


def _words(topics: Tuple[str, ...], *words: str) -> None:
    for word in words:
        _VOCAB[word] = tuple(dict.fromkeys(_VOCAB.get(word, ()) + topics))


_words(("stock",), "stock", "stocks", "inventory", "quantity", "quantities", "qty", "level", "levels", "units",
       "unit", "onhand", "count", "many", "much", "current", "balance", "amount")
_words(("availability",), "available", "availability", "avail", "left", "remaining", "have", "carry")
_words(("low",), "low", "running", "short", "shortage", "below", "threshold")
_words(("out",), "out", "empty", "zero", "none", "oos")
_words(("reorder",), "reorder", "reordering", "restock", "restocking", "replenish", "replenishment", "refill",
       "safety", "need")
_words(("location",), "where", "location", "locations", "located", "locate", "stored", "store", "storage", "bin",
       "bins", "rack", "racks", "shelf", "shelves", "aisle", "bay", "find", "placed", "placement", "map")
_words(("scope",), "warehouse", "warehouses", "floor", "floors", "zone", "wh")
_words(("movements",), "movement", "movements", "moved", "move", "moves", "history", "transaction",
       "transactions", "ins", "outs")
_words(("forecast",), "forecast", "depletion", "deplete", "burn", "run", "runout", "predict", "prediction", "when",
       "days", "until")
_words(("summary",), "summary", "overview", "total", "totals", "report", "breakdown")
_words(("category",), "category", "categories", "type", "types", "group")
_words(("reserved",), "reserved", "reservation", "reservations", "allocated")
_words(("unassigned",), "unassigned", "unplaced", "unallocated")
_words(("quarantined",), "quarantine", "quarantined", "hold")
_words(("highest",), "highest", "most", "largest", "top", "max", "maximum", "biggest")
_words(("lowest",), "lowest", "least", "smallest", "minimum", "min", "fewest")
_words(("catalog",), "many", "product", "products", "item", "items", "sku", "skus", "catalog", "catalogue", "list")

# Words that say the question belongs to another agent (leave, deliveries, SOPs, ...)
_FOREIGN = frozenset({
    "leave", "leaves", "vacation", "holiday", "holidays", "payroll", "salary", "sick", "roster",
    "delivery", "deliveries", "deliver", "delivered", "shipment", "shipments", "shipping", "shipped", "ship",
    "tracking", "track", "carrier", "courier", "dispatch", "dispatched", "order", "orders", "invoice",
    "policy", "policies", "procedure", "procedures", "sop", "sops", "manual", "protocol", "training", "ppe",
    "customer", "customers", "refund", "return", "returns",
})

_STOPWORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "do", "does", "did", "we", "i", "me", "my", "our", "us",
    "you", "what", "which", "who", "how", "show", "tell", "give", "get", "of", "for", "in", "on", "at", "to",
    "and", "or", "any", "all", "some", "there", "it", "this", "that", "these", "those", "please", "can", "could",
    "should", "would", "with", "by", "from", "about", "need", "s",
})

_FUZZY_CUTOFF = 0.8
_TOKEN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_TYPED_SKU = re.compile(r"\bSKU[-\s]?\d{3,6}\b", re.I)   # the same id shapes intents.py resolves
_TYPED_PRD = re.compile(r"\bPRD-\d{5}\b", re.I)


@dataclass(frozen=True)
class _Template:
    id: str
    text: str
    sub_intent: str              # what intents.detect_sub_intent must return for this question
    weights: Dict[str, float]    # topic → relevance of this question to that topic
    default: float = 0.0         # relevance when a product is named but no topic word was typed


# {label} = "Name (SKU)" for readability; {ref} = SKU or product id alone (what the agent resolves)
PRODUCT_TEMPLATES = (
    _Template("product_stock", "What is the current stock of {label}?", "stock_check",
              {"stock": 1.0, "catalog": 0.5, "summary": 0.4}, default=1.0),
    _Template("product_available", "Is {label} available?", "availability",
              {"availability": 1.0, "out": 0.6, "stock": 0.7}, default=0.9),
    _Template("product_location", "Where is {label} stored?", "location_lookup",
              {"location": 1.0, "scope": 0.6, "unassigned": 0.5}, default=0.8),
    _Template("product_movements", "Show stock movements for {ref}", "stock_movements",
              {"movements": 1.0, "stock": 0.3}, default=0.6),
    _Template("product_forecast", "When will {ref} run out?", "reorder_predictor",
              {"forecast": 1.0, "out": 0.7, "low": 0.6}, default=0.55),
    _Template("product_reorder", "Should we reorder {ref}?", "reorder_check",
              {"reorder": 1.0, "low": 0.8, "out": 0.4}, default=0.5),
)

GENERIC_TEMPLATES = (
    _Template("low_stock", "Which products are low on stock?", "reorder_check",
              {"low": 1.0, "reorder": 0.7, "stock": 0.55, "lowest": 0.5}),
    _Template("out_of_stock", "Which products are out of stock?", "inventory_report",
              {"out": 1.0, "availability": 0.6, "stock": 0.5, "low": 0.5}),
    _Template("restock", "Which products need restocking?", "reorder_check",
              {"reorder": 1.0, "low": 0.75, "stock": 0.35}),
    _Template("lowest_stock", "Which product has the lowest stock?", "lowest_stock",
              {"lowest": 1.0, "low": 0.65, "stock": 0.6}),
    _Template("highest_stock", "Which product has the highest stock?", "inventory_report",
              {"highest": 1.0, "stock": 0.45}),
    _Template("summary", "Show the inventory summary", "inventory_report",
              {"summary": 1.0, "stock": 0.5, "catalog": 0.35}),
    _Template("product_count", "How many products do we have?", "inventory_report",
              {"catalog": 1.0, "stock": 0.3, "summary": 0.4}),
    _Template("reserved", "Show reserved stock", "inventory_report",
              {"reserved": 1.0, "availability": 0.3}),
    _Template("unassigned", "Show unassigned inventory", "inventory_report",
              {"unassigned": 1.0, "location": 0.4}),
    _Template("quarantined", "Which products are quarantined?", "inventory_report",
              {"quarantined": 1.0}),
    _Template("by_category", "What is the total stock by category?", "inventory_report",
              {"category": 1.0, "summary": 0.7, "stock": 0.3}),
    _Template("by_floor", "What is the total stock by floor?", "inventory_report",
              {"scope": 1.0, "summary": 0.6, "location": 0.45}),
    _Template("by_warehouse", "What is the total stock by warehouse?", "inventory_report",
              {"scope": 0.9, "summary": 0.55}),
)

CATEGORY_TEMPLATE = _Template("category_list", "List products in category {category}", "inventory_report",
                              {"category": 0.9, "catalog": 0.6})
FLOOR_TEMPLATE = _Template("floor_lowest", "Which product has the lowest stock in {floor}?", "lowest_stock",
                           {"scope": 0.8, "lowest": 0.7, "location": 0.4})

# Shown to fill up a short list once the text is clearly about inventory
_CORE_GENERIC = ("low_stock", "lowest_stock", "summary", "out_of_stock")

_classifier = IntentClassifier(llm=None)  # rules only — match_rules never calls the LLM


# ── Text matching ───────────────────────────────────────────────────────────

def _tokens(text: str) -> List[str]:
    return _TOKEN.findall((text or "").lower())


def _alnum(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def _topics(tokens: List[str], last_is_partial: bool) -> Tuple[Dict[str, float], set]:
    """Topic strengths from typed words, plus the tokens that were used up as vocabulary."""
    strengths: Dict[str, float] = {}
    used = set()

    def add(word: str, strength: float, token: str) -> None:
        used.add(token)
        for topic in _VOCAB[word]:
            strengths[topic] = max(strengths.get(topic, 0.0), strength)

    for i, token in enumerate(tokens):
        if token in _VOCAB:
            add(token, 1.0, token)
            continue
        if last_is_partial and i == len(tokens) - 1 and len(token) >= 2:
            # "sto" → stock (0.74) beats "sto" → storage (0.67): closer completions score higher
            for word in _VOCAB:
                if word.startswith(token):
                    add(word, 0.5 + 0.4 * len(token) / len(word), token)
            if token in used:
                continue
        if len(token) >= 4 and token not in _STOPWORDS:
            close = difflib.get_close_matches(token, [w for w in _VOCAB if len(w) >= 4], n=1, cutoff=_FUZZY_CUTOFF)
            if close:
                add(close[0], 0.75, token)
    return strengths, used


def _word_strength(token: str, words: List[str], partial: bool) -> float:
    best = 0.0
    for word in words:
        if word == token:
            return 0.9  # a whole word; only an exact SKU / product id scores 1.0
        if word.startswith(token) and (len(token) >= 3 or (partial and len(token) >= 2)):
            best = max(best, 0.7 + 0.2 * len(token) / len(word))
        elif len(token) >= 4 and difflib.SequenceMatcher(None, token, word).ratio() >= _FUZZY_CUTOFF:
            best = max(best, 0.65)
    return best


def _product_strength(product: Dict[str, Any], tokens: List[str], phrase: str, partial: bool) -> float:
    sku = _alnum(product.get("sku"))
    pid = _alnum(product.get("product_id"))
    if not tokens:
        return 0.0
    # SKU / product id: exact beats prefix; "1004" also reaches "SKU-1004"
    for token in tokens:
        t = _alnum(token)
        if len(t) < 2:
            continue
        if t in (sku, pid):
            return 1.0
        digits = re.sub(r"[^0-9]", "", sku)
        if (len(t) >= 3 and (sku.startswith(t) or pid.startswith(t))) or (t.isdigit() and len(t) >= 3
                                                                          and digits.startswith(t)):
            return 0.9
    names = [product.get("name") or "", *(product.get("aliases") or [])]
    best = 0.0
    for name in names:
        name_l = name.lower()
        if phrase and len(phrase) >= 3 and name_l.startswith(phrase):
            return 0.95
        words = _tokens(name_l)
        scores = [_word_strength(t, words, partial and i == len(tokens) - 1) for i, t in enumerate(tokens)]
        if scores and all(s > 0 for s in scores):
            best = max(best, sum(scores) / len(scores))
    return best


def _match_products(products: List[Dict[str, Any]], tokens: List[str], phrase: str,
                    partial: bool) -> List[Tuple[float, Dict[str, Any]]]:
    hits = []
    for product in products:
        strength = _product_strength(product, tokens, phrase, partial)
        if strength >= 0.6:
            hits.append((strength, product))
    hits.sort(key=lambda h: (-h[0], str(h[1].get("name") or "")))
    if hits and hits[0][0] >= 1.0:  # an exact SKU / id names exactly one product
        return hits[:1]
    return hits[:_MAX_PRODUCTS]


def _named_without_digits(product: Dict[str, Any], tokens: List[str], phrase: str, partial: bool) -> bool:
    """The product is named by a full SKU/id or by name words, not only by a number that happens to match."""
    words = [t for t in tokens if not t.isdigit()]
    return bool(words) and _product_strength(product, words, phrase, partial) >= 0.6


def _resolvable_categories(categories: Iterable[str]) -> List[str]:
    """Categories the report parser can pick out alone: one whose name sits inside another's
    ("Equipment" in "Equipment Parts") matches twice there and is refused, so it isn't offered."""
    names = [c for c in categories if c]
    return [c for c in names if not any(
        other != c and re.search(r"(?<!\w)" + re.escape(c.casefold()) + r"(?!\w)", other.casefold())
        for other in names)]


def _match_names(names: Iterable[str], tokens: List[str], partial: bool) -> List[Tuple[float, str]]:
    hits = []
    for name in names:
        words = _tokens(name)
        strength = max((_word_strength(t, words, partial and i == len(tokens) - 1)
                        for i, t in enumerate(tokens) if len(t) >= 3), default=0.0)
        if strength >= 0.7:
            hits.append((strength, name))
    hits.sort(key=lambda h: (-h[0], h[1]))
    return hits[:2]


def _match_floors(floors: List[Dict[str, Any]], tokens: List[str]) -> List[Tuple[float, str]]:
    """'WH1-F2', 'f2', 'floor 2' → that floor id."""
    hits = []
    joined = " ".join(tokens)
    for floor in floors:
        fid = str(floor.get("id") or "")
        if not fid:
            continue
        key = _alnum(fid)
        level = floor.get("level")
        strength = 0.0
        for token in tokens:
            t = _alnum(token)
            if t == key:
                strength = 1.0
            elif len(t) >= 2 and (key.startswith(t) or key.endswith(t)) and any(c.isdigit() for c in t):
                strength = max(strength, 0.8)
        if level is not None and re.search(rf"\bfloor\s*{int(level)}\b", joined):
            strength = max(strength, 0.95)
        if strength:
            hits.append((strength, fid))
    hits.sort(key=lambda h: (-h[0], h[1]))
    return hits[:2]


# ── Building suggestions ────────────────────────────────────────────────────

def _relevance(template: _Template, topics: Dict[str, float]) -> float:
    return max((template.weights.get(topic, 0.0) * strength for topic, strength in topics.items()), default=0.0)


def _label(product: Dict[str, Any]) -> Tuple[str, str]:
    """('Name (SKU-1001)', 'SKU-1001'), using the product id when the SKU can't be resolved by the agent."""
    sku = str(product.get("sku") or "").strip().upper()
    ref = sku if sku and SKU_PATTERN.fullmatch(sku) else str(product.get("product_id") or "").strip().upper()
    name = str(product.get("name") or "").strip()
    return (f"{name} ({ref})" if name and ref else ref or name), ref


def routes_to_inventory(question: str, sub_intent: str) -> bool:
    """True when the coordinator's rules send `question` to the Inventory Agent as `sub_intent`."""
    decision = _classifier.match_rules(question)
    return decision is not None and decision.domain == "INVENTORY" and detect_sub_intent(question) == sub_intent


def _routed(text: str, sub_intent: str, fallback: Optional[str] = None) -> Optional[str]:
    if routes_to_inventory(text, sub_intent):
        return text
    if fallback and routes_to_inventory(fallback, sub_intent):
        return fallback  # e.g. a product name containing "order" pulls the question to fulfillment
    return None


def build_suggestions(text: str, catalog: Optional[Dict[str, Any]] = None,
                      limit: int = MAX_SUGGESTIONS) -> List[Dict[str, Any]]:
    """
    Up to `limit` questions for the partly typed `text`, most relevant first; [] when the text
    isn't about inventory. `catalog` = {"products": [...], "categories": [...], "floors": [...]};
    None or empty means only capability-based questions (no product details).
    """
    limit = max(1, min(int(limit or MAX_SUGGESTIONS), MAX_SUGGESTIONS))
    raw = (text or "").strip()
    if len(re.sub(r"\s", "", raw)) < MIN_CHARS:
        return []
    catalog = catalog or {}
    tokens = _tokens(raw)
    if not tokens:
        return []
    partial = not (text or "").endswith((" ", "?", ".", "!"))

    topics, vocab_tokens = _topics(tokens, partial)
    named = [t for t in tokens if t not in _STOPWORDS and (t not in vocab_tokens or len(t) >= 3)]
    # Name words: anything not consumed as an inventory keyword ("thermal", "scanner", "sku-1004")
    name_tokens = [t for t in tokens if t not in _STOPWORDS and t not in vocab_tokens] or \
                  [t for t in named if re.search(r"\d", t)]
    phrase = " ".join(t for t in tokens if t not in _STOPWORDS and t not in vocab_tokens)

    products = _match_products(catalog.get("products") or [], name_tokens or named, phrase, partial)
    if not catalog.get("products"):
        # No live catalog: an id the user typed in full may be reused, but nothing is looked up or invented
        products = [(0.9, {"sku": m.group(0).upper().replace(" ", "-")}) for m in _TYPED_SKU.finditer(raw)][:1] or \
                   [(0.9, {"product_id": m.group(0).upper()}) for m in _TYPED_PRD.finditer(raw)][:1]
    categories = _match_names(_resolvable_categories(catalog.get("categories") or []), name_tokens or named, partial)
    floors = _match_floors(catalog.get("floors") or [], tokens)
    if categories:
        topics["category"] = max(topics.get("category", 0.0), 0.7)
    if floors:
        topics["scope"] = max(topics.get("scope", 0.0), 0.7)

    # Clearly another agent's question (leave, delivery tracking, SOPs) or a greeting → no suggestions,
    # unless a product is named; a bare number ("order #4521") does not name a product
    decision = _classifier.match_rules(raw)
    if any(t in _FOREIGN for t in tokens) or (decision is not None and (
            decision.domain in ("KNOWLEDGE", "FULFILLMENT") or decision.source in ("meta", "social"))):
        products = [(s, p) for s, p in products if _named_without_digits(p, name_tokens or named, phrase, partial)]
        if not products:
            return []
    if not (topics or products or categories or floors):
        return []

    scored: List[Tuple[float, int, str, str, Optional[str]]] = []  # (score, order, text, kind, sku)
    order = 0

    def add(score: float, question: Optional[str], kind: str, sku: Optional[str] = None) -> None:
        nonlocal order
        if question and score > 0:
            scored.append((score, order, question, kind, sku))
            order += 1

    product_lead = bool(products) and products[0][0] >= 0.8
    for strength, product in products:
        label, ref = _label(product)
        if not ref:
            continue
        for template in PRODUCT_TEMPLATES:
            topical = _relevance(template, topics)
            fit = topical if topics else template.default
            if topics and not topical:
                fit = template.default * 0.35  # other questions about the same product stay below
            question = _routed(template.text.format(label=label, ref=ref), template.sub_intent,
                               template.text.format(label=ref, ref=ref))
            add(strength * (0.55 + 0.45 * fit), question, "product", ref)

    generic_weight = 0.55 if product_lead else 1.0
    for template in GENERIC_TEMPLATES:
        relevance = _relevance(template, topics)
        if relevance:
            add(relevance * generic_weight * 0.95, _routed(template.text, template.sub_intent), "generic")

    for strength, category in categories:
        relevance = max(strength, _relevance(CATEGORY_TEMPLATE, topics))
        add(relevance * 0.9, _routed(CATEGORY_TEMPLATE.text.format(category=category),
                                     CATEGORY_TEMPLATE.sub_intent), "category")

    for strength, floor in floors:
        add(min(1.0, strength + 0.05), _routed(FLOOR_TEMPLATE.text.format(floor=floor), FLOOR_TEMPLATE.sub_intent), "floor")

    scored.sort(key=lambda s: (-s[0], s[1]))
    results: List[Dict[str, Any]] = []
    seen = set()
    for _, _, question, kind, sku in scored:
        key = question.casefold()
        if key in seen:
            continue
        seen.add(key)
        results.append({"text": question, "kind": kind, **({"sku": sku} if sku else {})})
        if len(results) >= limit:
            return results

    # A short list on an inventory topic is filled with core inventory questions, never unrelated ones
    if (topics or categories or floors) and len(results) < min(MIN_SUGGESTIONS, limit):
        by_id = {t.id: t for t in GENERIC_TEMPLATES}
        for template_id in _CORE_GENERIC:
            template = by_id[template_id]
            question = _routed(template.text, template.sub_intent)
            if question and question.casefold() not in seen:
                seen.add(question.casefold())
                results.append({"text": question, "kind": "generic"})
            if len(results) >= min(MIN_SUGGESTIONS, limit):
                break
    return results


# ── Catalog (read-only) ─────────────────────────────────────────────────────

_twin_cache: Dict[str, Any] = {"at": 0.0, "catalog": None}


def _catalog_from_rows(products: List[Dict[str, Any]], floors: List[Dict[str, Any]]) -> Dict[str, Any]:
    slim = [{"sku": p.get("sku"), "product_id": p.get("product_id"), "name": p.get("name"),
             "category": p.get("category"), "aliases": list(p.get("aliases") or [])} for p in products]
    categories = sorted({str(p["category"]).strip() for p in slim if p.get("category") and str(p["category"]).strip()})
    return {"products": slim, "categories": categories,
            "floors": [{"id": f.get("id"), "level": f.get("level")} for f in floors]}


def _twin_catalog() -> Dict[str, Any]:
    from database.twin import repository

    now = time.monotonic()
    cached = _twin_cache["catalog"]
    if cached is not None and now - _twin_cache["at"] < _CATALOG_TTL_S:
        return cached
    catalog = _catalog_from_rows(repository.get_product_totals(), repository.get_floors())
    _twin_cache.update(at=now, catalog=catalog)
    return catalog


def _legacy_catalog(db) -> Dict[str, Any]:
    from database.models import Product

    rows = (db.query(Product.sku, Product.name, Product.category)
            .order_by(Product.sku).limit(_LEGACY_ROW_LIMIT).all())
    return _catalog_from_rows([{"sku": r.sku, "name": r.name, "category": r.category} for r in rows], [])


def load_catalog(db=None) -> Optional[Dict[str, Any]]:
    """Product names/SKUs/categories (and twin floors) for suggestions; None when the lookup fails."""
    from database import inventory_source

    try:
        if inventory_source.uses_twin():
            return _twin_catalog()
        if db is None:
            return None
        return _legacy_catalog(db)
    except Exception as exc:  # suggestions degrade to capability questions; chat keeps working
        logger.log_event("INVENTORY_SUGGESTIONS_CATALOG_FAILED", {"error": type(exc).__name__}, level="WARNING")
        return None
