# IntelliWMS — Agentic AI Warehouse Management System

![Version](https://img.shields.io/badge/version-0.1.0-blue)
![Python](https://img.shields.io/badge/python-3.12.13-green)
![Node.js](https://img.shields.io/badge/node-22.22.0-green)
![Status](https://img.shields.io/badge/status-development-yellow)

---

## 📋 Table of Contents

1. [What is IntelliWMS?](#what-is-intelliwms)
2. [Problem Statement](#problem-statement)
3. [Solution Overview](#solution-overview)
4. [Architecture](#architecture)
5. [Tech Stack](#tech-stack)
6. [Project Structure](#project-structure)
7. [Team Ownership](#team-ownership)
8. [Quick Start](#quick-start)
9. [Development Workflow](#development-workflow)
10. [Running the System](#running-the-system)
11. [Git Workflow & Branching](#git-workflow--branching)
12. [Environment Setup](#environment-setup)
13. [Database Setup](#database-setup)
14. [Testing](#testing)
15. [Troubleshooting](#troubleshooting)
16. [Responsible AI](#responsible-ai)
17. [Commercialization](#commercialization)
18. [Timeline](#timeline)

---

## What is IntelliWMS?

**IntelliWMS** is a multi-agent Agentic AI system for warehouse management. It automates the manual, language-heavy work that warehouse staff currently do: searching for stock locations, processing supplier documents, predicting restock needs, explaining order delays, and bridging communication gaps between multilingual teams.

**Key differentiators:**
- **3 cooperating AI agents** that communicate directly with each other via MCP (Model Context Protocol)
- **Truly agentic behavior** — agents *decide* which tools to use via LLM reasoning, not hardcoded scripts
- **Multi-LLM support** — seamlessly swaps between Gemini (free), Groq (free), and Ollama (open-source, local)
- **Production-ready security** — JWT auth, RBAC, input sanitization, PII encryption
- **Responsible AI built-in** — structured logging, explainability, fairness checks from day one

---

## Problem Statement

**The Real Challenge in Warehouse Operations:**

Warehouse staff spend significant time on repetitive manual work that *could* be automated:
- **Searching** — "Where is SKU-4521?" requires digging through floor plan docs or asking a supervisor
- **Re-typing** — Supplier emails arrive as unstructured PDFs; staff manually re-type data into the inventory system
- **Cross-checking** — Explaining an order delay means querying three separate systems (orders DB, inventory DB, logistics system)
- **Translating** — Many warehouses run on multilingual teams; miscommunicated instructions cause errors and safety issues
- **Pattern-finding** — Detecting equipment issues or shrinkage requires manual analysis of logs

**Why standard WMS software doesn't solve this:**
Modern warehouse systems (SAP EWM, Manhattan Associates) handle *structured* data beautifully—orders, inventory, logistics. But they can't understand *unstructured* human input: informal emails, spoken notes, multilingual chatter, or informal complaints. That gap is where staff time evaporates.

---

## Solution Overview

**How IntelliWMS solves it:**

1. **User asks a question in plain English** — "Why is order #4521 delayed?" or "Where is SKU-9012?" or "Customer reports damage on this item—what now?"

2. **Coordinator Agent receives the query** — validates the user (JWT), checks permissions (RBAC), sanitizes for prompt injection, classifies intent (Inventory vs. Knowledge vs. Fulfillment)

3. **Right specialist agent handles it** — 
   - **Inventory Agent** parses supplier documents, predicts restocks, flags anomalies
   - **Knowledge Agent** answers questions using RAG (Retrieval-Augmented Generation) over warehouse SOPs and documents
   - **Fulfillment Agent** explains order issues by querying Inventory Agent directly, triages complaints

4. **Agents collaborate directly** — Fulfillment doesn't ask the Coordinator for stock data; it queries Inventory Agent directly via MCP. Fast, autonomous, genuinely "agentic."

5. **Response goes back to user** — structured, cited, auditable

**Concrete value:**
- **~3 minutes** (old way) → **~30 seconds** (IntelliWMS) to explain an order delay
- **Supplier email re-typing** → **automatic NLP extraction** of SKU/qty/date
- **Supervisor interruptions** → **instant location answers** via RAG
- **Training overhead** → **self-service SOP chatbot** for new hires

---

## Architecture

### High-Level Flow

```
┌──────────────────────┐
│   React Frontend     │ (User types questions)
└──────────┬───────────┘
           │ HTTP
           ▼
┌──────────────────────────────────────────────────────────┐
│        COORDINATOR AGENT (FastAPI + CrewAI)              │
│  ┌──────────────────────────────────────────────────┐   │
│  │ 1. Validate JWT (security/jwt_handler.py)        │   │
│  │ 2. Check RBAC permissions (security/rbac.py)     │   │
│  │ 3. Sanitize input (security/sanitizer.py)        │   │
│  │ 4. Classify intent via LLM (agents/coordinator/) │   │
│  │ 5. Route to specialist agent via MCP             │   │
│  └──────────────────────────────────────────────────┘   │
└──────────┬──────────────────────────────────────────────┘
           │
     ┌─────┼─────┐
     │     │     │  (MCP communication)
     ▼     ▼     ▼
   ┌──┐ ┌──┐ ┌──────┐
   │IN│ │KN│ │FULF │
   └──┘ └──┘ └──────┘
    │     │      │
    │     │      └─────────┐
    │     │                │
    │     └─ ChromaDB ──┐  │
    │        (RAG)      │  │
    │                   │  │
    └─ PostgreSQL ──────┘  │
       (structured data)   │
       (inventory, orders) │
                          │
                  ┌────────┘
                  │ Direct MCP query
                  │ (Fulfillment → Inventory)
                  ▼
```

### 3 Main Agents

| Agent | Owner | Responsibilities | Sub-agents |
|---|---|---|---|
| **Inventory Agent** | Member 1 | Stock tracking, reorder predictions, anomaly detection, inter-warehouse transfers, equipment health | Document Parser (NER) · Reorder Predictor · Anomaly Watcher · Transfer Advisor · **Equipment Health** ⭐ |
| **Knowledge Agent** | Member 2 | Location lookup (RAG), SOP retrieval, safety training, compliance checking, shift handoff notes | Location Finder · Returns Handler · Training Assistant · Compliance Checker · **Shift Handoff** ⭐ |
| **Fulfillment Agent** | Member 3 | Order-delay diagnosis, vendor performance summaries, complaint triage, multilingual communication | Order Diagnostics · Vendor Report Generator · Complaint Triage · **Communication Bridge** ⭐ |

**⭐ = Team differentiators** — unique, under-explored warehouse problems your system solves.

### Why Supervisor/Coordinator-Worker Pattern

- **CrewAI's sweet spot** — built for role-based hierarchical workflows
- **5.76x faster** than LangGraph on similar tasks (verified benchmarks, 2026)
- **Clear separation of concerns** — Coordinator routes; specialists solve
- **Genuinely agentic** — agents decide which tools to use, not scripted if/else
- **Scales** — add a 4th agent without rearchitecting

---

## Tech Stack

### Backend
| Layer | Technology | Version | Purpose |
|---|---|---|---|
| **Orchestration** | CrewAI | 1.14.6 | Multi-agent framework, role-based agents |
| **Web Framework** | FastAPI | 0.141.1 | REST API server |
| **Agent Communication** | MCP (Model Context Protocol) | built-in | Agents call each other directly |
| **LLM** | Gemini / Groq / Ollama | — | Natural language understanding & generation |
| **Vector Store (IR)** | ChromaDB | 1.5.9 | Retrieval-Augmented Generation (RAG) |
| **NLP** | spaCy | 3.8.4 | Named Entity Recognition (extract SKU/qty/date) |
| **Database** | PostgreSQL | 16.15 | Structured data (inventory, orders, users) |
| **ORM** | SQLAlchemy | 2.0.36 | Python-to-SQL mapping |
| **Auth** | JWT (python-jose) | 3.3.0 | Token-based authentication |
| **Testing** | pytest | 8.3.4 | Unit & integration tests |

### Frontend
| Technology | Version | Purpose |
|---|---|---|
| React | 19.2.8 | UI components, state management |
| Vite | 6.0.7 | Build tool, dev server |
| Axios | 1.7.9 | HTTP client for backend calls |

### DevOps
| Tool | Version | Purpose |
|---|---|---|
| Python | 3.12.13 | Runtime |
| Node.js | 22.22.0 LTS | Frontend runtime |
| Git | latest | Version control |
| PostgreSQL | 16.15 | Database server |
| Docker | optional (Week 7+) | Containerization for deployment |

---

## Project Structure

```
intelliwms/
│
├── README.md                          ← You are here
├── requirements.txt                   ← Python dependencies (exact pinned versions)
├── requirements.md                    ← Setup guide + LLM decision tree
├── .gitignore                         ← Git ignore rules (prevents .env commit)
├── .env.example                       ← Template of required env vars
├── .env                               ← ACTUAL env vars (gitignored, never commit)
│
├── config/                            ★ CENTRALIZED CONFIGURATION
│   ├── __init__.py
│   ├── settings.py                    ← Loads .env, exposes Settings class
│   ├── llm_config.py                  ← LLM provider abstraction (Gemini/Groq/Ollama)
│   └── prompts.py                     ← System prompts for all agents (centralized)
│
├── agents/                            ★ AGENT DEFINITIONS (owned by team members)
│   ├── __init__.py
│   ├── coordinator/                   ← Coordinator Agent (shared, build together first)
│   │   ├── __init__.py
│   │   ├── agent.py                   ← Coordinator Agent class definition
│   │   ├── tasks.py                   ← Coordinator's task definitions
│   │   └── tools.py                   ← Auth, routing, sanitization tools
│   │
│   ├── inventory_agent/               ← Member 1 owns this
│   │   ├── __init__.py
│   │   ├── agent.py
│   │   ├── tasks.py
│   │   └── tools.py
│   │
│   ├── knowledge_agent/               ← Member 2 owns this
│   │   ├── __init__.py
│   │   ├── agent.py
│   │   ├── tasks.py
│   │   └── tools.py
│   │
│   └── fulfillment_agent/             ← Member 3 owns this
│       ├── __init__.py
│       ├── agent.py
│       ├── tasks.py
│       └── tools.py
│
├── crews/                             ★ CREAI CREW ORCHESTRATION
│   ├── __init__.py
│   └── main_crew.py                   ← Instantiates all agents, defines crew
│
├── mcp_servers/                       ★ AGENT-TO-AGENT COMMUNICATION
│   ├── __init__.py
│   ├── coordinator_client.py          ← MCP client to call agents
│   ├── inventory_mcp.py               ← Exposes Inventory Agent's tools
│   ├── knowledge_mcp.py               ← Exposes Knowledge Agent's tools
│   └── fulfillment_mcp.py             ← Exposes Fulfillment Agent's tools
│
├── backend/                           ★ FASTAPI SERVER
│   ├── __init__.py
│   ├── main.py                        ← FastAPI app, route definitions
│   ├── routes/
│   │   ├── __init__.py
│   │   └── query.py                   ← POST /query endpoint
│   └── middleware/
│       ├── __init__.py
│       ├── auth.py                    ← JWT verification middleware
│       ├── cors.py                    ← CORS headers
│       └── error_handler.py           ← Global exception handling
│
├── database/                          ★ DATABASE & ORM
│   ├── __init__.py
│   ├── connection.py                  ← SQLAlchemy engine, session factory
│   ├── models.py                      ← User, Product, Order, ConversationLog tables
│   └── schemas.py                     ← Pydantic validation schemas
│
├── security/                          ★ AUTH & ENCRYPTION
│   ├── __init__.py
│   ├── jwt_handler.py                 ← JWT encode/decode
│   ├── rbac.py                        ← Role-based access control
│   ├── sanitizer.py                   ← Prompt injection detection
│   └── crypto.py                      ← PII encryption at rest
│
├── ir/                                ★ INFORMATION RETRIEVAL (RAG)
│   ├── __init__.py
│   ├── chroma_client.py               ← ChromaDB connection, utilities
│   ├── embeddings.py                  ← Embedding model setup
│   └── document_loader.py             ← Load SOPs/floor plans into Chroma
│
├── nlp/                               ★ NLP UTILITIES
│   ├── __init__.py
│   ├── ner.py                         ← spaCy NER (extract SKU/qty/date)
│   ├── summarizer.py                  ← Text summarization
│   └── classifier.py                  ← Intent classification
│
├── utils/                             ★ SHARED UTILITIES
│   ├── __init__.py
│   ├── logger.py                      ← Structured logging (JSON audit trail)
│   ├── retry_handler.py               ← Exponential backoff for API calls
│   ├── validators.py                  ← Common validation functions
│   └── formatters.py                  ← JSON/text formatting
│
├── frontend/                          ★ REACT APP
│   ├── package.json                   ← Node dependencies
│   ├── vite.config.js                 ← Vite build config
│   ├── index.html                     ← HTML entry point
│   └── src/
│       ├── main.jsx                   ← React entry (ReactDOM.render)
│       ├── App.jsx                    ← Main chat component
│       ├── index.css                  ← Styling
│       ├── services/
│       │   └── api.js                 ← Axios calls to backend
│       ├── components/
│       │   ├── ChatBox.jsx
│       │   ├── ResponseDisplay.jsx
│       │   └── AuthModal.jsx
│       └── styles/
│           └── app.css
│
├── data/                              ★ SAMPLE DATA
│   ├── sample_orders.json             ← ~50 fake orders
│   ├── sample_products.csv            ← ~100 SKUs with quantities
│   └── sample_docs/                   ← SOPs, floor plan, compliance docs (for RAG)
│       ├── returns_policy.txt
│       ├── safety_procedures.txt
│       ├── compliance_checklist.txt
│       └── floor_plan.txt
│
├── docs/                              ★ DOCUMENTATION
│   ├── architecture-diagram.md        ← System design, data flow diagrams
│   ├── agent-interaction-flow.md      ← Step-by-step agent communication
│   ├── llm-selection-guide.md         ← Gemini vs Groq vs Ollama trade-offs
│   ├── responsible-ai.md              ← Fairness, transparency, privacy, security
│   └── api-reference.md               ← POST /query payload format
│
├── tests/                             ★ TEST SUITE
│   ├── __init__.py
│   ├── test_coordinator.py            ← Test /query endpoint
│   ├── test_agents.py                 ← Test agent behavior
│   ├── test_auth.py                   ← Test JWT, RBAC
│   ├── test_mcp.py                    ← Test inter-agent communication
│   └── conftest.py                    ← pytest fixtures (mocks)
│
├── scripts/                           ★ AUTOMATION SCRIPTS
│   ├── seed_database.py               ← Populate DB with sample data
│   ├── load_vectors.py                ← Load documents into ChromaDB
│   └── test_llm.py                    ← Quick LLM connection test
│
├── logs/                              ★ APPLICATION LOGS (gitignored)
│   └── .gitkeep
│
└── docker-compose.yml                 ★ DOCKER (optional, Week 7+)
```

**Key principles:**
- **One file = one responsibility** — no God files
- **Shared config** — all env vars, LLM clients, prompts in `/config/`
- **Team-owned agents** — each member's agent in its own folder with zero overlap
- **Separation of concerns** — security, database, frontend, backend are distinct layers

---

## Team Ownership

**This is a 3-person team project.** Each person owns one agent + one cross-cutting responsibility.

| Member | Agent | Owns | Branch | Individual Specialization |
|---|---|---|---|---|
| **Member 1** | Inventory Agent | `agents/inventory_agent/` + `mcp_servers/inventory_mcp.py` | `feature/inventory-agent` | Prompt Injection & Jailbreak Testing |
| **Member 2** | Knowledge Agent | `agents/knowledge_agent/` + `mcp_servers/knowledge_mcp.py` | `feature/knowledge-agent` | IR & Security Assessment |
| **Member 3** | Fulfillment Agent | `agents/fulfillment_agent/` + `mcp_servers/fulfillment_mcp.py` | `feature/fulfillment-agent` | Privacy & Data Leakage Testing |
| **Shared** | Coordinator Agent | `agents/coordinator/` + `backend/` + `security/` + `config/` + `database/` | `feature/coordinator` | Responsible AI & Bias Testing |

**Important:** The **Coordinator Agent is shared**. All 3 team members build it together on `feature/coordinator` before splitting into individual agent branches. This is the foundation everything depends on.

---

## Quick Start

### Prerequisites
- Python 3.12.13
- Node.js 22.22.0 LTS
- PostgreSQL 16.15
- Git (latest)
- VS Code (recommended)

### 5-Minute Setup

```bash
# 1. Clone the repo
git clone https://github.com/<your-org>/intelliwms.git
cd intelliwms

# 2. Python backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# 3. Create .env from template
cp .env.example .env
# Edit .env with your actual API keys and database URL

# 4. Database
python scripts/seed_database.py   # Creates tables + sample data

# 5. Frontend
cd frontend && npm install && npm run dev &
cd ..

# 6. Start backend
uvicorn backend.main:app --reload

# 7. Open http://localhost:5173 in browser
```

**That's it!** Backend runs on :8000, Frontend on :5173, they talk via HTTP.

---

## Development Workflow

### Phase 1: Coordinator Agent (Week 1, all together)
```bash
git checkout feature/coordinator
# All 3 members build:
# - Task 1 (Person A): Security layer (JWT, RBAC, sanitization)
# - Task 2 (Person B): Intent routing (classify intent via LLM, route to agent)
# - Task 3 (Person C): API gateway (FastAPI endpoint, MCP client)
# Commit frequently with clear messages
```

**Success criteria:**
- `POST /query` endpoint accepts a message, validates JWT, classifies intent, routes to stub agent
- Coordinator → Inventory Agent MCP call works (logged, testable)
- All unit tests pass: `pytest tests/test_coordinator.py`

### Phase 2: Individual Agents (Weeks 2–5)
```bash
# Member 1
git checkout feature/inventory-agent
# Build Document Parser, Reorder Predictor, Anomaly Watcher, Transfer Advisor, Equipment Health
# Open PR, get reviewed, merge

# Member 2
git checkout feature/knowledge-agent
# Build Location Finder (RAG), Returns Handler, Training Assistant, Compliance Checker, Shift Handoff
# Open PR, get reviewed, merge

# Member 3
git checkout feature/fulfillment-agent
# Build Order Diagnostics (queries Inventory directly), Vendor Report Generator, Complaint Triage, Communication Bridge
# Open PR, get reviewed, merge
```

### Phase 3: Mid-Evaluation (Week 6–7)
```bash
# All on main branch
# Demo: "Why is order #4521 delayed?"
#   → Coordinator routes to Fulfillment
#   → Fulfillment queries Inventory Agent via MCP
#   → Response: "Delayed because SKU-4521 out of stock; supplier delivery Friday"
# Discuss: architecture, Responsible AI, commercialization
```

### Phase 4: Polish & Final Submission (Weeks 8–10)
```bash
# Incorporate mid-eval feedback
# Write report
# Record 3–5 min Gen AI video (screen narration + architecture demo)
# Final commit to main
```

---

## Running the System

### Start Everything (3 terminal windows)

**Terminal 1: Backend**
```bash
source venv/bin/activate
uvicorn backend.main:app --reload
# Logs: Uvicorn running on http://127.0.0.1:8000
```

**Terminal 2: Frontend**
```bash
cd frontend
npm run dev
# Logs: VITE v6.0.7 ready at http://localhost:5173/
```

**Terminal 3: (Optional) Logs**
```bash
tail -f logs/app.log
```

### Test Endpoints

**Health check:**
```bash
curl http://localhost:8000/health
# Returns: {"status":"ok","message":"IntelliWMS backend is running"}
```

**Query endpoint (when implemented):**
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "token": "your_jwt_token_here",
    "message": "where is SKU-4521?"
  }'
```

**Using Insomnia (GUI):**
1. Import `IntelliWMS.postman_collection.json` (if provided)
2. Set `Authorization` header with Bearer token
3. Hit endpoints

---

## Git Workflow & Branching

### Branching Strategy

```
main (production/submission)
├── feature/coordinator (shared, all 3 build together)
│   └── (merge to main when complete)
├── feature/inventory-agent (Member 1)
│   └── (merge to main when complete)
├── feature/knowledge-agent (Member 2)
│   └── (merge to main when complete)
└── feature/fulfillment-agent (Member 3)
    └── (merge to main when complete)
```

### Workflow per person

```bash
# Start work on your feature
git checkout feature/<your-agent>

# Make changes
git add <files>
git commit -m "feat: add <specific feature>"

# Push to GitHub
git push origin feature/<your-agent>

# Open Pull Request on GitHub
# → Get 1 approval from a teammate
# → Merge (GitHub button)

# Pull latest main locally
git checkout main
git pull origin main
```

### Commit Message Conventions

Keep them clear and specific:
```
feat: add JWT validation to Coordinator Agent
fix: handle null values in sanitizer
docs: update README with setup steps
test: add unit test for RBAC
refactor: extract LLM client to config module
```

**Why:** Your viva checks commit history for individual contribution. "added stuff" doesn't show what you did; "feat: add Inventory Agent's Document Parser tool" does.

---

## Environment Setup

### PostgreSQL Local Setup

**Mac (Homebrew):**
```bash
brew install postgresql@16
brew services start postgresql@16
createdb -U postgres intelliwms
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get install postgresql-16
sudo systemctl start postgresql
sudo -u postgres createdb intelliwms
```

**Windows (installer):**
- Download from https://www.postgresql.org/download/windows/
- Remember the password you set for user `postgres`
- PostgreSQL starts automatically after install

### .env Configuration

Copy `.env.example` to `.env` and fill in actual values:

```bash
# LLM Configuration
LLM_PRIMARY=gemini  # Primary LLM (gemini, groq, or ollama)

# Gemini (free, recommended)
GEMINI_API_KEY=sk-proj-your-actual-key-here
# Get it from: https://aistudio.google.com/apikey

# Groq (free, fallback)
GROQ_API_KEY=your-groq-key-here
# Get it from: https://console.groq.com

# Ollama (optional, local)
OLLAMA_URL=http://localhost:11434
# Install from: https://ollama.com/download

# Database (PostgreSQL)
DATABASE_URL=postgresql://postgres:your_password@localhost:5432/intelliwms

# JWT Secret (for token signing)
JWT_SECRET=your-super-secret-key-change-in-production-min-32-chars

# Logging
LOG_LEVEL=INFO  # or DEBUG, WARNING, ERROR
```

**Never commit `.env`** — it's gitignored for a reason.

---

## Database Setup

### Create Tables

```bash
python scripts/seed_database.py
```

This creates:
- `users` — staff members (username, role: staff/manager)
- `products` — inventory SKUs (sku, name, quantity, location)
- `orders` — customer orders (order_id, sku, status: pending/delayed/shipped)
- `conversation_logs` — audit trail of all queries

### Verify

```bash
psql -U postgres -d intelliwms -c "SELECT * FROM products;"
# Should show ~3 sample products
```

### Reset (if needed)

```bash
# Drop and recreate (loses all data)
psql -U postgres -c "DROP DATABASE intelliwms;"
python scripts/seed_database.py
```

---

## Testing

### Run All Tests

```bash
pytest tests/
```

### Run Specific Test File

```bash
pytest tests/test_coordinator.py -v
pytest tests/test_auth.py -v
```

### Run with Coverage Report

```bash
pytest tests/ --cov=. --cov-report=html
# Opens htmlcov/index.html in browser
```

### Test Categories

- **`test_coordinator.py`** — POST /query endpoint, routing logic
- **`test_agents.py`** — Agent behavior, tool calling
- **`test_auth.py`** — JWT, RBAC, permissions
- **`test_mcp.py`** — Inter-agent communication via MCP
- **`test_security.py`** — Input sanitization, prompt injection detection

---

## Troubleshooting

### Python: "ModuleNotFoundError: No module named 'fastapi'"

**Solution:**
```bash
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### PostgreSQL: "psql: error: connection refused"

**Solution:**
```bash
# Check if PostgreSQL is running
# Mac: brew services list | grep postgresql
# Linux: sudo systemctl status postgresql
# Windows: Search "Services", look for "PostgreSQL"

# If not running, start it:
# Mac: brew services start postgresql@16
# Linux: sudo systemctl start postgresql
# Windows: Restart the PostgreSQL service
```

### Frontend: "Cannot GET /api/query"

**Solution:**
Make sure backend is running on port 8000:
```bash
uvicorn backend.main:app --reload
# Should show "Uvicorn running on http://127.0.0.1:8000"
```

Also verify vite.config.js has the proxy rule.

### "GEMINI_API_KEY not set"

**Solution:**
1. Make sure `.env` file exists in repo root (not inside a folder)
2. Check `.env` has `GEMINI_API_KEY=your_actual_key`
3. Restart your backend: `uvicorn backend.main:app --reload`

### "chromadb not found"

**Solution:**
```bash
pip install chromadb==1.5.9
```

### Tests fail with "conftest.py not found"

**Solution:**
Make sure you're running pytest from the repo root:
```bash
cd /path/to/intelliwms
pytest tests/
```

### React: "axios is not defined"

**Solution:**
```bash
cd frontend
npm install axios
```

### Vite: "VITE_* is not defined"

**Solution:**
Environment variables in Vite need `VITE_` prefix. In `.env`:
```
VITE_API_URL=http://localhost:8000
```

Then in React:
```javascript
const apiUrl = import.meta.env.VITE_API_URL;
```

---

## Responsible AI

This is **not a checkbox feature** — it's baked into the system design.

### What We're Building For

1. **Transparency** — Knowledge Agent cites its sources. "According to the Returns SOP (Section 2.3), ..."
2. **Explainability** — Every agent decision is logged with reasoning. Audit trail proves the agent reasoned its way to a choice, not just scripted.
3. **Fairness** — Anomaly Watcher doesn't profile by employee ID. No discrimination in detection.
4. **Privacy** — Customer names/addresses encrypted at rest. Access logged. PII handled carefully.
5. **Security** — Input sanitization against prompt injection. Guardrails prevent "ignore instructions" attacks.

### Key Files

- `security/sanitizer.py` — detects prompt injection attempts
- `utils/logger.py` — logs every decision (JSON audit trail)
- `security/rbac.py` — enforces role-based access (staff can't approve restocks)
- `security/crypto.py` — encrypts PII at rest

### Evidence You'll Show in the Viva

```bash
# Check the audit logs
tail logs/app.log | grep "AGENT_DECISION"
# See structured JSON showing what the agent decided and why
```

---

## Commercialization

**Target market:** Mid-size 3PL warehouses and retail distribution centers

**Problem they face:**
- Too small for enterprise WMS (SAP costs $1M+ to implement)
- Big enough to feel the daily pain of manual lookup/re-typing
- Typically 50–200 staff, 3–5 manual support roles just for warehouse coordination

**Our value proposition:**
- Cut staff time on lookup/data entry by 70%
- Reduce restock-request errors from ~5% to <1%
- Speed up customer-facing delay explanations from 3 min to 30 sec

**Pricing model (SaaS):**
- **Starter:** $500/month (flat) — 1 warehouse, up to 5 staff, 100 queries/day
- **Professional:** $1,500/month base + $0.01/query — growing teams, 1K+ queries/day
- **Enterprise:** Custom pricing — multi-warehouse, on-prem, SSO, SLAs

**Deployment:**
- Cloud-hosted (default) — multi-tenant SaaS
- On-prem (Enterprise tier) — for clients wary of inventory data leaving their network

**Market size:**
- ~5,000 mid-size warehouses in developed markets
- 2% adoption = $600K ARR @ $500/month average

---

## Timeline

| Week | Milestone | Deliverables |
|---|---|---|
| **1–2** | Coordinator Agent (all 3 build together) | Working POST /query endpoint, MCP wiring, unit tests passing |
| **2–5** | Individual agents | Inventory (Member 1), Knowledge (Member 2), Fulfillment (Member 3) complete their agents, open PRs, merge to main |
| **6–7** | Mid-Evaluation | 15-min discussion: domain rationale, architecture, agent interaction (MCP demo), Responsible AI approach, commercialization pitch. 20 marks. |
| **8–9** | Feedback + Polish | Incorporate mid-eval feedback, security hardening, final features |
| **10** | Final Submission | Gen AI video (3–5 min, screen narrated), Report (system design, Responsible AI, commercialization), GitHub (clean README, all commits visible) |
| **11** | Viva | Group viva (defend architecture, individual contribution), then individual vivaes (each member defends their agent + their audit findings) |

---

## FAQ

### Q: What if I'm stuck on my agent?
**A:** Post in the #intelliwms Slack channel. Your teammates (or me, if you share the repo) can look at your branch and unblock you in 5 min.

### Q: Can I use a different LLM?
**A:** Yes. Edit `config/llm_config.py` to add your provider. As long as it has a Python SDK, it'll work.

### Q: What if the Coordinator isn't done when I need to start my agent?
**A:** The Coordinator is shared; all 3 build it first. It takes 1–2 hours. Block this time on your calendar together.

### Q: How do I know if my agent is "agentic" enough?
**A:** Your agent should use the LLM to *decide* which tool to invoke. If your code has `if "stock" in message: call_tool_1()`, that's not agentic—that's scripted. If it's `llm.invoke("pick the right tool for this message")`, that's agentic.

### Q: Do I need to understand MCP deeply?
**A:** No. Just know: agents expose tools as MCP servers, other agents call them. The MCP SDK handles the wiring. You mostly use: `mcp_client.call_tool(agent, tool_name, args)`.

### Q: What's a good commit message?
**A:** `git commit -m "feat: add Document Parser NER to Inventory Agent"` (specific, linked to your agent). Not: `git commit -m "stuff"`.

---

## Contributors

- **Member 1** — Inventory Agent
- **Member 2** — Knowledge Agent  
- **Member 3** — Fulfillment Agent

---

## License

Academic project (IT3041, XYZ University). Not for commercial use without instructor approval.

---

## Support

- **Questions?** Check docs/ folder for architecture deep-dives
- **Stuck?** See Troubleshooting section above
- **Code review?** Open a PR on your feature branch, tag a teammate, get feedback
- **Emergency?** Post in team Slack #intelliwms channel

---

**Good luck. Build with confidence. You've got this.**

---

## Last Updated

August 2026 — Verified against CrewAI 1.14.6, FastAPI 0.141.1, PostgreSQL 16.15, React 19.2.8
