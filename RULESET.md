# IntelliWMS Agent Development Ruleset & Best Practices Guide

**Applies To:** All IntelliWMS Specialist Agents (`knowledge_agent`, `inventory_agent`, `fulfillment_agent`, `coordinator`)  
**Target Audience:** All backend and agent engineers working on IntelliWMS  
**Status:** Mandatory Active Standard

---

## 1. Core Architecture Principles

Every specialist agent in IntelliWMS must be designed as a **self-contained, highly modular, and decoupled subsystem**. An agent should encapsulate its own feature logic, schemas, tools, API exposure, and domain data fixtures without bleeding implementation details into other components.

### 1.1 The Golden Rules
1. **Self-Contained Domain Directory:** All code, schemas, tools, and fixtures required by an agent MUST reside within `agents/<agent_name>/`.
2. **Zero Hardcoded Values:** Never hardcode LLM model names, ports, directory paths, credentials, magic thresholds, compliance rule values, or long policy texts in code files.
3. **Feature Separation (Single Responsibility):** Separate query routing, vector search, database lookup, entity extraction, data contracts, and server endpoints into dedicated feature modules.
4. **Resilient Fallbacks:** Every external dependency (LLM API, ChromaDB vector store, spaCy NLP model, database connection) must have a reliable, non-crashing fallback path.
5. **Contract-Driven Communication:** All inputs and outputs across APIs and MCP tools must be defined using Pydantic schemas.
6. **Single Import Block Per File:** Each file must have one consolidated import block at the top. Never split imports into multiple blocks or repeat the same import twice in one file.

---

## 2. Agent Directory & File Layout

Each agent under `agents/<agent_name>/` must adhere to the following file layout:

```
agents/<agent_name>/
├── __init__.py               # Exports public agent functions, singletons, and schemas
├── config.py                 # Agent-specific settings, defaults, and env overrides
├── schemas.py                # Pydantic models for queries, responses, entities, and tool payloads
├── agent.py                  # Orchestrator, CrewAI agent setup, and fast-path execution engine
├── tools.py                  # CrewAI tool definitions wrapped with @tool decorators
├── server.py                 # FastAPI microservice exposing agent endpoints and tool routes
├── <feature_1>.py            # Feature implementation 1 (e.g., location_resolver.py, stock_checker.py)
├── <feature_2>.py            # Feature implementation 2 (e.g., knowledge_store.py, order_tracker.py)
└── data/                     # Seed fixtures, JSON ontologies, and markdown/json documents
    └── <seed_files>.json
```

### 2.1 File Responsibilities

| File | Purpose | Anti-Pattern to Avoid |
| :--- | :--- | :--- |
| `config.py` | Declares all environment variable lookups, model names, timeouts, fallback defaults, AND domain-specific rule constants (e.g., compliance limits). | Do not read raw `os.getenv` repeatedly across different feature files. Do not hardcode rule thresholds in feature modules. |
| `schemas.py` | Contains all Pydantic request/response models and data transfer objects (DTOs). | Do not use untyped `dict` payloads across agent boundaries without a schema. |
| `agent.py` | CrewAI agent instantiation, query triage, and fast-path execution routing. | Do not put low-level database queries or vector indexing logic in `agent.py`. Do not have duplicate import blocks. |
| `tools.py` | CrewAI tool declarations using `@tool(...)` calling feature modules. | Do not implement business logic directly inside tool wrapper functions. |
| `server.py` | FastAPI app providing HTTP / MCP-compatible REST endpoints. | Do not write server code in a separate root folder without an agent-local service module. Use `lifespan=` instead of deprecated `@app.on_event`. |
| `data/` | External JSON/YAML/Markdown seed files (e.g., SOP documents, ontology). | Never write large text documents or seed catalogs directly as Python string literals. |

---

## 3. Zero-Hardcoding Standards

### 3.1 LLM Models & Providers
- Model identifiers must never be written as literal strings in `agent.py`.
- **Bad:** `llm = "gemini/gemini-2.5-flash"`
- **Good:**
  ```python
  from agents.knowledge_agent.config import knowledge_config
  llm = knowledge_config.MODEL_NAME
  ```

### 3.2 File Paths
- Never use fragile relative path navigation like `Path(__file__).parent.parent.parent / "data"`.
- Use the centralized application paths defined in `config/settings.py` or agent `config.py`:
  ```python
  from agents.knowledge_agent.config import knowledge_config
  persist_dir = knowledge_config.CHROMA_PERSIST_DIR
  ```

### 3.3 Ports & Service URLs
- Define default service ports in `config/settings.py` with environment variable overrides:
  - Coordinator API: `PORT=8000`
  - Inventory Agent: `INVENTORY_SERVER_PORT=8001`
  - Knowledge Agent: `KNOWLEDGE_SERVER_PORT=8002`
  - Fulfillment Agent: `FULFILLMENT_SERVER_PORT=8003`

### 3.4 Prompts & Persona Guidelines
- Centralize all agent personas, goals, backstories, and system prompts in `config/prompts.py` (or agent-local `prompts.py`).
- Allows prompt tuning without modifying business logic or test suites.

### 3.5 Magic Numbers & Thresholds
- All search limits (`limit=5`), similarity counts (`n_results=2`), chunk sizes, timeouts, and **domain rule constants** (e.g., stacking tier limits, speed limits) must be defined as named constants in `config.py` with `os.getenv(...)` overrides.
  ```python
  COMPLIANCE_DEFAULT_TIERS: float = float(os.getenv("COMPLIANCE_DEFAULT_TIERS", "4"))
  ```

### 3.6 Service Metadata
- API version strings must never be hardcoded in `FastAPI(version="...")`.
- **Bad:** `app = FastAPI(version="1.1.0")`
- **Good:**
  ```python
  app = FastAPI(version=knowledge_config.SERVICE_VERSION)
  ```

### 3.7 CORS Origins
- Never hardcode `allow_origins=["*"]` in production code.
- Source CORS from config:
  ```python
  app.add_middleware(CORSMiddleware, allow_origins=knowledge_config.CORS_ORIGINS, ...)
  ```

---

## 4. Feature Decomposition & Separation of Concerns

### 4.1 Knowledge Agent Reference Structure
The Knowledge Agent separates warehouse information retrieval into distinct components:
1. **Ontology & Vocabulary (`ontology.py`):** Loads product synonyms, location indicators, unit indicators, and stop words from `data/warehouse_ontology.json`.
2. **Entity Recognition (`ner.py`):** Parses SKUs, physical coordinates (Aisles/Shelves/Bins), quantities, dates, and query intents.
3. **Location Resolver (`location_resolver.py`):** Queries relational database (`Product` model) for physical storage coordinates.
4. **Vector Knowledge Store (`knowledge_store.py`):** Manages ChromaDB persistence, document chunking, and similarity ranking with automatic in-memory fallback.
5. **Compliance Checker (`compliance.py`):** Evaluates pallet stacking, forklift speed, and PPE against SOP rules (constants from config).
6. **Returns Handler (`returns_handler.py`):** Triages inbound customer returns and assigns grade/destination per SOP-RET-004.
7. **Shift Handoff (`shift_handoff.py`):** Records and retrieves warehouse shift transition logs from the database.
8. **Seed SOP Data (`data/sops.json`):** Holds initial Standard Operating Procedures for safety, stacking, forklift traffic, and returns.

---

## 5. Type Safety & Schema Specifications

Always define Pydantic models with clear Field descriptions:

```python
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class KnowledgeQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Warehouse question or SKU search")
    user_role: str = Field("staff", description="Querying user's RBAC role ('staff', 'manager', 'admin')")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Session and coordinator context")

class KnowledgeQueryResponse(BaseModel):
    agent: str = Field("knowledge_agent")
    query: str
    response: str
    source: str = Field(..., description="'database_location' | 'vector_rag' | 'general_knowledge'")
    entities: Dict[str, Any] = Field(default_factory=dict)
    data: Optional[Dict[str, Any]] = None
    rag_sources: Optional[List[Dict[str, Any]]] = None
```

---

## 6. Logging & Observability

- Use `StructuredLogger` from `utils.logger` for all operations.
- Avoid raw `print()` statements in agent code.
- Always include structured metadata in log events:
  ```python
  logger.log_event("KNOWLEDGE_LOCATION_SEARCH", {
      "query": clean_query,
      "detected_sku": detected_sku,
      "found": True
  })
  ```

---

## 6. Logging & Observability

- Use `StructuredLogger` from `utils.logger` for all operations.
- Avoid raw `print()` statements in agent code.
- Use **timezone-aware UTC timestamps** — always `datetime.now(timezone.utc)`, never `datetime.utcnow()` (deprecated in Python 3.12+).
- Always include structured metadata in log events:
  ```python
  logger.log_event("KNOWLEDGE_LOCATION_SEARCH", {
      "query": clean_query,
      "detected_sku": detected_sku,
      "found": True
  })
  ```

---

## 7. FastAPI Server Standards

### 7.1 Startup via Lifespan (not deprecated `on_event`)
- **Bad:**
  ```python
  @app.on_event("startup")
  def on_startup():
      seed_warehouse_sops(knowledge_store)
  ```
- **Good:**
  ```python
  from contextlib import asynccontextmanager
  
  @asynccontextmanager
  async def lifespan(application):
      seed_warehouse_sops(knowledge_store)
      logger.log_event("KNOWLEDGE_SERVER_STARTUP", {...})
      yield
  
  app = FastAPI(lifespan=lifespan, ...)
  ```

### 7.2 MCP Servers & API Exposure

To support both standalone microservice deployment and Coordinator MCP client calls:
1. **Agent-Local Microservice (`agents/<agent>/server.py`):** Implements the FastAPI app, endpoints (`/health`, `/query`, `/tools/...`), and CORS configuration.
2. **Global MCP Gateway (`mcp_servers/<agent>_server.py`):** A lightweight facade that imports and serves the agent-local FastAPI app:
   ```python
   from agents.knowledge_agent.server import app
   import uvicorn
   from agents.knowledge_agent.config import knowledge_config

   if __name__ == "__main__":
       uvicorn.run(app, host=knowledge_config.HOST, port=knowledge_config.PORT)
   ```

---

## 8. Testing Standards

Every agent must have a dedicated test file under `tests/`:
- `tests/test_knowledge_agent.py`
- `tests/test_inventory_agent.py`
- `tests/test_fulfillment_agent.py`

### 8.1 Shared `conftest.py`
All shared pytest fixtures (database init, SOP seeding, TestClient creation) belong in `tests/conftest.py`:
- Use **session-scoped** fixtures for expensive one-time setup (DB init, ChromaDB seeding).
- Use **function-scoped** fixtures for per-test isolation of mutable state.
- Never duplicate fixture definitions across test files.

### Mandatory Test Scenarios:
1. **Direct SKU lookup:** Valid SKU, nonexistent SKU, case-insensitive SKU matching.
2. **Natural language lookup:** Synonym handling, stopword stripping, ambiguous product matches.
3. **RAG retrieval:** Safety protocols, policy retrieval, returns/SOP queries with category filter.
4. **NER extraction:** Proper entity parsing for SKUs, quantities, dates, and locations.
5. **Fast-path routing:** Shift handoff, compliance, returns triage, SOP, and location fast-paths each tested individually.
6. **API & Endpoints:** Test `/health`, `/query`, and tool routes using FastAPI `TestClient`.
7. **Integration with Coordinator:** Ensure routing from `CoordinatorMCPClient` succeeds without regression.
8. **Fallback paths:** ChromaDB unavailable → in-memory fallback, missing product → formatted not-found message.

---

## 9. Environment Variables

Every new configurable value MUST be:
1. Added to `agents/<agent>/config.py` as an `os.getenv(...)` with a safe default.
2. Documented in `.env.example` with a descriptive comment.
3. **Never** read directly via `os.getenv` in feature files — always via the agent's `config` singleton.

---

## 9. Teammate Checklist Before Submitting a PR

- [ ] All code for the agent is inside `agents/<agent_name>/`.
- [ ] No hardcoded model names, ports, file paths, rule thresholds, or seed texts in Python code.
- [ ] Rule constants (stacking limits, speed limits, etc.) are in `config.py` with env overrides.
- [ ] Pydantic models in `schemas.py` cover all API payloads and internal DTOs.
- [ ] Centralized prompts are imported from `config/prompts.py` (or agent `prompts.py`).
- [ ] Fallbacks are tested (e.g., ChromaDB unavailability, missing API key, DB missing item).
- [ ] All unit and integration tests pass via `pytest` with zero warnings.
- [ ] Structured logging is present at query receipt, resolution, and error stages.
- [ ] FastAPI server uses `lifespan=` instead of deprecated `@app.on_event`.
- [ ] Timestamps in logs use `datetime.now(timezone.utc)` (not `datetime.utcnow()`).
- [ ] No duplicate import blocks exist in any file.
- [ ] `.env.example` is updated with all new environment variables.
- [ ] `tests/conftest.py` contains session-scoped fixtures; test files only contain test functions.
