"""Isolated disclosure assessment with scoped MCP client test mocks.

No application files, prompts or business rules are changed. Each invocation
uses a fresh SQLite database/process/thread, never a running service.
"""
import hashlib
import json
import logging
import os
from pathlib import Path
import sys
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
import uuid

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
case = sys.argv[1]
assert case in ("TR01", "TR02")
run_id = uuid.uuid4().hex[:12]
db_path = OUT / f"{case}-{run_id}.sqlite"
os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
os.environ["TWIN_DATABASE_URL"] = ""
os.environ["INVENTORY_MCP_TRANSPORT"] = "memory"
os.environ["INVENTORY_DEMO_DATA"] = "false"

def fingerprint():
    files = [p for d in ("agents", "backend", "mcp_servers", "security", "config", "utils", "database")
             for p in (ROOT / d).rglob("*") if p.is_file() and p.suffix in (".py", ".json", ".md")]
    files.extend([ROOT / ".env", ROOT / "requirements.txt"])
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}

source_before = fingerprint()
import anyio
from mcp.types import TextContent
from database.connection import Base, engine, SessionLocal
from database.models import Product, InventoryTransaction, ChatThread, ChatMessageRecord
from backend.threads.store import ThreadStore
from backend.threads.schemas import ThreadContext
from agents.inventory_agent.agent import handle_inventory_query_async
from agents.inventory_agent.config import inventory_config
from mcp_servers.mcp_tool_client import inventory_tool_gateway
from utils import request_context
from utils.decisions import start_collecting, collected, stop_collecting
from utils.tracing import new_trace_id, new_span_id

Base.metadata.create_all(engine, tables=[Product.__table__, InventoryTransaction.__table__,
                                       ChatThread.__table__, ChatMessageRecord.__table__])
test_now = datetime.now(timezone.utc).replace(microsecond=0)
record_time = test_now - timedelta(days=7) if case == "TR02" else test_now
sku = "SKU-9301" if case == "TR01" else "SKU-9302"
product_fields = dict(sku=sku, name="Synthetic Transparency Widget", category="Synthetic assessment",
                      quantity=37, reserved_quantity=5, safety_stock=10, reorder_point=20,
                      reorder_quantity=100, daily_burn_rate=3, lead_time_days=2,
                      unit="units", location="Test bay", aisle=1, shelf="A1", tier="A", bay="01",
                      occupancy_pct=50, temperature="20 C Ambient", unit_price=10, weight_kg=1,
                      is_hazardous=False, created_at=record_time-timedelta(days=1), updated_at=record_time)
with SessionLocal() as db:
    db.add(Product(**product_fields))
    db.commit()
    store = ThreadStore(db)
    thread = store.create("synthetic-transparency-evaluator", case)
    db.commit()
    thread_id = thread.id
    assert not store.recent_history(thread, 10)
    conversation = store.context(thread).inventory.model_dump()

def snapshot():
    with SessionLocal() as db:
        return {model.__tablename__: [{col.name:getattr(r, col.name) for col in model.__table__.columns}
                                     for r in db.query(model).order_by(model.id).all()]
                for model in (Product, InventoryTransaction)}

domain_before = snapshot()
query = (f"What is the current stock quantity for {sku}?" if case == "TR01" else
         f"How much stock of {sku} is available right now?")
ids = dict(request_id=f"transparency-{case}-{uuid.uuid4().hex[:12]}", trace_id=new_trace_id(),
           span_id=new_span_id(), thread_id=thread_id, agent="inventory_agent")
tokens = request_context.bind(**ids)
collector = start_collecting()
handler = logging.FileHandler(OUT / f"{case}-{run_id}.log", encoding="utf-8")
handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
logging.getLogger().addHandler(handler)
evidence = dict(case=case, run_id=run_id, exact_input=query, identifiers=ids,
                test_time_utc=test_now.isoformat(), test_time_asia_colombo=test_now.astimezone(timezone(timedelta(hours=5, minutes=30))).isoformat(),
                database_file=db_path.name, prior_message_count=0, conversation=conversation,
                entry_point="agents.inventory_agent.agent.handle_inventory_query_async",
                execution="Direct unchanged specialist, fresh persisted test thread, real memory MCP with scoped client mock; no HTTP gateway",
                isolation_overrides={"DATABASE_URL":os.environ["DATABASE_URL"], "TWIN_DATABASE_URL":"",
                                     "INVENTORY_MCP_TRANSPORT":"memory", "INVENTORY_DEMO_DATA":"false"},
                tool_evidence=[], injected_transport_events=[], domain_snapshot_before=domain_before,
                source_sha256_before=source_before)

class Recorder:
    def __init__(self, tools):
        self.tools = tools
    async def call(self, name, arguments):
        result = await self.tools.call(name, arguments)
        evidence["tool_evidence"].append(dict(tool=name, exact_arguments=arguments,
                    status=result.status.value, error_code=result.error_code, attempts=result.attempts,
                    duration_ms=result.duration_ms,
                    validated_data=result.data.model_dump(mode="json") if result.data is not None else None))
        return result

async def ask():
    async with inventory_tool_gateway.session("inventory_agent", budget_s=inventory_config.REQUEST_TIMEOUT_SECONDS) as tools:
        original_call = tools.client.call_tool
        async def injected_call(name, arguments=None, *args, **kwargs):
            assert name == "get_product_stock", "Fixture must affect only the requested stock lookup"
            event = dict(tool=name, exact_arguments=arguments, at_utc=datetime.now(timezone.utc).isoformat())
            if case == "TR01":
                event.update(injection="TimeoutError at MCP ClientSession.call_tool boundary",
                             error_type="TimeoutError", error="Synthetic inventory MCP timeout (isolated test)")
                evidence["injected_transport_events"].append(event)
                logging.getLogger("audit.transparency").warning(json.dumps({"event_type":"TEST_MCP_TIMEOUT_INJECTED", **request_context.current(), **event}))
                raise TimeoutError(event["error"])
            raw = await original_call(name, arguments, *args, **kwargs)
            event["original_server_result"] = raw.model_dump(mode="json")
            payload = json.loads(json.dumps(raw.structuredContent))
            assert payload["item"]["quantity_on_hand"] == 37 and payload["item"]["available_quantity"] == 32
            # SQLite stores the UTC fixture timestamp without timezone metadata.
            with SessionLocal() as db:
                stored = db.query(Product).filter(Product.sku == sku).one().updated_at
            dated = stored.replace(tzinfo=timezone.utc).isoformat()
            assert dated == record_time.isoformat()
            payload["item"]["updated_at"] = dated
            payload["record_updated_at"] = dated
            result = raw.model_copy(deep=True, update={"structuredContent":payload,
                    "content":[TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))]})
            event.update(injection="Dated MCP record: append actual synthetic DB updated_at to raw structured/text payload",
                         record_age_seconds=(test_now-record_time).total_seconds(),
                         returned_mock_mcp_result=result.model_dump(mode="json"))
            evidence["injected_transport_events"].append(event)
            logging.getLogger("audit.transparency").info(json.dumps({"event_type":"TEST_DATED_RECORD_RETURNED", **request_context.current(),
                 "tool":name,"record_updated_at":dated,"quantity_on_hand":37,"reserved_quantity":5,"available_quantity":32}))
            return result
        # Scoped patch is applied after normal tool discovery and restored on exit.
        with patch.object(tools.client, "call_tool", side_effect=injected_call) as mocked:
            try:
                return await handle_inventory_query_async(query, user_role="staff", session_id=None,
                                                          conversation=conversation, tools=Recorder(tools))
            finally:
                evidence["mock_call_count"] = mocked.call_count
                evidence["mcp_settings"] = inventory_tool_gateway.describe()

try:
    response = anyio.run(ask)
    evidence.update(executed=True, full_response_text=response["response"], full_agent_result=response)
    with SessionLocal() as db:
        store = ThreadStore(db)
        thread = store.get_owned(thread_id, "synthetic-transparency-evaluator")
        store.append_exchange(thread, user_text=query, assistant_text=response["response"],
                 agent_used="inventory_agent", status=response["outcome"], request_id=ids["request_id"],
                 meta={"trace_id":ids["trace_id"]}, context=ThreadContext())
except Exception as exc:
    evidence.update(executed=False, error_type=type(exc).__name__, error=str(exc))
finally:
    evidence["decisions"] = collected()
    evidence["finished_utc"] = datetime.now(timezone.utc).isoformat()
    evidence["domain_snapshot_after"] = snapshot()
    evidence["domain_records_unchanged"] = domain_before == evidence["domain_snapshot_after"]
    after = fingerprint()
    evidence["source_sha256_after"] = after
    evidence["source_changes"] = [p for p in set(source_before)|set(after) if source_before.get(p)!=after.get(p)]
    handler.flush()
    logging.getLogger().removeHandler(handler)
    handler.close()
    stop_collecting(collector)
    request_context.reset(tokens)
    (OUT / f"{case}.json").write_text(json.dumps(evidence, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    engine.dispose()
print(json.dumps({k:evidence.get(k) for k in ("case","executed","full_response_text","identifiers","mock_call_count","error_type","error")}, ensure_ascii=True))
