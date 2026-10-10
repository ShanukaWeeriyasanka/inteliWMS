"""
FastAPI Microservice for the Knowledge Agent.
Exposes REST and MCP tool endpoints for product location, vector RAG retrieval, and entity extraction.
"""
from typing import Optional
from contextlib import asynccontextmanager

import uvicorn
import hmac

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from agents.knowledge_agent.agent import execute_knowledge_query
from agents.knowledge_agent.location_resolver import resolve_location
from agents.knowledge_agent.knowledge_store import knowledge_store, seed_warehouse_sops
from agents.knowledge_agent.ner import extract_warehouse_entities
from agents.knowledge_agent.config import knowledge_config
from agents.knowledge_agent.shift_handoff import (
    record_shift_handoff,
    get_latest_shift_handoff,
    list_recent_shift_handoffs
)
from agents.knowledge_agent.compliance import check_compliance, evaluate_compliance_query
from agents.knowledge_agent.returns_handler import triage_returned_item, evaluate_return_query
from agents.knowledge_agent.schemas import (
    KnowledgeQueryRequest,
    LocationLookupRequest,
    RAGQueryRequest,
    ExtractEntitiesRequest,
    IndexDocumentRequest,
    HealthResponse,
    ShiftHandoffCreate,
    ComplianceCheckRequest,
    ReturnTriageRequest
)
from security.sanitizer import sanitizer
from utils.logger import StructuredLogger


logger = StructuredLogger(__name__)


@asynccontextmanager
async def lifespan(application):
    """Seed default warehouse SOPs into vector storage on application boot."""
    try:
        seed_warehouse_sops(knowledge_store)
        logger.log_event("KNOWLEDGE_SERVER_STARTUP", {
            "status": "ready",
            "port": knowledge_config.PORT,
            "indexed_chunks": knowledge_store.count()
        })
    except Exception as e:
        logger.log_event("KNOWLEDGE_SERVER_STARTUP_WARN", {"error": str(e)})
    yield  # Application is running


# Initialize FastAPI App — version sourced from config (zero hardcoding)
app = FastAPI(
    title="IntelliWMS Knowledge Agent Service",
    description="Microservice for warehouse product locations, RAG SOP retrieval, and entity extraction",
    version=knowledge_config.SERVICE_VERSION,
    lifespan=lifespan
)

# CORS origins are env-configurable (set KNOWLEDGE_CORS_ORIGINS in .env for prod)
app.add_middleware(
    CORSMiddleware,
    allow_origins=knowledge_config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if not knowledge_config.SERVICE_API_KEY:
    logger.log_event("KNOWLEDGE_SERVICE_UNAUTHENTICATED",
                     {"warning": "KNOWLEDGE_SERVICE_API_KEY is not set; every endpoint is open"}, level="WARNING")


@app.middleware("http")
async def require_service_key(request: Request, call_next):
    """With KNOWLEDGE_SERVICE_API_KEY set, every endpoint but /health needs a matching X-API-Key header."""
    expected = knowledge_config.SERVICE_API_KEY
    if expected and request.method != "OPTIONS" and request.url.path != "/health":
        supplied = request.headers.get("x-api-key", "")
        if not hmac.compare_digest(supplied.encode(), expected.encode()):
            return JSONResponse(status_code=401, content={"detail": "Missing or invalid X-API-Key."})
    return await call_next(request)


def _reject_injected(*texts: Optional[str]) -> None:
    """
    Text stored here is later quoted back to users and re-enters LLM prompts through chat history
    (indirect prompt injection / RAG poisoning): refuse it when it carries instruction-like text.
    """
    for text in texts:
        if text and sanitizer.is_injection_attempt(text)[0]:
            rule = sanitizer.matched_rule(text)
            logger.log_event("KNOWLEDGE_WRITE_REJECTED", {"rule": rule}, level="WARNING")
            raise HTTPException(status_code=400, detail=f"Rejected: the text matched the security filter (rule: {rule}).")



@app.get("/health", response_model=HealthResponse)
def health_check():
    """Service health and telemetry endpoint."""
    return {
        "status": "healthy",
        "service": "knowledge_agent",
        "port": knowledge_config.PORT,
        "indexed_chunks": knowledge_store.count()
    }


@app.post("/query")
def process_agent_query(req: KnowledgeQueryRequest):
    """
    Main entry point for Coordinator Agent delegation.
    Resolves location or retrieves SOP policy with extracted entity breakdown.
    """
    _reject_injected(req.query)
    try:
        result = execute_knowledge_query(
            query=req.query,
            user_role=req.user_role,
            context=req.context
        )
        return {"status": "success", **result}
    except Exception as e:
        logger.log_event("KNOWLEDGE_QUERY_ERROR", {"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/lookup_location")
def tool_lookup_location(req: LocationLookupRequest):
    """Direct tool endpoint for physical location lookup."""
    res = resolve_location(req.query_or_sku)
    return {"status": "success", "result": res}


@app.post("/tools/query_knowledge")
def tool_query_knowledge(req: RAGQueryRequest):
    """Direct tool endpoint for ChromaDB RAG vector search with optional category filtering."""
    hits = knowledge_store.query(req.question, n_results=req.n_results, category=req.category)
    return {"status": "success", "hits": hits, "count": len(hits)}


@app.post("/tools/extract_entities")
def tool_extract_entities(req: ExtractEntitiesRequest):
    """Direct tool endpoint for NER entity extraction."""
    entities = extract_warehouse_entities(req.text)
    return {"status": "success", "entities": entities}


@app.post("/tools/index_document")
def tool_index_document(req: IndexDocumentRequest):
    """Direct tool endpoint to ingest and index new warehouse documents."""
    _reject_injected(req.title, req.content)
    try:
        knowledge_store.add_document(
            doc_id=req.doc_id,
            title=req.title,
            content=req.content,
            category=req.category
        )
        return {
            "status": "success",
            "message": f"Document '{req.title}' successfully indexed into vector store.",
            "total_indexed_chunks": knowledge_store.count()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to index document: {str(e)}")


@app.post("/tools/upload_sop_file")
async def tool_upload_sop_file(
    file: UploadFile = File(...),
    doc_id: str = Form(...),
    title: str = Form(...),
    category: str = Form("SOP")
):
    """Upload and ingest a markdown (.md) or text (.txt) SOP document directly into ChromaDB."""
    if not (file.filename.endswith(".txt") or file.filename.endswith(".md")):
        raise HTTPException(status_code=400, detail="Only .txt and .md SOP documents are supported.")

    try:
        content_bytes = await file.read()
        content = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="SOP files must be UTF-8 text.")
    _reject_injected(title, content)
    try:
        knowledge_store.add_document(
            doc_id=doc_id,
            title=title,
            content=content,
            category=category
        )
        return {
            "status": "success",
            "message": f"SOP document '{title}' successfully ingested from '{file.filename}'.",
            "doc_id": doc_id,
            "category": category,
            "total_indexed_chunks": knowledge_store.count()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")


@app.get("/tools/shift_handoff/latest")
def tool_get_latest_shift_handoff(shift_type: Optional[str] = None):
    """Retrieve the latest warehouse shift handoff summary."""
    res = get_latest_shift_handoff(shift_type)
    return {"status": "success", "result": res}


@app.post("/tools/shift_handoff/record")
def tool_record_shift_handoff(req: ShiftHandoffCreate):
    """Record a shift handover note."""
    _reject_injected(req.supervisor, req.summary, req.incidents, req.pending_tasks)
    res = record_shift_handoff(
        shift_type=req.shift_type,
        supervisor=req.supervisor,
        summary=req.summary,
        incidents=req.incidents,
        pending_tasks=req.pending_tasks
    )
    if not res.get("success"):
        raise HTTPException(status_code=500, detail=res.get("error", "Failed to record"))
    return {"status": "success", "result": res}


@app.get("/tools/shift_handoff/recent")
def tool_list_recent_shift_handoffs(limit: int = 5):
    """List recent shift handoff entries for audits."""
    entries = list_recent_shift_handoffs(limit=limit)
    return {"status": "success", "count": len(entries), "entries": entries}


@app.post("/tools/check_compliance")
def tool_check_compliance(req: ComplianceCheckRequest):
    """Direct tool endpoint to evaluate warehouse safety and regulatory compliance."""
    res = check_compliance(
        category=req.category,
        zone=req.zone,
        value=req.value,
        pallet_condition=req.pallet_condition,
        has_ppe=req.has_ppe if req.has_ppe is not None else True
    )
    return {"status": "success", "result": res}


@app.post("/tools/triage_return")
def tool_triage_return(req: ReturnTriageRequest):
    """Direct tool endpoint to evaluate and route returned inventory per SOP-RET-004."""
    res = triage_returned_item(
        rma_number=req.rma_number,
        sku=req.sku,
        condition=req.condition,
        package_sealed=req.package_sealed,
        has_accessories=req.has_accessories
    )
    return {"status": "success", "result": res}


@app.get("/campus/overview")
def get_campus_overview_endpoint():
    """Returns Colombo Logistics Complex master plan overview and all 7 facilities."""
    from agents.knowledge_agent.campus_data import CAMPUS_OVERVIEW, CAMPUS_BUILDINGS
    return {
        "status": "success",
        "overview": CAMPUS_OVERVIEW,
        "buildings": list(CAMPUS_BUILDINGS.values())
    }


@app.get("/campus/facilities")
def get_campus_facilities_endpoint():
    """Lists all 7 campus buildings with capacities, operational statuses, and assigned MHE."""
    from agents.knowledge_agent.campus_data import CAMPUS_BUILDINGS
    return {
        "status": "success",
        "count": len(CAMPUS_BUILDINGS),
        "facilities": list(CAMPUS_BUILDINGS.values())
    }


@app.get("/campus/facilities/{bld_id}")
def get_campus_facility_endpoint(bld_id: str):
    """Returns detailed specifications for a specific campus facility (e.g. BLD-01 to BLD-07)."""
    from agents.knowledge_agent.campus_data import CAMPUS_BUILDINGS
    key = bld_id.strip().upper()
    if key in CAMPUS_BUILDINGS:
        return {"status": "success", "facility": CAMPUS_BUILDINGS[key]}
    # Search by number
    for b in CAMPUS_BUILDINGS.values():
        if b.get("number") == bld_id or b.get("id").lower() == bld_id.lower():
            return {"status": "success", "facility": b}
    raise HTTPException(status_code=404, detail=f"Campus facility '{bld_id}' not found.")


@app.get("/campus/vehicles")
def get_campus_vehicles_endpoint():
    """Returns active fleet vehicles, coordinates, battery State of Charge, and duty status."""
    from agents.knowledge_agent.campus_data import CAMPUS_VEHICLES
    return {
        "status": "success",
        "count": len(CAMPUS_VEHICLES),
        "vehicles": list(CAMPUS_VEHICLES.values())
    }


@app.get("/campus/objects")
def get_campus_objects_endpoint():
    """Returns campus static infrastructure assets (60T scale, fast chargers, airlock, etc.)."""
    from agents.knowledge_agent.campus_data import CAMPUS_OBJECTS
    return {
        "status": "success",
        "count": len(CAMPUS_OBJECTS),
        "objects": list(CAMPUS_OBJECTS.values())
    }


if __name__ == "__main__":
    uvicorn.run(
        "agents.knowledge_agent.server:app",
        host=knowledge_config.HOST,
        port=knowledge_config.PORT,
        reload=True
    )
