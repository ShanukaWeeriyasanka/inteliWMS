"""
Warehouse Digital Twin navigator for the Inventory Agent.

Turns a "where is / how do I get to / how many / what's low" question into a
UiCommand (database/twin/ui_command.schema.json) for the twin map:

  1. resolve_product() and resolve_location() decide what the question is about.
  2. The top candidate is used only when it is clearly the best one;
     otherwise the user is asked to choose (action = clarify).
  3. Directions come from get_directions() — never written by the agent.
  4. Every number in the answer comes from a database view.
  5. The command is stored in ui_commands so the browser session can play it.

Returns None when the twin database is unavailable or nothing matched, so the
Inventory Agent falls back to its classic SKU lookup.
"""
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from agents.inventory_agent.config import inventory_config
from agents.inventory_agent.schemas import UiCommand
from database.twin import repository as twin_repo
from database.twin.connection import TwinUnavailable, is_enabled
from utils.logger import StructuredLogger

logger = StructuredLogger(__name__)

_NAVIGATE = re.compile(r"\b(how (do|can|should) (i|we) (get|go|reach)|how to (get|go|reach)|directions?|take me|"
                       r"route|navigate|guide me|walk me|way to)\b", re.I)
_ALERTS = re.compile(r"\b(running (low|out)|low stock|low on|out of stock|alerts?|over capacity|low)\b", re.I)
_HEATMAP = re.compile(r"\b(heat ?map|busiest|fullest|how full|full|fill level|occupancy|capacity)\b", re.I)
_FILL_METRIC = re.compile(r"\b(full|fullest|fill|occupancy|capacity)\b", re.I)
_COUNT = re.compile(r"\b(how many|how much|count|total units?)\b", re.I)
_CLEAR = re.compile(r"^\s*(clear|reset|close)( the)?( map| view| twin)?\W*$", re.I)
_STAIRS = re.compile(r"\b(stairs?|staircase|stairway)\b", re.I)
_FASTEST = re.compile(r"\b(fastest|quickest|hurry|asap|quickly)\b", re.I)
_FROM = re.compile(r"\bfrom\s+(.+?)(?=\s+(?:to|into|towards?)\s+|\s+(?:by|via|using)\s+|[?.!]|$)", re.I)
_TO = re.compile(r"\b(?:to|towards?)\s+(.+)$", re.I)

_RACK_TYPE_NOUN = {
    "shelf_unit": "shelf units",
    "pallet_grid": "pallet racks",
    "crate_rack": "crate racks",
    "cabinet": "cold cabinets",
}


@dataclass
class TwinAnswer:
    command: Dict[str, Any]
    chat_text: str
    command_id: Optional[str] = None


@dataclass
class _Candidate:
    kind: str                     # 'product' | 'location'
    id: str
    score: float
    name: str                     # short name: "Rack 2", "Power Adapter 65W"
    label: str                    # chip label: "Rack 2 · Floor 1"
    match_type: str
    level: Optional[str] = None
    floor_id: Optional[str] = None
    floor_name: Optional[str] = None


@dataclass
class _Pick:
    mode: str                     # 'one' | 'clarify' | 'multi'
    items: List[_Candidate]

    @property
    def top(self) -> _Candidate:
        return self.items[0]


# ── Resolution ───────────────────────────────────────────────────────────────

def _product_candidates(text: str) -> List[_Candidate]:
    return [
        _Candidate("product", r["product_id"], float(r["score"]), r["name"],
                   f"{r['name']} ({r['product_id']})", r["match_type"])
        for r in twin_repo.resolve_product(text)
    ]


def _location_candidates(text: str) -> List[_Candidate]:
    out = []
    for r in twin_repo.resolve_location(text):
        short = r["label"].split(",")[0].strip() if r["level"] != "floor" else r["label"]
        if r["level"] in ("shelf", "bin"):
            short = ", ".join(p.strip() for p in r["label"].split(",")[:-1])
        out.append(_Candidate("location", r["location_id"], float(r["score"]), short,
                              f"{short} · {r['floor_name']}", r["match_type"], r["level"],
                              r["floor_id"], r["floor_name"]))
    return out


def _pick(cands: List[_Candidate]) -> Optional[_Pick]:
    """Agent rule: use the top candidate only if it is alone, or >= 0.9 and >= 0.1 ahead."""
    if not cands:
        return None
    if all(c.kind == "location" and c.match_type == "rack_type" for c in cands):
        return _Pick("multi", cands)
    ranked = sorted(cands, key=lambda c: -c.score)
    if len(ranked) == 1:
        return _Pick("one", ranked)
    top, second = ranked[0], ranked[1]
    margin = round(top.score - second.score, 4)
    if top.score >= inventory_config.TWIN_PICK_MIN_SCORE and margin >= inventory_config.TWIN_PICK_MARGIN:
        return _Pick("one", ranked[:1])
    return _Pick("clarify", ranked[: inventory_config.TWIN_MAX_CANDIDATES])


def _resolve(text: str) -> Dict[str, Optional[_Pick]]:
    products = _product_candidates(text)
    locations = _location_candidates(text)
    best_p = max((c.score for c in products), default=0.0)
    best_l = max((c.score for c in locations), default=0.0)
    # The side that matched best is the target; the other side is context
    # ("the charger on floor 2"). On a tie the product wins.
    primary = "product" if products and best_p >= best_l else ("location" if locations else None)
    return {
        "primary": primary,
        "product": _pick(products),
        "location": _pick(locations),
    }


# ── Answer text helpers (numbers only from the database) ────────────────────

def _fmt_time(seconds: Optional[float]) -> str:
    s = float(seconds or 0)
    if s < 90:
        return f"about {round(s)} seconds"
    return f"about {round(s / 60, 1):g} minutes"


def _route_summary(directions: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not directions:
        return {"ok": False, "short": "", "lines": [], "total_s": None}
    if directions[0]["kind"] == "error":
        return {"ok": False, "short": directions[0]["instruction"], "lines": [directions[0]["instruction"]],
                "total_s": None}
    lines = [d["instruction"] for d in directions]
    moving = [d["instruction"] for d in directions if d["kind"] in ("walk", "floor_change", "note")]
    total_s = directions[-1].get("total_s")
    first = " ".join(moving[: inventory_config.TWIN_ANSWER_STEPS])
    return {"ok": True, "short": f"{first} {_fmt_time(total_s).capitalize()} on foot.".strip(),
            "lines": lines, "total_s": total_s}


def _chat_text(headline: str, route: Optional[Dict[str, Any]] = None) -> str:
    if not route or not route["lines"]:
        return headline
    numbered = "\n".join(f"{i}. {line}" for i, line in enumerate(route["lines"], 1))
    tail = f"\n\nTotal: {_fmt_time(route['total_s'])}." if route["ok"] else ""
    return f"{headline}\n\nDirections:\n{numbered}{tail}"


def _prefer(query: str) -> str:
    if _STAIRS.search(query):
        return "stairs"
    if _FASTEST.search(query):
        return "fastest"
    return inventory_config.TWIN_DEFAULT_PREFER


def _clarify(pick: _Pick) -> TwinAnswer:
    items = pick.items
    names = {c.name for c in items}
    if items[0].kind == "location" and len(names) == 1:
        floors = [c.floor_name for c in items]
        text = f"There's a {items[0].name} on {', '.join(floors[:-1])} and on {floors[-1]}. Which one?"
    else:
        text = "I found several matches: " + "; ".join(c.label for c in items) + ". Which one did you mean?"
    candidates = []
    for c in items:
        cand = {"label": c.label, "score": round(c.score, 3)}
        cand["product_id" if c.kind == "product" else "location_id"] = c.id
        candidates.append(cand)
    return TwinAnswer({"action": "clarify", "answer_text": text, "candidates": candidates}, text)


# ── Command builders ─────────────────────────────────────────────────────────

def _locate_product(product: _Candidate, context: Optional[_Pick], prefer: str) -> TwinAnswer:
    rows = twin_repo.get_product_locations([product.id])
    totals = next((t for t in twin_repo.get_product_totals() if t["product_id"] == product.id), None)
    cmd: Dict[str, Any] = {"action": "locate_product", "product_ids": [product.id]}
    if context and context.mode == "one" and context.top.floor_id:
        cmd["floor_id"] = context.top.floor_id

    if not rows:
        text = f"{product.name} ({product.id}) is out of stock — no bin holds it right now."
        cmd["answer_text"] = text
        return TwinAnswer(cmd, text)

    total = sum(r["quantity"] for r in rows)
    floors = {r["floor_id"] for r in rows}
    best = rows[0]
    unit = (totals or {}).get("unit") or "units"
    headline = (f"{product.name} ({product.id}) is in {len(rows)} bin{'s' if len(rows) != 1 else ''} across "
                f"{len(floors)} floor{'s' if len(floors) != 1 else ''} — {total} {unit} in total. "
                f"Most of it ({best['quantity']}) is on {best['floor_name']} · {best['rack_name']} · "
                f"shelf {best['level_index']}, bin {best['position_index']}.")
    if totals and totals["is_low_stock"]:
        headline += f" Stock is low: {totals['total_quantity']} left, reorder point {totals['reorder_point']}."

    route = _route_summary(twin_repo.get_route(product.id, None, prefer)["directions"])
    cmd["route"] = {"prefer": prefer}
    cmd["answer_text"] = f"{headline} {route['short']}".strip()
    return TwinAnswer(cmd, _chat_text(headline, route))


def _show_location(pick: _Pick, prefer: str) -> TwinAnswer:
    if pick.mode == "multi":
        racks = twin_repo.get_racks([c.id for c in pick.items])
        kind = _RACK_TYPE_NOUN.get(racks[0]["type"], "racks") if racks else "racks"
        floors = sorted({r["floor_name"] for r in racks})
        names = ", ".join(r["name"] for r in racks)
        text = f"There are {len(racks)} {kind} on {' and '.join(floors)}: {names}."
        cmd = {"action": "show_location", "location_ids": [r["id"] for r in racks],
               "floor_id": racks[0]["floor_id"], "answer_text": text}
        return TwinAnswer(cmd, text)

    loc = pick.top
    loc_row = twin_repo.get_locations([loc.id])[0]
    parts = [p.strip() for p in loc_row["label"].split(",")]
    where = ", ".join(parts[:-1]) if len(parts) > 1 else parts[0]
    if loc.level == "floor":
        headline = f"Showing {loc_row['floor_name']}."
    else:
        headline = f"{where} is on {loc_row['floor_name']}."
    if loc_row.get("rack_id"):
        fill = next((f for f in twin_repo.get_rack_fill(loc_row["floor_id"]) if f["rack_id"] == loc_row["rack_id"]), None)
        if fill and loc.level == "rack":
            headline += (f" It holds {fill['total_units']} units of {fill['distinct_products']} "
                         f"product{'s' if fill['distinct_products'] != 1 else ''}.")

    cmd: Dict[str, Any] = {"action": "show_location", "location_ids": [loc.id], "floor_id": loc_row["floor_id"]}
    if loc.level == "floor":
        cmd["answer_text"] = headline
        return TwinAnswer(cmd, headline)
    route = _route_summary(twin_repo.get_route(loc.id, None, prefer)["directions"])
    cmd["route"] = {"to_id": loc.id, "prefer": prefer}
    cmd["answer_text"] = f"{headline} {route['short']}".strip()
    return TwinAnswer(cmd, _chat_text(headline, route))


def _navigate(query: str, prefer: str) -> Optional[TwinAnswer]:
    from_id = None
    from_name = "the main entrance"
    m_from = _FROM.search(query)
    rest = query
    if m_from:
        res_from = _resolve(m_from.group(1))
        side = res_from["primary"]
        pick = res_from[side] if side else None
        if pick and pick.mode == "clarify":
            return _clarify(pick)
        if pick and pick.mode == "one":
            from_id, from_name = pick.top.id, pick.top.label
        rest = (query[: m_from.start()] + query[m_from.end():]).strip()

    m_to = _TO.search(rest)
    target_text = m_to.group(1) if m_to else rest
    res = _resolve(target_text)
    side = res["primary"]
    pick = res[side] if side else None
    if pick is None:
        return None
    if pick.mode == "clarify":
        return _clarify(pick)
    target = pick.top  # 'multi' (e.g. "the freezers"): go to the first one listed
    route = _route_summary(twin_repo.get_route(target.id, from_id, prefer)["directions"])
    dest = target.label if target.kind == "location" else target.name
    headline = f"Directions from {from_name} to {dest}."
    cmd: Dict[str, Any] = {"action": "navigate", "route": {"to_id": target.id, "prefer": prefer}}
    if from_id:
        cmd["route"]["from_id"] = from_id
    if target.kind == "product":
        cmd["product_ids"] = [target.id]
    elif target.floor_id:
        cmd["location_ids"] = [target.id]
        cmd["floor_id"] = target.floor_id
    cmd["answer_text"] = f"{headline} {route['short']}".strip()
    return TwinAnswer(cmd, _chat_text(headline, route))


def _count(res: Dict[str, Optional[_Pick]]) -> Optional[TwinAnswer]:
    loc_pick, prod_pick = res["location"], res["product"]
    if loc_pick and loc_pick.mode == "clarify":
        return _clarify(loc_pick)
    if prod_pick and prod_pick.mode == "clarify" and res["primary"] == "product":
        return _clarify(prod_pick)

    if loc_pick and loc_pick.mode == "one":
        loc = loc_pick.top
        scope = {"level": loc.level, "id": loc.id}
        where = f"{loc.name} on {loc.floor_name}" if loc.level != "floor" else loc.floor_name
        floor_id = loc.floor_id
    else:
        scope = {"level": "warehouse", "id": "WH1"}
        where = "the warehouse"
        floor_id = None
    prefix = None if scope["level"] == "warehouse" else scope["id"]

    cmd: Dict[str, Any] = {"action": "count", "scope": scope}
    if floor_id:
        cmd["floor_id"] = floor_id
    if prod_pick and prod_pick.mode == "one":
        product = prod_pick.top
        rows = twin_repo.get_product_locations([product.id], prefix)
        qty = sum(r["quantity"] for r in rows)
        text = f"There {'is' if qty == 1 else 'are'} {qty} × {product.name} in {where}."
        cmd.update(product_ids=[product.id], metric="product_quantity", answer_text=text)
        return TwinAnswer(cmd, text)

    rows = twin_repo.get_product_locations(None, prefix)
    units, products = sum(r["quantity"] for r in rows), len({r["product_id"] for r in rows})
    text =f"{where[0].upper() + where[1:]} holds {units} units across {products} product{'s' if products != 1 else ''}."
    cmd.update(metric="total_units", answer_text=text)
    return TwinAnswer(cmd, text)


def _heatmap(query: str, res: Dict[str, Optional[_Pick]]) -> TwinAnswer:
    loc_pick = res["location"]
    floor_id = loc_pick.top.floor_id if loc_pick and loc_pick.mode == "one" else None
    floor_id = floor_id or twin_repo.floor_with_most_units()
    metric = "fill_ratio" if _FILL_METRIC.search(query) else "total_units"
    fills = twin_repo.get_rack_fill(floor_id)
    floor_name = next((f["name"] for f in twin_repo.get_layout()["floors"] if f["id"] == floor_id), floor_id)
    key = (lambda f: f["fill_ratio"] or 0) if metric == "fill_ratio" else (lambda f: f["total_units"])
    top = max(fills, key=key) if fills else None
    if top is None:
        text = f"Showing the heatmap for {floor_name}."
    elif metric == "fill_ratio":
        text = f"Rack fill on {floor_name}: the fullest is {top['rack_name']} at {round((top['fill_ratio'] or 0) * 100)}%."
    else:
        text = f"Units per rack on {floor_name}: the busiest is {top['rack_name']} with {top['total_units']} units."
    return TwinAnswer({"action": "heatmap", "floor_id": floor_id, "metric": metric, "answer_text": text}, text)


def _alerts(query: str) -> TwinAnswer:
    q = query.lower()
    if "capacity" in q:
        types = ["bin_over_capacity"]
    elif "out of stock" in q and "low" not in q:
        types = ["out_of_stock"]
    else:
        types = ["low_stock", "out_of_stock"]
    alerts = [a for a in twin_repo.get_open_alerts() if a["type"] in types]
    low = [a for a in alerts if a["type"] == "low_stock"]
    out = [a for a in alerts if a["type"] == "out_of_stock"]
    over = [a for a in alerts if a["type"] == "bin_over_capacity"]
    parts = []
    if low:
        parts.append(f"{len(low)} product{'s are' if len(low) != 1 else ' is'} running low")
    if out:
        parts.append(f"{len(out)} {'are' if len(out) != 1 else 'is'} out of stock")
    if over:
        parts.append(f"{len(over)} bin{'s are' if len(over) != 1 else ' is'} over capacity")
    text = (" and ".join(parts) + ".") if parts else "No open stock alerts right now."
    text = text[0].upper() + text[1:]
    lines = "\n".join(f"• {a['message']}" for a in alerts)
    return TwinAnswer({"action": "show_alerts", "alert_types": types, "answer_text": text},
                      f"{text}\n\n{lines}" if lines else text)


# ── Entry point ──────────────────────────────────────────────────────────────

def build_twin_answer(query: str) -> Optional[TwinAnswer]:
    """Build (but do not store) the twin command for a question. None = not a twin question."""
    if not inventory_config.TWIN_ENABLED or not is_enabled():
        return None
    try:
        if _CLEAR.match(query):
            answer = TwinAnswer({"action": "clear", "answer_text": "Map cleared."}, "Map cleared.")
        elif _NAVIGATE.search(query):
            answer = _navigate(query, _prefer(query))
        elif _ALERTS.search(query):
            answer = _alerts(query)
        else:
            res = _resolve(query)
            if _HEATMAP.search(query) and not (res["product"] and res["primary"] == "product"):
                answer = _heatmap(query, res)
            elif _COUNT.search(query):
                answer = _count(res)
            else:
                side = res["primary"]
                pick = res[side] if side else None
                if pick is None:
                    answer = None
                elif pick.mode == "clarify":
                    answer = _clarify(pick)
                elif side == "product":
                    answer = _locate_product(pick.top, res["location"], _prefer(query))
                else:
                    answer = _show_location(pick, _prefer(query))
        if answer is None:
            return None
        payload = UiCommand(version=inventory_config.TWIN_COMMAND_VERSION, **answer.command).to_payload()
        return TwinAnswer(payload, answer.chat_text)
    except TwinUnavailable as exc:
        logger.log_event("TWIN_UNAVAILABLE", {"error": str(exc)})
        return None
    except Exception as exc:
        logger.log_event("TWIN_NAVIGATOR_ERROR", {"query": query[:80], "error": str(exc)})
        return None


def answer_with_twin(query: str, session_id: Optional[str] = None) -> Optional[TwinAnswer]:
    """Build the twin command and store it in ui_commands for the browser session."""
    answer = build_twin_answer(query)
    if answer is None or not session_id:
        return answer
    try:
        row = twin_repo.insert_ui_command(session_id, query, answer.command)
        answer.command_id = row["id"]
    except Exception as exc:
        logger.log_event("TWIN_COMMAND_STORE_FAILED", {"session_id": session_id, "error": str(exc)})
    return answer
