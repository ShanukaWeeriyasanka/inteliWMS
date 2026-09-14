# IntelliWMS Agent Development Ruleset & Best Practices Guide

**Applies To:** All IntelliWMS Specialist Agents (`knowledge_agent`, `inventory_agent`, `fulfillment_agent`, `coordinator`)  
**Target Audience:** All backend and agent engineers working on IntelliWMS  
**Status:** Mandatory Active Standard

---

## 1. Core Architecture Principles

Every specialist agent in IntelliWMS must be designed as a **self-contained, highly modular, and decoupled subsystem**. An agent should encapsulate its own feature logic, schemas, tools, API exposure, and domain data fixtures without bleeding implementation details into other components.

### 1.1 The Golden Rules
1. **Self-Contained Domain Directory:** All code, schemas, tools, and fixtures required by an agent MUST reside within `agents/<agent_name>/`.
2. **Zero Hardcoded Values:** Never hardcode LLM model names, ports, directory paths, credentials, magic thresholds, or long policy texts in code files.
3. **Feature Separation (Single Responsibility):** Separate query routing, vector search, database lookup, entity extraction, data contracts, and server endpoints into dedicated feature modules.
4. **Resilient Fallbacks:** Every external dependency (LLM API, ChromaDB vector store, spaCy NLP model, database connection) must have a reliable, non-crashing fallback path.
5. **Contract-Driven Communication:** All inputs and outputs across APIs and MCP tools must be defined using Pydantic schemas.

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
| `config.py` | Declares all environment variable lookups, model names, timeouts, and fallback defaults. | Do not read raw `os.getenv` repeatedly across different feature files. |
| `schemas.py` | Contains all Pydantic request/response models and data transfer objects (DTOs). | Do not use untyped `dict` payloads across agent boundaries without a schema. |
| `agent.py` | CrewAI agent instantiation, query triage, and fast-path execution routing. | Do not put low-level database queries or vector indexing logic in `agent.py`. |
| `tools.py` | CrewAI tool declarations using `@tool(...)` calling feature modules. | Do not implement business logic directly inside tool wrapper functions. |
| `server.py` | FastAPI app providing HTTP / MCP-compatible REST endpoints. | Do not write server code in a separate root folder without an agent-local service module. |
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
- All search limits (`limit=5`), similarity counts (`n_results=2`), chunk sizes, and timeouts must be defined as named constants in `config.py`.

---

## 4. Feature Decomposition & Separation of Concerns

### 4.1 Knowledge Agent Reference Structure
The Knowledge Agent separates warehouse information retrieval into distinct components:
1. **Ontology & Vocabulary (`ontology.py`):** Loads product synonyms, location indicators, unit indicators, and stop words from `data/warehouse_ontology.json`.
2. **Entity Recognition (`ner.py`):** Parses SKUs, physical coordinates (Aisles/Shelves/Bins), quantities, dates, and query intents.
3. **Location Resolver (`location_resolver.py`):** Queries relational database (`Product` model) for physical storage coordinates.
4. **Vector Knowledge Store (`knowledge_store.py`):** Manages ChromaDB persistence, document chunking, and similarity ranking with automatic in-memory fallback.
5. **Seed SOP Data (`data/sops.json`):** Holds initial Standard Operating Procedures for safety, stacking, forklift traffic, and returns.

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

## 7. MCP Servers & API Exposure

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

### Mandatory Test Scenarios:
1. **Direct SKU lookup:** Valid SKU, nonexistent SKU, case-insensitive SKU matching.
2. **Natural language lookup:** Synonym handling, stopword stripping, ambiguous product matches.
3. **RAG retrieval:** Safety protocols, policy retrieval, returns/SOP queries.
4. **NER extraction:** Proper entity parsing for SKUs, quantities, dates, and locations.
5. **API & Endpoints:** Test `/health`, `/query`, and tool routes using FastAPI `TestClient`.
6. **Integration with Coordinator:** Ensure routing from `CoordinatorMCPClient` succeeds without regression.

---

## 9. Teammate Checklist Before Submitting a PR

- [ ] All code for the agent is inside `agents/<agent_name>/`.
- [ ] No hardcoded model names, ports, file paths, or seed texts exist in python code.
- [ ] Pydantic models in `schemas.py` cover all API payloads and internal DTOs.
- [ ] Centralized prompts are imported from `config/prompts.py` (or agent `prompts.py`).
- [ ] Fallbacks are tested (e.g., ChromaDB unavailability, missing API key, DB missing item).
- [ ] All unit and integration tests pass via `pytest`.
- [ ] Structured logging is present at query receipt, resolution, and error stages.
