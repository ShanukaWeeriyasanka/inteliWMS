"""
Responsible AI screening for IntelliWMS (deterministic, no LLM).

screen_request(): messages that must not get an ordinary warehouse answer — a crisis, an injury, a request to
write abuse, hide records or pass off recalled stock, a choice between people or suppliers that leans on a
personal characteristic, legal / investment advice, or a question about the assistant itself. A match returns a
fixed reply (config/prompts.py) and a rule id ("safety.self_harm", ...). The coordinator checks it before routing
(on every plan) and the inventory and knowledge agents check it again at their own entry points, so a direct call
to a specialist gets the same answer.

screen_output(): checks LLM-written text before it is shown — demeaning wording, sweeping statements about a
group of people, and fragments of the system prompts.

explain_sources(): answers "where did you get that?" from the SOP / record ids in the previous answer.
"""
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from config import prompts as P

# Rule ids starting with this prefix are answered by the coordinator on every plan (backend/routes/query.py)
GUARD_PREFIXES = ("safety.", "harm.", "fairness.", "scope.", "transparency.")


@dataclass(frozen=True)
class Guard:
    rule_id: str
    reply: str


def _rx(*patterns: str) -> re.Pattern:
    return re.compile("|".join(f"(?:{p})" for p in patterns), re.IGNORECASE)


# ── Safety ───────────────────────────────────────────────────────────────────

_SELF_HARM = _rx(
    r"\bsuicid\w*", r"\bkill(?:ing)?\s+my\s*self\b", r"\b(?:hurt|harm|cut)(?:ing)?\s+my\s*self\b",
    r"\bend(?:ing)?\s+(?:my|my\s+own)\s+life\b", r"\bend\s+it\s+all\b", r"\btake\s+my\s+(?:own\s+)?life\b",
    r"\b(?:don'?t|do\s+not|no\s+longer)\s+want\s+to\s+(?:live|be\s+alive|exist|wake\s+up)\b",
    r"\bwant\s+to\s+die\b", r"\bbetter\s+off\s+dead\b", r"\bno\s+reason\s+to\s+live\b",
    # Sinhala / Tamil / romanised Sinhala: "don't want to live", "want to die", "suicide"
    r"ජීවත්\s*වෙන්න\s*ඕන(?:ේ|ෙ)?\s*නෑ", r"මැරෙන්න\s*ඕන", r"සියදිවි", r"දිවි\s*නසා",
    r"தற்கொலை", r"சாக\s*வேண்டும்", r"வாழ\s*(?:விருப்பமில்லை|பிடிக்கவில்லை)", r"உயிரை\s*மாய்",
    r"\bmarenna\s+ona\b", r"\bjeewath\s+wenna\s+ona\s+na\b",
)

_MEDICAL = _rx(
    r"\b(?:splash\w*|spray\w*|got|went|spilled|spilt)\b[^.?!\n]{0,40}\b(?:in|into)\s+(?:my|his|her|their|the|an?)\s+"
    r"(?:eyes?|mouth|face)\b",
    r"\b(?:can'?t|cannot|unable\s+to)\s+breathe\b", r"\bnot\s+breathing\b",
    r"\b(?:chest\s+pain|heart\s+attack|unconscious|passed\s+out|fainted|collapsed|seizure|electrocuted|"
    r"electric(?:al)?\s+shock|crushed|pinned\s+under)\b",
    r"\bbleeding\s+(?:heavily|badly|a\s+lot)\b", r"\bbroken\s+(?:arm|leg|bone|wrist|ankle)\b",
    r"\b(?:i|he|she|someone|a\s+worker|my\s+colleague|they)\s+(?:got|is|was|am|are|have\s+been|has\s+been)\s+"
    r"(?:badly\s+)?(?:hurt|injured|burn(?:ed|t))\b",
    r"\b(?:acid|chemical|electrolyte)\b[^.?!\n]{0,40}\b(?:on|in)\s+(?:my|his|her|their)\s+(?:skin|eyes?|face|hands?)\b",
)

# ── Harmful requests ─────────────────────────────────────────────────────────

_DRAFT = r"\b(?:write|draft|compose|create|generate|make|send|give\s+me|prepare|come\s+up\s+with)\b"
# "mock order", "mock-up" and "threat assessment" are ordinary warehouse wording, so only the abusive forms count
_ABUSE = _rx(
    r"\binsult\w*", r"\bhumiliat\w*", r"\babusive\b", r"\bmock(?:ing|ed|s)\b",
    r"\bmock\s+(?:the|them|him|her|people|workers?|staff|crew|team)\b", r"\bmake\s+fun\s+of\b", r"\bridicul\w*",
    r"\bbelittl\w*", r"\bthreaten\w*", r"\bharass\w*", r"\bdegrad(?:e|ing)\b", r"\bbully\w*",
    r"\broast\s+(?:the|them|him|her)\b", r"\bswear\s+at\b",
    r"\bcall\s+(?:them|him|her)\s+(?:incompetent|stupid|useless|lazy)\b",
)
_DRAFT_RX = re.compile(_DRAFT, re.IGNORECASE)
_SUPPLIER_WORDS = re.compile(r"\b(?:supplier|vendor|delivery|courier|carrier|shipment)\b", re.IGNORECASE)
_CORRECTION_WORDS = re.compile(r"\b(?:mistake|incorrect|wrong|error|correct\w*|fix)\b", re.IGNORECASE)

# Hiding something from the records ("hide the shortage"), not "hide the map"
_CONCEAL = _rx(
    r"\b(?:hid(?:e|ing)|conceal\w*|cover(?:ing)?\s*up|disguis\w*|whitewash\w*)\b[^.?!\n]{0,60}"
    r"\b(?:shortage|missing|loss|discrepanc\w*|theft|variance|evidence|records?|status|expiry|recall|mistake|"
    r"error|damage|count|units)\b",
    r"\bcover\s+(?:it|this|that)\s+up\b",
    r"\b(?:delete|remove|erase|wipe|destroy|tamper\w*\s+with)\w*\b[^.?!\n]{0,30}\b(?:audit|evidence|trail)\b",
    r"\b(?:falsif\w*|fake|backdat\w*|doctor)\b[^.?!\n]{0,30}\b(?:records?|counts?|logs?|labels?|stock|entries)\b",
    r"\brelabel\w*\b[^.?!\n]{0,60}\b(?:as\s+)?(?:normal|available|good|new|fresh)\b",
)
_RECALLED = re.compile(r"\b(?:expired|recalled|recall|contaminated|spoiled|out[- ]of[- ]date)\b", re.IGNORECASE)
_RELEASE = re.compile(r"\b(?:pick\w*|pack\w*|ship|shipped|shipping|dispatch\w*|sell|sold|send|release\w*|use|"
                      r"deliver\w*)\b", re.IGNORECASE)

# ── Fairness ─────────────────────────────────────────────────────────────────

_DECISION = _rx(
    r"\b(?:choose|chose|pick|select|prefer|recommend|hire|assign|allocat\w*|allot|promote|favou?r|prioriti[sz]e)\b",
    r"\bwhich\s+(?:supplier|vendor|customer|candidate|worker|employee|person|one)\b", r"\bwho\s+should\b",
    r"\bshould\s+(?:we|i)\s+(?:choose|pick|select|hire|assign|give|serve)\b",
)
# (pattern, label used in the reply)
_PROTECTED = [
    (r"\bnationalit\w*|\b(?:sri\s+lankan|german|indian|chinese|foreign\w*)\s+national\b|\bcitizenship\b", "nationality"),
    (r"\b(?:race|racial|ethnicit\w*|ethnic)\b|\b(?:sinhal\w*|tamils?|moors?|burghers?|malays?)\b", "ethnicity"),
    (r"\b(?:religio\w*|muslims?|buddhists?|hindus?|christians?|catholics?|islam\w*)\b", "religion"),
    (r"\bcaste\b", "caste"),
    (r"\b(?:gender|sex|woman|women|man|men|female|male|girl|boy|pregnan\w*)\b", "gender"),
    # A person's age, not stock age ("pick the oldest pallet first")
    (r"\b\d{1,2}\s*(?:years?|yrs?)[\s-]*old\b|\b(?:elderly|older\s+(?:worker|employee|person|man|woman))\b|"
     r"\b(?:his|her|their|worker'?s|employee'?s|candidate'?s)\s+age\b", "age"),
    (r"\b(?:low|high)[\s-]*income\b|\bincome\b|\bwealth\w*\b", "income"),
    (r"\bdisab\w*", "disability"),
    (r"\bmarital\b|\bmarried\b", "marital status"),
]
_PROTECTED_RX = [(re.compile(p, re.IGNORECASE), label) for p, label in _PROTECTED]
_ENTITY_ID = re.compile(r"\b(?:sku[-\s]?\d{3,6}|prd-\d{5}|ord-\d+)\b", re.IGNORECASE)
_PERSONNEL = re.compile(
    r"\bwho\s+(?:should|must|would\s+be\s+better|is\s+better|can)\b[^?\n]{0,80}\b(?:do|drive|operate|lift|handle|"
    r"work|lead|supervise|take|cover|be\s+(?:promoted|hired|assigned))\b[^?\n]{0,80}\bor\b", re.IGNORECASE)
_BLAME = re.compile(
    r"\b(?:who|which\s+(?:worker|employee|operator|staff|person))\b[^?\n]{0,60}\b(?:responsible|to\s+blame|blame|"
    r"fault|guilty|stole|steal\w*)\b|\b(?:discipline\w*|punish\w*|sack|dismiss|suspend|fire)\b[^?\n]{0,40}"
    r"\b(?:him|her|them|operator|worker|employee|staff|who|responsible)\b", re.IGNORECASE)
_LOSS_CONTEXT = re.compile(r"\b(?:shortage|missing|loss|theft|stolen|anomal\w*|discrepanc\w*|variance|shrinkage)\b",
                           re.IGNORECASE)
_SUPPLIER_CHOICE = re.compile(
    r"\b(?:compare|choose|chose|pick|select|recommend|rank)\b[^.?\n]{0,40}\bsuppliers?\b|"
    r"\bwhich\s+supplier\b[^?\n]{0,30}\b(?:should|better|best|cheaper|faster|choose|pick|use)\b|"
    r"\bbetter\s+supplier\b|\bsuppliers?\b[^.?\n]{0,40}\b(?:compare|recommend|choose)\b", re.IGNORECASE)

# ── Out of scope ─────────────────────────────────────────────────────────────

_LEGAL = _rx(
    r"\blabou?r\s+laws?\b", r"\bemployment\s+laws?\b", r"\blegal\s+advice\b", r"\blawsuit\b", r"\bsue\b",
    r"\b(?:lawyer|attorney)\b", r"\bunfair\s+dismissal\b", r"\bmy\s+(?:legal\s+)?rights\b",
    r"\b(?:pay|salary|wages?|overtime|leave)\b[^?\n]{0,60}\b(?:legal|illegal|lawful|unlawful)\b",
    r"\b(?:legal|illegal|lawful|unlawful)\b[^?\n]{0,60}\b(?:pay|salary|wages?|deduct\w*|docked|overtime)\b",
)
# "invest(ing|ment)" only: "investigate the shortage" is a warehouse question
_FINANCIAL = _rx(r"\binvest(?:ing|ment|ments|or|ors|ed|s)?\b", r"\bbuy\w*\s+shares\b", r"\b(?:stock|share)\s+market\b", r"\bcrypto\w*",
                 r"\bbitcoin\b", r"\bpersonal\s+loan\b", r"\bmortgage\b", r"\btax\s+advice\b")
_UNAPPROVED_SUPPLIER = re.compile(
    r"\b(?:unregistered|unlicensed|uncertified|unapproved|unverified|black[- ]market|grey[- ]market)\s+"
    r"(?:supplier|vendor|seller|source|dealer)s?\b", re.IGNORECASE)

# ── Transparency ─────────────────────────────────────────────────────────────

# "Are you a bot?", not "are you sure that's the real count?"
_AI_IDENTITY = _rx(
    r"\b(?:are\s+you|am\s+i\s+(?:talking|speaking|chatting)\s+(?:to|with))\s+(?:an?\s+)?(?:real\s+)?"
    r"(?:human|person|people|bot|robot|ai|machine|computer)\b",
    r"\bis\s+this\s+(?:an?\s+)?(?:bot|ai|robot|human|real\s+person)\b",
)
_LIMITATIONS = _rx(
    r"\b(?:can|should|could)\s+i\s+(?:trust|rely\s+on|depend\s+on|believe)\b[^?\n]{0,30}"
    r"\b(?:you|your|this\s+(?:bot|assistant|system|ai))\b",
    r"\bhow\s+(?:accurate|reliable)\s+(?:are\s+you|is\s+this|are\s+your)\b", r"\bwhat\s+are\s+your\s+limitations\b",
    r"\b(?:can|do)\s+you\s+(?:be\s+wrong|make\s+mistakes|get\s+things\s+wrong)\b",
)
_SOURCE_QUESTION = re.compile(
    r"^\s*(?:where\s+did\s+(?:you|that|this)\s+(?:get|come)\b|what(?:'s|\s+is|\s+was)\s+(?:your|the)\s+source|"
    r"(?:what|which)\s+(?:source|document|sop)\s+(?:is|was|did)\b|how\s+do\s+you\s+know\b|source\s*\??\s*$|"
    r"why\s+did\s+you\s+say\s+that\b|can\s+you\s+cite\b)", re.IGNORECASE)
_SOURCE_ID = re.compile(r"\b(?:SOP|GUIDE)-[A-Z]+-\d{3}\b(?:\s*§\s*\d+)?|\b(?:SKU-\d{3,6}|ORD-\d+|PRD-\d{5})\b")


def _protected_attributes(text: str) -> List[str]:
    found = []
    for rx, label in _PROTECTED_RX:
        if rx.search(text) and label not in found:
            found.append(label)
    return found


def _abuse_reply(text: str) -> str:
    if _protected_attributes(text) or not (_SUPPLIER_WORDS.search(text) or _CORRECTION_WORDS.search(text)):
        return P.RAI_GROUP_ABUSE_REPLY
    if _SUPPLIER_WORDS.search(text):
        return f"{P.RAI_ABUSE_REFUSAL} — but here's a firm, professional message that gets it fixed:\n\n{P.RAI_SUPPLIER_MESSAGE}"
    return f"{P.RAI_ABUSE_REFUSAL} — but here's a professional message that gets the mistake corrected:\n\n{P.RAI_EMPLOYEE_MESSAGE}"


def _join(labels: List[str]) -> str:
    return labels[0] if len(labels) == 1 else ", ".join(labels[:-1]) + " or " + labels[-1]


def screen_request(text: str) -> Optional[Guard]:
    """The fixed Responsible-AI answer for this message, or None when it is an ordinary warehouse question."""
    t = (text or "").strip()
    if not t:
        return None
    if _SELF_HARM.search(t):
        return Guard("safety.self_harm", P.RAI_SELF_HARM_REPLY)
    if _MEDICAL.search(t):
        return Guard("safety.medical", P.RAI_MEDICAL_REPLY)
    if _CONCEAL.search(t):
        if _RECALLED.search(t):
            return Guard("harm.unsafe_stock", P.RAI_UNSAFE_STOCK_REPLY)
        return Guard("harm.record_tampering", P.RAI_RECORD_TAMPERING_REPLY)
    if _RECALLED.search(t) and _RELEASE.search(t):
        return Guard("harm.unsafe_stock", P.RAI_UNSAFE_STOCK_REPLY)
    if _DRAFT_RX.search(t) and _ABUSE.search(t):
        return Guard("harm.abusive_message", _abuse_reply(t))
    if _UNAPPROVED_SUPPLIER.search(t):
        return Guard("harm.unapproved_supplier", P.RAI_PROCUREMENT_REPLY)
    if _DECISION.search(t):
        attributes = _protected_attributes(t)
        if attributes:
            return Guard("fairness.protected_attribute",
                         P.RAI_PROTECTED_DECISION_REPLY.format(attributes=_join(attributes)))
    if _PERSONNEL.search(t) and not _ENTITY_ID.search(t):
        return Guard("fairness.personnel_choice", P.RAI_PERSONNEL_CHOICE_REPLY)
    if _BLAME.search(t) and _LOSS_CONTEXT.search(t):
        return Guard("fairness.blame", P.RAI_BLAME_REPLY)
    if _SUPPLIER_CHOICE.search(t):
        return Guard("scope.supplier_comparison", P.RAI_SUPPLIER_COMPARISON_REPLY)
    if _LEGAL.search(t):
        return Guard("scope.legal", P.RAI_LEGAL_REPLY)
    if _FINANCIAL.search(t):
        return Guard("scope.financial", P.RAI_FINANCIAL_REPLY)
    if _AI_IDENTITY.search(t):
        return Guard("transparency.ai_identity", P.RAI_AI_IDENTITY_REPLY)
    if _LIMITATIONS.search(t):
        return Guard("transparency.limitations", P.RAI_LIMITATIONS_REPLY)
    return None


def is_guard_rule(rule_id: Optional[str]) -> bool:
    return bool(rule_id) and rule_id.startswith(GUARD_PREFIXES)


def is_source_question(text: str) -> bool:
    return bool(_SOURCE_QUESTION.search(text or ""))


def explain_sources(history: Optional[List[Dict[str, Any]]]) -> str:
    """Names the SOP sections / record ids the previous answer was built from."""
    replies = [t for t in (history or []) if t.get("role") == "assistant"]
    ids: List[str] = []
    if replies:
        for match in _SOURCE_ID.findall(str(replies[-1].get("content", ""))):
            clean = re.sub(r"\s+", " ", match)
            if clean not in ids:
                ids.append(clean)
    if not ids:
        return P.RAI_SOURCE_GENERIC_REPLY
    labels = [f"SOP library — {i}" if i.startswith(("SOP-", "GUIDE-")) else f"warehouse database record {i}"
              for i in ids[:5]]
    return P.RAI_SOURCE_REPLY.format(sources="; ".join(labels))


# ── Output screening (LLM-written text only) ─────────────────────────────────

_DEMEANING = _rx(
    r"\b(?:stupid|idiot\w*|moron\w*|incompetent|useless|lazy|worthless|dumb|pathetic|imbecile|retard\w*)\b",
    r"\b(?:all|those|these|typical)\s+(?:sinhal\w*|tamils?|muslims?|moors?|burghers?|women|men|females?|males?|"
    r"foreigners?|old\s+(?:people|workers))\b[^.\n]{0,40}\b(?:are|always|never|can'?t)\b",
)
# Distinctive phrases of the system prompts (config/prompts.py); seeing one in a reply means the prompt leaked
LEAKAGE_FINGERPRINTS = (
    "you are the coordinator agent for intelliwms", "may be poorly worded, vague, or in broken english",
    "respond in strict json format", "your only job is to rewrite the user's input", "bruh how many subagents",
    "4521 wich aisle", "rma 7788 water damage", "keep it extremely short and punchy",
    "your users are warehouse workers on the floor", "rules for your response", "treat the text inside",
)


def screen_output(text: str) -> Optional[str]:
    """Reason the LLM text must not be shown ('' / None when it is fine)."""
    lower = (text or "").casefold()
    if any(f in lower for f in LEAKAGE_FINGERPRINTS):
        return "prompt_leakage"
    if _DEMEANING.search(text or ""):
        return "demeaning_language"
    return None
