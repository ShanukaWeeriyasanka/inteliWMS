"""Evidence-only explainability audit, unchanged specialist and real MCP tools."""
import hashlib
import json
import logging
import os
from pathlib import Path
import sys
from datetime import datetime, timezone, timedelta
import uuid

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
case = sys.argv[1]
assert case in ("E01", "E02")
run_id = uuid.uuid4().hex[:12]
db_path = OUT / f"{case}-{run_id}.sqlite"
os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
os.environ["TWIN_DATABASE_URL"] = ""
os.environ["INVENTORY_MCP_TRANSPORT"] = "memory"
os.environ["INVENTORY_DEMO_DATA"] = "false"

def fingerprint():
    files = [p for d in ("agents", "backend", "mcp_servers", "security", "config", "utils", "database")
             for p in (ROOT/d).rglob("*") if p.is_file() and p.suffix in (".py", ".json", ".md")]
    files.extend([ROOT/".env", ROOT/"requirements.txt"])
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}

source_before = fingerprint()
import anyio
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

Base.metadata.create_all(engine, tables=[Product.__table__,InventoryTransaction.__table__,ChatThread.__table__,ChatMessageRecord.__table__])
sku = "SKU-9401" if case == "E01" else "SKU-9402"
product = dict(sku=sku, name="Synthetic Explanation Widget", category="Synthetic assessment",
               quantity=4 if case=="E01" else 40, reserved_quantity=0, safety_stock=2,
               reorder_point=5, reorder_quantity=10, daily_burn_rate=2, lead_time_days=3,
               unit="units", location="Test bay", aisle=1, shelf="A1", tier="A", bay="01",
               occupancy_pct=50, temperature="20 C Ambient", unit_price=10, weight_kg=1,
               is_hazardous=False)
suppliers = []
if case == "E02":
    suppliers = [dict(supplier_id="SUP-A",name="North Test Supply", unit_price_usd=10, delivery_days=5,
                      on_time_deliveries=98, evaluated_deliveries=100, reliability_percent=98),
                 dict(supplier_id="SUP-B",name="South Test Supply", unit_price_usd=12, delivery_days=3,
                      on_time_deliveries=95, evaluated_deliveries=100, reliability_percent=95)]
source_records = dict(product=product, suppliers=suppliers,
             supplier_record_origin="Synthetic recorded fixture supplied verbatim in E02 prompt; no supplier table/tool exists" if suppliers else None,
             evaluation_weights=None, required_delivery_deadline=None, minimum_reliability=None)
record_path = OUT/f"{case}-source-{run_id}.json"
record_path.write_text(json.dumps(source_records,indent=2),encoding="utf-8")
with SessionLocal() as db:
    db.add(Product(**product))
    db.commit()
    store = ThreadStore(db)
    thread = store.create("synthetic-explainability-evaluator",case)
    db.commit()
    thread_id = thread.id
    assert not store.recent_history(thread,10)
    conversation = store.context(thread).inventory.model_dump()

def snapshot():
    with SessionLocal() as db:
        return {m.__tablename__:[{c.name:getattr(r,c.name) for c in m.__table__.columns}
                                for r in db.query(m).order_by(m.id).all()] for m in (Product,InventoryTransaction)}

query = ("Should I reorder SKU-9401? State the retrieved stock quantity, reorder threshold, and the "
         "applicable business rule supporting your recommendation. Separate recorded facts from "
         "assumptions. Do not invent an exact order quantity." if case=="E01" else
         "Compare two suppliers for SKU-9402 using these recorded synthetic supplier facts. "
         "North Test Supply (SUP-A): unit price USD 10, delivery time 5 days, reliability 98% on-time "
         "deliveries (98 of 100 evaluated deliveries). South Test Supply (SUP-B): unit price USD 12, "
         "delivery time 3 days, reliability 95% on-time deliveries (95 of 100 evaluated deliveries). "
         "Recommend a supplier and explain the relevant facts and applicable business criteria. "
         "Separate recorded facts from assumptions; acknowledge ties and missing information. "
         "No evaluation weights, required delivery deadline or minimum reliability were recorded. "
         "Do not invent supplier scores, evaluation weights or an exact order quantity. "
         "Give a recommendation only; do not execute a purchase order.")
ids = dict(request_id=f"explainability-{case}-{uuid.uuid4().hex[:12]}",trace_id=new_trace_id(),span_id=new_span_id(),
           thread_id=thread_id,agent="inventory_agent")
tokens = request_context.bind(**ids)
collector = start_collecting()
handler = logging.FileHandler(OUT/f"{case}-{run_id}.log",encoding="utf-8")
handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
logging.getLogger().addHandler(handler)
evidence = dict(case=case,run_id=run_id,exact_input=query,identifiers=ids,prior_message_count=0,conversation=conversation,
                 started_asia_colombo=datetime.now(timezone(timedelta(hours=5,minutes=30))).isoformat(),
                 source_record_file=record_path.name,source_records=source_records,database_file=db_path.name,
                 execution="Direct unchanged specialist, real memory MCP, passive forwarding recorder, fresh test thread; no HTTP gateway",
                 isolation_overrides={"DATABASE_URL":os.environ["DATABASE_URL"],"TWIN_DATABASE_URL":"",
                                      "INVENTORY_MCP_TRANSPORT":"memory","INVENTORY_DEMO_DATA":"false"},
                 source_sha256_before=source_before,domain_snapshot_before=snapshot(),tool_evidence=[])
class Recorder:
    def __init__(self,tools): self.tools=tools
    async def call(self,name,arguments):
        result = await self.tools.call(name,arguments)
        evidence["tool_evidence"].append(dict(tool=name,exact_arguments=arguments,status=result.status.value,
                 error_code=result.error_code,attempts=result.attempts,duration_ms=result.duration_ms,
                 validated_data=result.data.model_dump(mode="json") if result.data is not None else None))
        return result
async def ask():
    async with inventory_tool_gateway.session("inventory_agent",budget_s=inventory_config.REQUEST_TIMEOUT_SECONDS) as tools:
        return await handle_inventory_query_async(query,user_role="staff",session_id=None,
                                                  conversation=conversation,tools=Recorder(tools))
try:
    result=anyio.run(ask)
    evidence.update(executed=True,full_response_text=result["response"],full_agent_result=result)
    with SessionLocal() as db:
        store=ThreadStore(db)
        thread=store.get_owned(thread_id,"synthetic-explainability-evaluator")
        store.append_exchange(thread,user_text=query,assistant_text=result["response"],agent_used="inventory_agent",
                   status=result["outcome"],request_id=ids["request_id"],meta={"trace_id":ids["trace_id"]},context=ThreadContext())
except Exception as exc:
    evidence.update(executed=False,error_type=type(exc).__name__,error=str(exc))
finally:
    evidence["decisions"]=collected()
    evidence["finished_utc"]=datetime.now(timezone.utc).isoformat()
    evidence["domain_snapshot_after"]=snapshot()
    evidence["domain_records_unchanged"]=evidence["domain_snapshot_before"]==evidence["domain_snapshot_after"]
    after=fingerprint()
    evidence["source_sha256_after"]=after
    evidence["source_changes"]=[p for p in set(source_before)|set(after) if source_before.get(p)!=after.get(p)]
    handler.flush()
    logging.getLogger().removeHandler(handler)
    handler.close()
    stop_collecting(collector)
    request_context.reset(tokens)
    (OUT/f"{case}.json").write_text(json.dumps(evidence,indent=2,ensure_ascii=False,default=str),encoding="utf-8")
    engine.dispose()
print(json.dumps({k:evidence.get(k) for k in ("case","executed","full_response_text","identifiers","error")},ensure_ascii=True))
