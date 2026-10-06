"""
Inventory Specialist Agent for IntelliWMS (Member 1).

Complete Multi-Component Autonomous Specialist:
  1. Document Parser: Inbound supplier emails & PDFs (NER SKU, Qty, Date, PO).
  2. Reorder Predictor: Daily consumption burn rate & depletion forecasting.
  3. Anomaly Watcher: Stock movement shrinkage & variance detection.
  4. Transfer Advisor: Sibling warehouse surplus evaluation vs external vendor POs.
  5. Equipment Health: Informal complaint logs NLP for predictive maintenance.
  6. Real-time Warehouse Floor Locator: High-bay rack coordinates, tiers, & live layout.
  7. Stock levels, availability, low stock and stock movements.

All warehouse data comes from the inventory MCP server's tools
(mcp_servers/inventory_mcp_server.py), reached through the tool gateway
(mcp_servers/mcp_tool_client.py), which only lets this agent use its allowlisted
tools. Answers are built from successful tool results only: no default SKUs, no
made-up quantities. When the product is unclear the agent asks which one; when a
tool fails it says so instead of guessing.
"""
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from agents.inventory_agent import responder as R
from agents.inventory_agent import tool_contracts as C
from agents.inventory_agent.config import inventory_config
from agents.inventory_agent.intents import (
    TWIN_SUB_INTENTS,
    detect_sub_intent_with_rule,
    extract_entities,
    meaningful_terms,
    resolve_follow_up,
)
from agents.inventory_agent.schemas import InventoryQueryRequest, InventoryQueryResponse, StockItemInfo
from agents.inventory_agent.warehouse_map import get_full_warehouse_layout
from utils.async_bridge import run_sync
from utils.decisions import RULE, record_decision
from utils.logger import StructuredLogger
from utils.metrics import INVENTORY_REQUESTS
from utils.tracing import span

logger = StructuredLogger(__name__)

AGENT_NAME = "inventory_agent"
_MAX_SKUS_PER_ANSWER = 3
# Words that name a place in the warehouse, not a product (Digital Twin count scopes)
_PLACE_WORDS = {"rack", "crate", "cold", "freezer", "floor", "shelf", "bin", "zone", "aisle", "storage", "level",
                "bay", "room", "area", "section", "building", "site", "total", "everything", "altogether", "overall",
                "place", "map", "ground", "first", "second", "third", "top", "basement"}


class _ToolFailed(Exception):
    def __init__(self, result):
        super().__init__(result.status.value)
        self.result = result


@dataclass
class _Ref:
    """Which product(s) the question is about."""
    skus: List[str] = field(default_factory=list)
    product_ids: List[str] = field(default_factory=list)
    assumed: bool = False  # carried over from earlier in the conversation

    @property
    def any(self) -> bool:
        return bool(self.skus or self.product_ids)


class _Turn:
    """Everything needed to answer one question."""

    def __init__(self, request: InventoryQueryRequest, tools):
        self.request = request
        self.tools = tools
        self.query = request.query.strip()
        ctx = request.context or {}
        self.session_id: Optional[str] = ctx.get("session_id")
        self.conversation: Dict[str, Any] = ctx.get("conversation") or {}
        self.sub_intent, self.sub_intent_rule = detect_sub_intent_with_rule(self.query)
        self.entities = extract_entities(self.query)
        self.raw_sku_hint = (request.sku or "").strip() or None
        hint = C.canonical_sku(self.raw_sku_hint)
        self.sku_from_hint = bool(hint and hint not in self.entities.skus)
        if self.sku_from_hint:
            self.entities.skus.insert(0, hint)
        self.start = time.perf_counter()
        self.assumed_label: Optional[str] = None
        # How the product was identified (recorded as the inventory.product_ref decision)
        self.ref_source: str = "not_required"

    async def call(self, tool: str, **arguments: Any):
        """Tool call that must succeed (a failure ends the turn with an honest error)."""
        result = await self.tools.call(tool, arguments)
        if result.failed:
            raise _ToolFailed(result)
        return result

    def respond(self, text: str, *, source: str, items: Optional[List[StockItemInfo]] = None,
                outcome: str = "answered", skus: Optional[List[str]] = None,
                product_ids: Optional[List[str]] = None, pending: Optional[List[Dict[str, Any]]] = None,
                sub_intent: Optional[str] = None, needs_reorder: Optional[bool] = None,
                **attachments: Any) -> InventoryQueryResponse:
        items = list(items or [])
        if self.assumed_label and outcome == "answered":
            text = R.assumed_note(self.assumed_label) + text
        if needs_reorder is None:
            needs_reorder = any(i.status in ("OUT_OF_STOCK", "LOW_STOCK") for i in items)
        return InventoryQueryResponse(
            agent=AGENT_NAME, query=self.query, sub_intent=sub_intent or self.sub_intent, response=text,
            source=source, items=items, needs_reorder=needs_reorder, outcome=outcome,
            context_update={"skus": skus or [], "product_ids": product_ids or [],
                            "last_sub_intent": self.sub_intent, "pending_clarification": pending},
            clarification_candidates=pending or [],
            execution_time_ms=round((time.perf_counter() - self.start) * 1000, 2),
            **attachments,
        )

    def fail(self, result) -> InventoryQueryResponse:
        return InventoryQueryResponse(
            agent=AGENT_NAME, query=self.query, sub_intent=self.sub_intent, response=R.failure(result.status.value),
            source="error", items=[], needs_reorder=False, outcome="error", error_code=result.error_code,
            context_update=None, execution_time_ms=round((time.perf_counter() - self.start) * 1000, 2),
        )


class InventoryAgent:
    """
    Inventory Specialist Agent (Member 1).
    Full suite: Document Parser, Reorder Predictor, Anomaly Watcher,
    Transfer Advisor, Equipment Health and stock lookups — all via MCP tools.
    """

    async def handle_query_async(self, request: InventoryQueryRequest, tools=None) -> InventoryQueryResponse:
        if tools is not None:
            return await self._handle(request, tools)
        from mcp_servers.mcp_tool_client import inventory_tool_gateway
        async with inventory_tool_gateway.session(
                AGENT_NAME, budget_s=inventory_config.REQUEST_TIMEOUT_SECONDS) as session_tools:
            return await self._handle(request, session_tools)

    def handle_query(self, request: InventoryQueryRequest, db=None) -> InventoryQueryResponse:
        """Synchronous facade. `db` is accepted for compatibility but unused: the MCP tools
        open their own database sessions."""
        return run_sync(lambda: self.handle_query_async(request))

    async def _handle(self, request: InventoryQueryRequest, tools) -> InventoryQueryResponse:
        turn = _Turn(request, tools)
        record_decision("inventory.sub_intent", turn.sub_intent, RULE, turn.sub_intent_rule)
        with span("inventory.handle", agent=AGENT_NAME, sub_intent=turn.sub_intent) as sp:
            try:
                resp = await self._answer(turn)
            except _ToolFailed as failed:
                resp = turn.fail(failed.result)
            sp.set(status="error" if resp.outcome == "error" else "ok", outcome=resp.outcome,
                   error_code=resp.error_code, product_ref=turn.ref_source)
        record_decision("inventory.product_ref", turn.ref_source, RULE, f"product_ref.{turn.ref_source}")
        INVENTORY_REQUESTS.inc(outcome=resp.outcome, sub_intent=resp.sub_intent)
        logger.log_event("INVENTORY_RESPONSE", {
            "sub_intent": resp.sub_intent, "outcome": resp.outcome, "source": resp.source,
            "items": len(resp.items), "error_code": resp.error_code, "duration_ms": resp.execution_time_ms,
            "follow_up": bool(turn.assumed_label), "sub_intent_rule": turn.sub_intent_rule,
            "product_ref": turn.ref_source,
        }, level="WARNING" if resp.outcome == "error" else "INFO")
        return resp

    # ── Routing inside the agent ────────────────────────────────────────────

    async def _answer(self, turn: _Turn) -> InventoryQueryResponse:
        sub = turn.sub_intent

        if sub == "document_parser":
            return await self._document(turn)
        if sub == "equipment_health":
            r = await turn.call(C.ANALYZE_EQUIPMENT_LOG, text=turn.query[:5000])
            return turn.respond(R.equipment(r.data.report), source="equipment_health",
                                equipment_health_result=r.data.report)

        if turn.raw_sku_hint and not C.canonical_sku(turn.raw_sku_hint) and not turn.entities.any:
            # The caller named a SKU we can't look up (e.g. a malformed code) — never substitute another
            turn.ref_source = "invalid_sku_hint"
            return turn.respond(R.not_found(turn.raw_sku_hint), source="database", outcome="not_found")

        ref = self._explicit_or_follow_up(turn)

        # Warehouse Digital Twin first for map questions (legacy SKU-xxxx lookups skip it)
        if sub in TWIN_SUB_INTENTS and not ref.skus and not turn.raw_sku_hint:
            twin = await self._twin(turn, ref)
            if twin is not None:
                return twin

        if sub == "anomaly_watcher":
            return await self._anomalies(turn, ref)

        if sub == "reorder_check" and not ref.any:
            found = await self._search(turn) if meaningful_terms(turn.query) else None
            if isinstance(found, InventoryQueryResponse):
                return found
            if found is None:
                r = await turn.call(C.LIST_LOW_STOCK, limit=50)
                return turn.respond(R.low_stock_list(r.data.items, r.data.total_checked), source="database",
                                    items=r.data.items, sub_intent="reorder_check",
                                    outcome="answered" if r.data.items else "empty",
                                    skus=[i.sku for i in r.data.items][:5])
            ref = found

        if not ref.any:
            found = await self._search(turn)
            if isinstance(found, InventoryQueryResponse):
                return found
            if found is not None:
                ref = found
            else:
                fu = resolve_follow_up(turn.query, turn.conversation, allow_short=True)
                if not fu.any:
                    turn.ref_source = "none"
                    return turn.respond(R.needs_product(sub), source="database", outcome="needs_product")
                ref = _Ref(skus=fu.skus, product_ids=fu.product_ids, assumed=True)
                turn.assumed_label = (fu.skus or fu.product_ids)[0]
                turn.ref_source = "short_follow_up"

        if sub == "stock_movements":
            return await self._movements(turn, ref)
        if not ref.skus:
            # Only a Digital Twin product id, and the twin did not answer above
            pid = ref.product_ids[0]
            return turn.respond(R.not_found(pid), source="digital_twin", outcome="not_found", product_ids=[pid])
        if sub == "transfer_advisor":
            return await self._transfer(turn, ref.skus[0])
        if sub == "reorder_predictor":
            return await self._forecast(turn, ref.skus[0])
        return await self._stock(turn, ref.skus[:_MAX_SKUS_PER_ANSWER])

    # ── Product reference ───────────────────────────────────────────────────

    def _explicit_or_follow_up(self, turn: _Turn) -> _Ref:
        if turn.entities.skus:
            turn.ref_source = "sku_hint" if turn.sku_from_hint and len(turn.entities.skus) == 1 else "explicit_id"
            return _Ref(skus=list(turn.entities.skus))
        if turn.entities.product_ids:
            turn.ref_source = "explicit_id"
            return _Ref(product_ids=list(turn.entities.product_ids))
        fu = resolve_follow_up(turn.query, turn.conversation)
        # A pick from the offered choices, or a pure pointer back ("where is it?") with no new product named
        if fu.picked_from_clarification or (fu.assumed and not meaningful_terms(turn.query)):
            if fu.assumed:
                turn.assumed_label = (fu.skus or fu.product_ids)[0]
            turn.ref_source = "clarification_pick" if fu.picked_from_clarification else "pointer_follow_up"
            return _Ref(skus=fu.skus, product_ids=fu.product_ids, assumed=fu.assumed)
        return _Ref()

    async def _search(self, turn: _Turn):
        """Name search → _Ref (one clear match), a clarification response (several), or None."""
        if not meaningful_terms(turn.query):
            return None
        r = await turn.call(C.SEARCH_PRODUCTS, text=turn.query[:300], limit=5)
        if r.status.value == "ok":
            turn.ref_source = "name_search"
            return _Ref(skus=[r.data.items[0].sku])
        if r.status.value == "ambiguous":
            turn.ref_source = "ambiguous"
            pending = [{"label": f"{c.name} ({c.sku})", "sku": c.sku} for c in r.data.candidates]
            return turn.respond(R.clarification(r.data.candidates), source="database",
                                outcome="clarification_needed", items=r.data.items, pending=pending,
                                needs_reorder=False)
        return None

    # ── Answers ─────────────────────────────────────────────────────────────

    async def _stock(self, turn: _Turn, skus: List[str]) -> InventoryQueryResponse:
        items: List[StockItemInfo] = []
        parts: List[str] = []
        missing: List[str] = []
        for sku in skus:
            r = await turn.call(C.GET_PRODUCT_STOCK, sku=sku)
            if r.status.value == "not_found":
                missing.append(sku)
                continue
            item = r.data.item
            items.append(item)
            card = (R.availability_answer(item, r.data.thresholds_defaulted) if turn.sub_intent == "availability"
                    else R.stock_card(item, r.data.thresholds_defaulted))
            parts.append(card)
        parts += [R.not_found(s) for s in missing]
        outcome = "answered" if items else "not_found"
        return turn.respond("\n\n".join(parts), source="database", items=items, outcome=outcome,
                            skus=[i.sku for i in items] or missing)

    async def _movements(self, turn: _Turn, ref: _Ref) -> InventoryQueryResponse:
        args = {"sku": ref.skus[0]} if ref.skus else {"product_id": ref.product_ids[0]}
        r = await turn.call(C.GET_STOCK_MOVEMENTS, limit=20, **args)
        data = r.data
        if data.status == "not_found":
            return turn.respond(R.not_found(data.subject_id or next(iter(args.values()))), source=data.source,
                                outcome="not_found")
        if data.status == "disabled":
            return turn.respond(R.not_found(args.get("product_id", "")), source="digital_twin", outcome="not_found")
        ids = {"skus": [data.subject_id]} if ref.skus else {"product_ids": [data.subject_id]}
        return turn.respond(R.movements(data), source=data.source,
                            outcome="answered" if data.movements else "empty", **ids)

    async def _forecast(self, turn: _Turn, sku: str) -> InventoryQueryResponse:
        r = await turn.call(C.PREDICT_DEPLETION, sku=sku)
        if r.data.status == "not_found":
            return turn.respond(R.not_found(sku), source="reorder_predictor", outcome="not_found", skus=[sku])
        stock = await turn.call(C.GET_PRODUCT_STOCK, sku=sku)
        items = [stock.data.item] if stock.data.item else []
        pred = r.data.prediction
        return turn.respond(R.depletion(r.data), source="reorder_predictor", items=items, skus=[sku],
                            prediction_result=pred, needs_reorder=pred.urgency in ("CRITICAL", "HIGH"))

    async def _transfer(self, turn: _Turn, sku: str) -> InventoryQueryResponse:
        r = await turn.call(C.EVALUATE_TRANSFER, sku=sku)
        if r.data.status == "not_found":
            return turn.respond(R.not_found(sku), source="transfer_advisor", outcome="not_found", skus=[sku])
        stock = await turn.call(C.GET_PRODUCT_STOCK, sku=sku)
        items = [stock.data.item] if stock.data.item else []
        return turn.respond(R.transfer(r.data), source="transfer_advisor", items=items, skus=[sku],
                            transfer_result=r.data.recommendation, needs_reorder=False)

    async def _anomalies(self, turn: _Turn, ref: _Ref) -> InventoryQueryResponse:
        sku = ref.skus[0] if ref.skus else None
        if sku is None and meaningful_terms(turn.query):
            found = await self._search(turn)
            if isinstance(found, InventoryQueryResponse):
                return found
            sku = found.skus[0] if found is not None else None
        r = await turn.call(C.CHECK_STOCK_ANOMALIES, **({"sku": sku} if sku else {}))
        data = r.data
        if data.status == "not_found":
            return turn.respond(R.not_found(sku), source="anomaly_watcher", outcome="not_found")
        alert = data.alerts[0] if data.alerts else None
        items: List[StockItemInfo] = []
        if alert:
            stock = await turn.tools.call(C.GET_PRODUCT_STOCK, {"sku": alert.sku})
            if not stock.failed and stock.data.item:
                items = [stock.data.item]
        return turn.respond(R.anomaly(data), source="anomaly_watcher", items=items,
                            outcome="answered" if alert else "empty", skus=[alert.sku] if alert else [],
                            anomaly_result=alert,
                            needs_reorder=bool(alert and alert.severity in ("HIGH", "CRITICAL")))

    async def _document(self, turn: _Turn) -> InventoryQueryResponse:
        r = await turn.call(C.PARSE_SUPPLIER_DOCUMENT, text=turn.query[:5000])
        doc = r.data.result
        items: List[StockItemInfo] = []
        sku = C.canonical_sku(doc.extracted_sku)
        if sku:
            stock = await turn.tools.call(C.GET_PRODUCT_STOCK, {"sku": sku})
            if not stock.failed and stock.data.item:
                items = [stock.data.item]
        return turn.respond(doc.raw_summary, source="document_parser", items=items, skus=[sku] if sku else [],
                            document_result=doc, needs_reorder=False)

    @staticmethod
    def _names_a_product(query: str) -> bool:
        """Does the question name something other than a place ("rack 2", "cold storage", "floor 3")?"""
        return any(t not in _PLACE_WORDS and not t.isdigit() for t in meaningful_terms(query))

    async def _twin(self, turn: _Turn, ref: _Ref) -> Optional[InventoryQueryResponse]:
        """Answer on the Digital Twin map; None lets the classic lookup try."""
        query = turn.query
        if ref.product_ids and ref.product_ids[0] not in query.upper():
            query = f"{query} {ref.product_ids[0]}"  # follow-up: name the product the user pointed back to
        r = await turn.tools.call(C.TWIN_ANSWER, {"query": query[:2000]})
        if r.failed:
            logger.log_event("TWIN_LOOKUP_FAILED", {"status": r.status.value, "error_code": r.error_code},
                             level="WARNING")
            record_decision("inventory.twin", "failed", RULE, "twin.failed", tool_status=r.status.value)
            return None
        if r.status.value != "ok":
            record_decision("inventory.twin", r.status.value, RULE, f"twin.{r.status.value}")
            return None
        command, text = r.data.command, r.data.chat_text or ""
        action = command.get("action", "")
        if action == "count" and not command.get("product_ids") and self._names_a_product(turn.query):
            # The twin didn't recognise the product and counted a whole place instead
            # ("how many barcode scanners?" → "the warehouse holds 580 units"): not an answer.
            record_decision("inventory.twin", "rejected_product_not_resolved", RULE, "twin.rejected_place_total")
            return None
        record_decision("inventory.twin", "accepted", RULE, "twin.accepted", action=action)
        command_id = None
        if turn.session_id:
            pub = await turn.tools.call(C.PUBLISH_MAP_COMMAND, {
                "session_id": turn.session_id, "query_text": turn.query[:2000], "command": command})
            if pub.failed:
                # The answer still stands; the map just won't replay it over SSE for this session
                logger.log_event("TWIN_COMMAND_STORE_FAILED", {"status": pub.status.value,
                                                               "error_code": pub.error_code}, level="WARNING")
            else:
                command_id = pub.data.command_id
        pending = None
        outcome = "answered"
        if action == "clarify":
            outcome = "clarification_needed"
            pending = [{"label": c.get("label", ""), "product_id": c["product_id"]}
                       for c in command.get("candidates", []) if c.get("product_id")] or None
        product_ids = command.get("product_ids") or ref.product_ids
        return turn.respond(text, source="digital_twin", sub_intent=f"twin_{action}", outcome=outcome,
                            product_ids=product_ids, pending=pending, needs_reorder=action == "show_alerts",
                            ui_command=command, ui_command_id=command_id)


inventory_agent = InventoryAgent()


def _to_dict(resp: InventoryQueryResponse) -> Dict[str, Any]:
    return {
        "agent": resp.agent,
        "query": resp.query,
        "sub_intent": resp.sub_intent,
        "response": resp.response,
        "source": resp.source,
        "items": [i.model_dump() for i in resp.items],
        "needs_reorder": resp.needs_reorder,
        "document_result": resp.document_result.model_dump() if resp.document_result else None,
        "prediction_result": resp.prediction_result.model_dump() if resp.prediction_result else None,
        "anomaly_result": resp.anomaly_result.model_dump() if resp.anomaly_result else None,
        "transfer_result": resp.transfer_result.model_dump() if resp.transfer_result else None,
        "equipment_health_result": resp.equipment_health_result.model_dump() if resp.equipment_health_result else None,
        "warehouse_layout": None,
        "ui_command": resp.ui_command,
        "ui_command_id": resp.ui_command_id,
        "outcome": resp.outcome,
        "error_code": resp.error_code,
        "context_update": resp.context_update,
        "clarification": resp.clarification_candidates or None,
        "execution_time_ms": resp.execution_time_ms,
    }


def _request(query: str, sku: Optional[str], user_role: str, session_id: Optional[str],
             conversation: Optional[Dict[str, Any]]) -> InventoryQueryRequest:
    return InventoryQueryRequest(query=query, sku=sku, user_role=user_role,
                                 context={"session_id": session_id, "conversation": conversation or {}})


async def handle_inventory_query_async(
    query: str, *, sku: Optional[str] = None, user_role: str = "staff", session_id: Optional[str] = None,
    conversation: Optional[Dict[str, Any]] = None, tools=None,
) -> Dict[str, Any]:
    """Async entry point used by the coordinator's dispatcher."""
    resp = await inventory_agent.handle_query_async(_request(query, sku, user_role, session_id, conversation), tools)
    return _to_dict(resp)


def handle_inventory_query(
    query: str, sku: Optional[str] = None, user_role: str = "staff", db=None,
    session_id: Optional[str] = None, conversation: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Synchronous entry point (scripts, tests, the legacy coordinator client). `db` is unused."""
    req = _request(query, sku, user_role, session_id, conversation)
    out = _to_dict(run_sync(lambda: inventory_agent.handle_query_async(req)))
    out["warehouse_layout"] = get_full_warehouse_layout()
    return out
