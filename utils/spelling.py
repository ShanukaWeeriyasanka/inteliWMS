"""
Global Spelling Correction & Fuzzy Matching Utility for IntelliWMS.

Handles:
- Missing letters / omissions (e.g., 'quck' -> 'quick')
- Scrambled / transposed letters (e.g., 'qiuck' -> 'quick', 'froklift' -> 'forklift')
- Wrong / substituted letters (e.g., 'qwick' -> 'quick')
- Extra / inserted letters (e.g., 'quuick' -> 'quick')
- Phonetic misspellings (e.g., 'quik' -> 'quick')

Protects:
- Formatted domain IDs (SKU-1004, ORD-4521, PRD-00002, WH01-F02, #4521, FL-01)
- Numeric values, units, email addresses, and URLs
- Preserves original capitalization and sentence punctuation
"""
import re
from collections import Counter
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


# =============================================================================
# 1. PROTECTED ENTITY PATTERNS (Never modify IDs or codes)
# =============================================================================
_PROTECTED_PATTERNS = [
    re.compile(r"^(?:sku|ord|prd|wh|bld|fl|agv)[-\s]?\d+", re.IGNORECASE),
    re.compile(r"^#\d+$"),
    re.compile(r"^\d+(?:[.,]\d+)?(?:kg|g|lb|oz|m|cm|mm|ft|in|%|c|f)?$", re.IGNORECASE),
    re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"),
    re.compile(r"^https?://\S+$"),
    re.compile(r"^wh\d+(?:-f\d+)?(?:-z\d{2})?(?:-r\d{2})?(?:-s\d{2})?(?:-b\d{2})?$", re.IGNORECASE),
]

def is_protected_token(token: str) -> bool:
    """True if token is a warehouse entity code, number, or identifier."""
    if not token or len(token) <= 1:
        return True
    return any(p.match(token) for p in _PROTECTED_PATTERNS)


# =============================================================================
# 2. CORE INTELLIWMS WAREHOUSE & ENGLISH LEXICON
# =============================================================================
_CORE_WAREHOUSE_VOCABULARY = [
    # Question & action verbs
    ("what", 50), ("where", 50), ("when", 40), ("which", 45), ("how", 50), ("who", 30),
    ("is", 50), ("are", 50), ("was", 30), ("were", 30), ("can", 45), ("could", 35),
    ("would", 30), ("should", 30), ("will", 35), ("do", 40), ("does", 40), ("did", 30),
    ("have", 45), ("has", 45), ("had", 30), ("get", 45), ("find", 45), ("check", 50),
    ("show", 50), ("tell", 40), ("list", 45), ("locate", 45), ("give", 40), ("help", 45),
    ("quick", 55), ("quickly", 40), ("fast", 35), ("please", 40), ("look", 35), ("search", 40),
    ("track", 45), ("trace", 35), ("update", 40), ("create", 35), ("modify", 30), ("cancel", 35),
    ("verify", 35), ("confirm", 35), ("audit", 40), ("count", 45), ("inspect", 35),

    # Prepositions & connectors
    ("the", 60), ("a", 50), ("an", 40), ("in", 50), ("on", 45), ("at", 45), ("to", 50),
    ("for", 50), ("from", 45), ("with", 40), ("by", 35), ("about", 40), ("into", 35),
    ("under", 35), ("over", 35), ("between", 35), ("and", 50), ("or", 40), ("not", 45),
    ("any", 40), ("all", 40), ("some", 35), ("many", 40), ("much", 45), ("more", 40),
    ("less", 35), ("most", 40), ("least", 35), ("lowest", 50), ("highest", 50), ("low", 45),
    ("high", 45), ("out", 45), ("empty", 40), ("full", 40),

    # Core Warehouse & Inventory terms
    ("inventory", 60), ("stock", 60), ("quantity", 55), ("product", 55), ("products", 50),
    ("item", 50), ("items", 50), ("sku", 55), ("skus", 45), ("order", 60), ("orders", 55),
    ("status", 55), ("reorder", 50), ("restock", 45), ("transfer", 50), ("transfers", 45),
    ("replenish", 45), ("replenishment", 45), ("shipment", 50), ("shipments", 45),
    ("delivery", 50), ("deliveries", 45), ("dispatch", 45), ("dispatched", 40),
    ("shipping", 50), ("receiving", 50), ("staging", 45), ("picking", 50), ("packing", 50),
    ("fulfill", 45), ("fulfilled", 40), ("fulfillment", 55), ("delayed", 45), ("delay", 40),
    ("pending", 45), ("in-transit", 40), ("transit", 40), ("carrier", 45), ("carriers", 40),
    ("supplier", 45), ("customer", 45), ("return", 45), ("returns", 40), ("damaged", 45),
    ("damage", 45), ("loss", 40), ("defect", 35), ("quarantine", 40), ("scrap", 35),
    ("summary", 50), ("report", 50), ("forecast", 45), ("prediction", 40), ("anomaly", 40),

    # Spatial, Facility, & Digital Twin locations
    ("warehouse", 60), ("facility", 50), ("facilities", 45), ("campus", 45), ("building", 50),
    ("floor", 50), ("floors", 45), ("zone", 50), ("zones", 45), ("aisle", 50), ("aisles", 45),
    ("rack", 50), ("racks", 45), ("shelf", 50), ("shelves", 45), ("tier", 45), ("tiers", 40),
    ("bay", 50), ("bays", 45), ("bin", 50), ("bins", 45), ("slot", 45), ("slots", 40),
    ("dock", 50), ("docks", 45), ("gate", 45), ("gates", 40), ("cold", 50), ("vault", 45),
    ("freezer", 45), ("chilled", 45), ("ambient", 40), ("temperature", 40), ("humidity", 35),
    ("capacity", 45), ("utilization", 45), ("occupancy", 45),

    # Equipment & Operations
    ("forklift", 50), ("forklifts", 45), ("vehicle", 45), ("vehicles", 40), ("fleet", 40),
    ("pallet", 50), ("pallets", 45), ("crate", 45), ("crates", 40), ("carton", 40),
    ("box", 45), ("package", 45), ("packages", 40), ("scanner", 45), ("scanners", 40),
    ("printer", 40), ("barcode", 45), ("barcodes", 40), ("rfid", 40), ("label", 45),
    ("hazmat", 45), ("hazardous", 40), ("flammable", 40), ("chemical", 40), ("battery", 40),
    ("safety", 45), ("protocol", 45), ("procedure", 50), ("sop", 55), ("guideline", 45),
    ("policy", 40), ("manual", 40), ("shift", 45), ("staff", 45), ("worker", 40),
    ("manager", 40), ("supervisor", 40), ("driver", 40),

    # Agent Personas & System Terms
    ("coordinator", 50), ("specialist", 45), ("assistant", 40), ("agent", 50),
    ("starter", 40), ("professional", 45), ("enterprise", 45), ("subscription", 40),
    ("plan", 45), ("upgrade", 40), ("twin", 45), ("digital", 45), ("map", 50),
]


# =============================================================================
# 3. DAMERAU-LEVENSHTEIN DISTANCE
# =============================================================================
def damerau_levenshtein_distance(s1: str, s2: str) -> int:
    """
    Calculates the Damerau-Levenshtein distance between s1 and s2:
    Counts insertions, deletions, substitutions, and adjacent character transpositions.
    """
    len1, len2 = len(s1), len(s2)
    if s1 == s2:
        return 0
    if len1 == 0:
        return len2
    if len2 == 0:
        return len1

    # Matrix allocation
    d = [[0] * (len2 + 2) for _ in range(len1 + 2)]
    max_dist = len1 + len2
    d[0][0] = max_dist

    for i in range(0, len1 + 1):
        d[i + 1][1] = i
        d[i + 1][0] = max_dist
    for j in range(0, len2 + 1):
        d[1][j + 1] = j
        d[0][j + 1] = max_dist

    da: Dict[str, int] = {}
    for i in range(1, len1 + 1):
        db = 0
        for j in range(1, len2 + 1):
            k = da.get(s2[j - 1], 0)
            l = db
            cost = 0 if s1[i - 1] == s2[j - 1] else 1
            if cost == 0:
                db = j

            d[i + 1][j + 1] = min(
                d[i][j + 1] + 1,          # deletion
                d[i + 1][j] + 1,          # insertion
                d[i][j] + cost,            # substitution
                d[k][l] + (i - k - 1) + 1 + (j - l - 1)  # transposition
            )
        da[s1[i - 1]] = i

    return d[len1 + 1][len2 + 1]


def similarity_ratio(s1: str, s2: str) -> float:
    """Returns a normalized similarity score between 0.0 and 1.0."""
    max_len = max(len(s1), len(s2))
    if max_len == 0:
        return 1.0
    dist = damerau_levenshtein_distance(s1, s2)
    return max(0.0, 1.0 - (dist / max_len))


# =============================================================================
# 4. SOUNDEX PHONETIC MATCHING
# =============================================================================
def soundex(token: str) -> str:
    """Computes the American Soundex code for phonetic comparison."""
    token = token.upper()
    if not token or not token[0].isalpha():
        return "0000"

    code_map = {
        'B': '1', 'F': '1', 'P': '1', 'V': '1',
        'C': '2', 'G': '2', 'J': '2', 'K': '2', 'Q': '2', 'S': '2', 'X': '2', 'Z': '2',
        'D': '3', 'T': '3',
        'L': '4',
        'M': '5', 'N': '5',
        'R': '6'
    }
    first_letter = token[0]
    tail = token[1:]
    encoded = []
    prev_code = code_map.get(first_letter, '0')

    for char in tail:
        code = code_map.get(char, '0')
        if code != '0' and code != prev_code:
            encoded.append(code)
        prev_code = code

    res = first_letter + "".join(encoded)
    return (res + "0000")[:4]


# =============================================================================
# 5. SPELL CORRECTOR ENGINE
# =============================================================================
class SpellCorrector:
    """
    Robust, production-grade spelling corrector and fuzzy matcher
    customized for IntelliWMS warehouse queries and natural language chat.
    """

    def __init__(self, initial_vocab: Optional[Iterable[Tuple[str, int]]] = None):
        self._vocab: Counter[str] = Counter()
        self._soundex_index: Dict[str, Set[str]] = {}

        # Load default warehouse dictionary
        vocab_items = initial_vocab or _CORE_WAREHOUSE_VOCABULARY
        self.learn_weighted_words(vocab_items)

    def learn_word(self, word: str, weight: int = 1) -> None:
        """Register a word into the active vocabulary."""
        w = word.strip().lower()
        if not w or is_protected_token(w):
            return
        self._vocab[w] += weight
        sx = soundex(w)
        if sx not in self._soundex_index:
            self._soundex_index[sx] = set()
        self._soundex_index[sx].add(w)

    def learn_words(self, words: Iterable[str], default_weight: int = 10) -> None:
        """Add a list of words or product names to vocabulary."""
        for word in words:
            # Tokenize phrases into single words as well
            for part in re.findall(r"[a-zA-Z0-9_-]+", str(word)):
                self.learn_word(part, weight=default_weight)

    def learn_weighted_words(self, items: Iterable[Tuple[str, int]]) -> None:
        """Add tuples of (word, weight)."""
        for w, weight in items:
            self.learn_word(w, weight)

    def learn_catalog(self, catalog: Dict[str, Any]) -> None:
        """
        Dynamically learn words from database catalog (products, categories, facilities).
        """
        if not catalog:
            return
        # Products
        for p in catalog.get("products") or []:
            if isinstance(p, dict):
                self.learn_words([p.get("name", ""), p.get("category", "")], default_weight=20)
                for alias in p.get("aliases") or []:
                    self.learn_words([alias], default_weight=15)
        # Categories
        for cat in catalog.get("categories") or []:
            self.learn_words([cat], default_weight=25)
        # Facilities / buildings
        for f in catalog.get("facilities") or []:
            if isinstance(f, dict):
                self.learn_words([f.get("name", ""), f.get("building_id", "")], default_weight=30)

    @property
    def vocabulary_size(self) -> int:
        return len(self._vocab)

    def is_known(self, word: str) -> bool:
        """True if word is already in the dictionary."""
        return word.lower() in self._vocab

    # ── Edit Generation (Distance 1 & 2) ──────────────────────────────────────

    @staticmethod
    def _edits1(word: str) -> Set[str]:
        """All strings with 1 edit (deletion, transposition, substitution, insertion)."""
        letters = 'abcdefghijklmnopqrstuvwxyz'
        splits = [(word[:i], word[i:]) for i in range(len(word) + 1)]
        
        deletes = [L + R[1:] for L, R in splits if R]
        transposes = [L + R[1] + R[0] + R[2:] for L, R in splits if len(R) > 1]
        replaces = [L + c + R[1:] for L, R in splits if R for c in letters]
        inserts = [L + c + R for L, R in splits for c in letters]
        
        return set(deletes + transposes + replaces + inserts)

    def _edits2(self, word: str) -> Set[str]:
        """All strings with 2 edits."""
        return set(e2 for e1 in self._edits1(word) for e2 in self._edits1(e1))

    # ── Candidate Resolution ──────────────────────────────────────────────────

    def candidates(self, word: str) -> Set[str]:
        """
        Generate ranked candidate corrections for a word.
        Priority:
        1. Exact known word
        2. Known words at edit distance 1 (handles: quck -> quick, qiuck -> quick)
        3. Known words at edit distance 2 (for words with len >= 4)
        4. Phonetic candidates (soundex match)
        """
        w = word.lower()
        if w in self._vocab:
            return {w}

        # 1-edit matches
        known_e1 = {e for e in self._edits1(w) if e in self._vocab}
        if known_e1:
            return known_e1

        # 2-edit matches (only for words long enough to prevent false positives)
        if len(w) >= 4:
            known_e2 = {e for e in self._edits2(w) if e in self._vocab}
            if known_e2:
                return known_e2

        # Phonetic matches
        sx = soundex(w)
        phonetic = self._soundex_index.get(sx, set())
        if phonetic:
            # Filter phonetic to those with reasonable distance (<= 2)
            close_phonetic = {p for p in phonetic if damerau_levenshtein_distance(w, p) <= 2}
            if close_phonetic:
                return close_phonetic

        return {w}

    # ── Word Correction ───────────────────────────────────────────────────────

    @lru_cache(maxsize=4096)
    def correct_word(self, word: str) -> str:
        """
        Returns the best corrected version of a single word, preserving original casing.
        """
        if not word or is_protected_token(word):
            return word

        w = word.lower()
        if w in self._vocab:
            return word

        possible = self.candidates(w)
        if not possible or possible == {w}:
            return word

        # Rank candidates by:
        # 1. Similarity ratio (Damerau-Levenshtein)
        # 2. Vocabulary frequency / probability
        def score(cand: str) -> Tuple[float, int]:
            sim = similarity_ratio(w, cand)
            freq = self._vocab.get(cand, 0)
            return (sim, freq)

        best = max(possible, key=score)
        
        # Only accept if similarity is at least 65%
        if similarity_ratio(w, best) < 0.65:
            return word

        return self._match_case(word, best)

    # ── Sentence / Query Correction ───────────────────────────────────────────

    def correct_query(self, query: str) -> str:
        """
        Corrects misspelled words in a full natural language query while
        preserving whitespace, punctuation, capitalization, and entity codes.
        
        Example:
          "can you quck check the stck for sku-1004?"
          -> "can you quick check the stock for sku-1004?"
        """
        if not query or not query.strip():
            return query

        tokens = re.findall(r"[a-zA-Z0-9_-]+|[^\w\s]|\s+", query)
        corrected_parts = []

        for token in tokens:
            # Only process word tokens
            if re.match(r"^[a-zA-Z]{2,}$", token):
                corrected_parts.append(self.correct_word(token))
            else:
                corrected_parts.append(token)

        return "".join(corrected_parts)

    def correct_query_detailed(self, query: str) -> Dict[str, Any]:
        """
        Corrects a query and returns audit metadata showing all corrections made.
        """
        if not query:
            return {"original": query, "corrected": query, "has_corrections": False, "changes": []}

        tokens = re.findall(r"[a-zA-Z0-9_-]+|[^\w\s]|\s+", query)
        corrected_parts = []
        changes = []

        for token in tokens:
            if re.match(r"^[a-zA-Z]{2,}$", token):
                corr = self.correct_word(token)
                if corr != token:
                    changes.append({
                        "original": token,
                        "corrected": corr,
                        "distance": damerau_levenshtein_distance(token.lower(), corr.lower()),
                        "similarity": round(similarity_ratio(token.lower(), corr.lower()), 3),
                    })
                corrected_parts.append(corr)
            else:
                corrected_parts.append(token)

        corrected = "".join(corrected_parts)
        return {
            "original": query,
            "corrected": corrected,
            "has_corrections": len(changes) > 0,
            "changes": changes,
        }

    # ── Fuzzy Matching API ────────────────────────────────────────────────────

    def fuzzy_match(self, query: str, candidates: Iterable[str],
                    threshold: float = 0.70) -> Optional[Tuple[str, float]]:
        """
        Finds the closest candidate from a list using Damerau-Levenshtein similarity.
        Returns (best_candidate, similarity_score) or None if below threshold.
        """
        if not query or not candidates:
            return None

        q = query.strip().lower()
        best_cand: Optional[str] = None
        best_score = -1.0

        for cand in candidates:
            c = str(cand).strip().lower()
            score = similarity_ratio(q, c)
            if score > best_score:
                best_score = score
                best_cand = cand

        if best_score >= threshold and best_cand is not None:
            return (best_cand, round(best_score, 3))
        return None

    # ── Utilities ─────────────────────────────────────────────────────────────

    @staticmethod
    def _match_case(original: str, target: str) -> str:
        """Transfers capitalization pattern from original to target word."""
        if original.isupper():
            return target.upper()
        if original.istitle():
            return target.capitalize()
        return target.lower()


# =============================================================================
# 6. GLOBAL SINGLETON INSTANCE & CONVENIENCE FUNCTIONS
# =============================================================================
# Global engine instance used across coordinator, agents, and API routers
spell_corrector = SpellCorrector()

def correct_word(word: str) -> str:
    """Convenience function: correct a single word."""
    return spell_corrector.correct_word(word)

def correct_query(query: str) -> str:
    """Convenience function: correct full query text."""
    return spell_corrector.correct_query(query)

def correct_query_detailed(query: str) -> Dict[str, Any]:
    """Convenience function: correct full query text with audit details."""
    return spell_corrector.correct_query_detailed(query)

def fuzzy_match(query: str, candidates: Iterable[str], threshold: float = 0.70) -> Optional[Tuple[str, float]]:
    """Convenience function: fuzzy match query against candidate list."""
    return spell_corrector.fuzzy_match(query, candidates, threshold)
