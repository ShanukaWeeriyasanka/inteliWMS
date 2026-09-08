# IntelliWMS Skeleton Setup — Step-by-Step Manual Build Guide

**Goal:** You'll build the complete project skeleton manually, understanding *why* each file exists and *what* goes in it.  
**Timeline:** ~2 hours to read + execute all steps  
**Result:** A working Python + React environment ready for the Coordinator Agent

---

## PHASE 1: Project Initialization (15 min)

### Step 1.1: Create the root folder and initialize Git

```bash
mkdir intelliwms
cd intelliwms
git init
git config user.name "Your Name"
git config user.email "your@email.com"
```

**Why:** Git tracks all your work. Every file you create will be committed so your teammates can see your progress.

---

### Step 1.2: Create the folder structure (copy-paste this entire block)

```bash
# Core agent folders
mkdir -p agents/coordinator
mkdir -p agents/inventory_agent
mkdir -p agents/knowledge_agent
mkdir -p agents/fulfillment_agent

# Backend infrastructure
mkdir -p backend/routes
mkdir -p backend/middleware

# Configuration
mkdir -p config

# Security
mkdir -p security

# Information Retrieval (vector store)
mkdir -p ir

# NLP utilities
mkdir -p nlp

# Database
mkdir -p database

# MCP servers (agent communication)
mkdir -p mcp_servers

# Shared utilities
mkdir -p utils

# Frontend
mkdir -p frontend/src/{components,services,styles}

# Documentation
mkdir -p docs

# Tests
mkdir -p tests

# Sample data
mkdir -p data

# Scripts
mkdir -p scripts

# Logs (will be gitignored)
mkdir -p logs
```

**Why:** This structure mirrors the architecture you studied. Each folder has a clear responsibility:
- `agents/` = where your AI agents live
- `backend/` = FastAPI server (REST API)
- `config/` = centralized configuration (settings, LLM clients, prompts)
- `security/` = auth, encryption, sanitization
- `database/` = database models and ORM
- etc.

Run this command and verify:
```bash
tree -L 2  # or just `ls -la` to see the folders
```

---

## PHASE 2: Environment & Configuration (20 min)

### Step 2.1: Create `.env.example` (template, safe to commit)

**What it is:** A template showing what environment variables your app needs. This file is committed to Git so teammates know what keys to set up.

```bash
cat > .env.example << 'EOF'
# LLM Configuration
LLM_PRIMARY=gemini  # or "groq" or "ollama"
GEMINI_API_KEY=your_gemini_key_here
GROQ_API_KEY=your_groq_key_here
OLLAMA_URL=http://localhost:11434

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/intelliwms

# JWT & Security
JWT_SECRET=your-secret-key-change-in-production

# Logging
LOG_LEVEL=INFO
EOF
```

**Why:** This is a checklist for your team. When someone clones the repo, they see what they need to configure.

---

### Step 2.2: Create `.env` (actual, gitignored, never commit)

**What it is:** The *real* file with your *actual* keys. This is private to your machine.

```bash
cp .env.example .env
```

Now edit `.env` with your real keys:
```bash
nano .env  # or use VS Code to edit it
```

**Change these lines in `.env`:**
```
GEMINI_API_KEY=sk-proj-your-actual-key-here
GROQ_API_KEY=your-actual-groq-key-here
DATABASE_URL=postgresql://postgres:your_password@localhost:5432/intelliwms
JWT_SECRET=your-super-secret-key-here-minimum-32-chars-long
```

**Why:** `.env` stores secrets. It's gitignored so your API keys never accidentally get pushed to GitHub.

---

### Step 2.3: Create `.gitignore`

**What it is:** Tells Git which files to ignore (not track). Prevents secrets from being committed.

```bash
cat > .gitignore << 'EOF'
# Python
venv/
__pycache__/
*.pyc
*.pyo
*.egg-info/
dist/
build/

# Environment
.env
.env.local
.env.*.local

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# Database
*.db
*.sqlite3
chroma_db/

# Logs
logs/
*.log

# Frontend
frontend/node_modules/
frontend/dist/
frontend/.vite

# OS
.DS_Store
Thumbs.db

# Testing
.pytest_cache/
.coverage
htmlcov/
EOF
```

**Why:** This prevents you from accidentally committing `.env`, `__pycache__/`, `venv/`, etc. into Git.

**Test it:**
```bash
git status  # should show .env is NOT staged (gitignored)
```

---

## PHASE 3: Backend Setup (40 min)

### Step 3.1: Create `requirements.txt` (Python dependencies)

**What it is:** A list of Python packages your app needs. Teammates run `pip install -r requirements.txt` to get the exact same versions.

```bash
cat > requirements.txt << 'EOF'
crewai==1.14.6
crewai-tools==1.15.5
fastapi==0.141.1
uvicorn[standard]==0.35.0
pydantic==2.10.6
python-dotenv==1.0.1
chromadb==1.5.9
spacy==3.8.4
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.20
httpx==0.28.1
pytest==8.3.4
psycopg2-binary==2.9.10
sqlalchemy==2.0.36

# LLM SDKs
google-genai==1.4.0
anthropic==0.42.0
openai==1.59.0
EOF
```

**Why:** This is your dependency manifest. If one person uses `fastapi==0.140.0` and another uses `0.141.1`, they get different bugs. Pinning versions prevents "works on my machine" issues.

---

### Step 3.2: Create Python virtual environment

**What it is:** A sandboxed Python environment for this project only. Prevents package conflicts with other Python projects on your machine.

```bash
python3 -m venv venv
source venv/bin/activate      # Mac/Linux
# OR
venv\Scripts\activate          # Windows
```

**Verify:**
```bash
python --version              # should show 3.12.13
which python                  # should point to ./venv/bin/python
```

---

### Step 3.3: Install dependencies

```bash
pip install -r requirements.txt
pip install -r requirements.txt  # Run twice to ensure all install

# Download spaCy's NER model (separate from pip)
python -m spacy download en_core_web_sm
```

**Why:** spaCy's pre-trained models aren't pip packages—they're downloaded separately. This model recognizes entities (SKU, dates, quantities) in text.

**Wait time:** ~2–3 minutes depending on internet speed.

---

### Step 3.4: Create `config/settings.py` (centralized configuration)

**What it is:** Python reads `.env` file here and makes those values available to the rest of your app.

```bash
cat > config/__init__.py << 'EOF'
"""Configuration package."""
EOF
```

```bash
cat > config/settings.py << 'EOF'
import os
from dotenv import load_dotenv

load_dotenv()  # Reads .env file

class Settings:
    """Centralized settings loaded from environment variables."""
    
    # LLM Configuration
    LLM_PRIMARY = os.getenv("LLM_PRIMARY", "gemini")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
    
    # Database
    DATABASE_URL = os.getenv("DATABASE_URL")
    
    # JWT & Security
    JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Create a singleton instance
settings = Settings()

# Validate critical settings on startup
if not settings.DATABASE_URL:
    raise ValueError("DATABASE_URL not set in .env")
if not settings.JWT_SECRET or len(settings.JWT_SECRET) < 16:
    raise ValueError("JWT_SECRET must be set and at least 16 chars")

EOF
```

**Why:** All your app's configuration is in ONE place. Change an API key? Edit this file, not scattered throughout your codebase.

---

### Step 3.5: Create `config/llm_config.py` (LLM provider abstraction)

**What it is:** Sets up Gemini/Groq/Ollama clients. Your agents don't care which LLM they use—they just ask this file for a client.

```bash
cat > config/llm_config.py << 'EOF'
import os
import google.generativeai as genai
from groq import Groq
import requests
from config.settings import settings

class LLMConfig:
    """Centralized LLM provider configuration with fallback logic."""
    
    def __init__(self):
        self.primary_provider = settings.LLM_PRIMARY
        self.gemini_key = settings.GEMINI_API_KEY
        self.groq_key = settings.GROQ_API_KEY
        self.ollama_url = settings.OLLAMA_URL
    
    def get_client(self, provider=None):
        """
        Get an LLM client for the specified provider.
        Falls back to next provider if the primary one fails.
        """
        provider = provider or self.primary_provider
        
        try:
            if provider == "gemini":
                if not self.gemini_key:
                    raise ValueError("GEMINI_API_KEY not set")
                genai.configure(api_key=self.gemini_key)
                return genai.GenerativeModel("gemini-2.5-flash")
            
            elif provider == "groq":
                if not self.groq_key:
                    raise ValueError("GROQ_API_KEY not set")
                return Groq(api_key=self.groq_key)
            
            elif provider == "ollama":
                # Test connection to Ollama server
                resp = requests.get(f"{self.ollama_url}/api/tags")
                if resp.status_code == 200:
                    return {"type": "ollama", "url": self.ollama_url, "model": "llama3.3:8b"}
                raise ConnectionError(f"Ollama server not responding at {self.ollama_url}")
        
        except Exception as e:
            print(f"Provider {provider} failed: {e}")
            # Fallback logic: try next provider
            if provider != "groq":
                print(f"Falling back to groq...")
                return self.get_client("groq")
            elif provider != "ollama":
                print(f"Falling back to ollama...")
                return self.get_client("ollama")
            else:
                raise RuntimeError("All LLM providers exhausted")

# Singleton instance
llm_config = LLMConfig()

EOF
```

**Why:** When Gemini's rate limit is hit, your app automatically tries Groq. No code changes needed—just relies on this abstraction.

---

### Step 3.6: Create `config/prompts.py` (system prompts for agents)

**What it is:** All your LLM system prompts in one file. Don't hardcode prompts inside agent code.

```bash
cat > config/prompts.py << 'EOF'
"""
System prompts for each agent.
Keep these centralized so they're easy to tweak without touching agent code.
"""

COORDINATOR_SYSTEM_PROMPT = """You are the Coordinator Agent for IntelliWMS, a warehouse management system.

Your job is to:
1. Read the user's natural-language query
2. Understand what domain it belongs to: INVENTORY, KNOWLEDGE, or FULFILLMENT
3. Respond with a JSON decision in this exact format:
   {
     "domain": "INVENTORY|KNOWLEDGE|FULFILLMENT",
     "confidence": 0.95,
     "reasoning": "User asked about stock levels, which is an Inventory concern."
   }

Rules:
- Always respond with valid JSON, no extra text.
- If unsure, default to KNOWLEDGE (safest fallback).
- Be concise in your reasoning (1 sentence max).
"""

INVENTORY_AGENT_SYSTEM_PROMPT = """You are the Inventory Agent for IntelliWMS.

You handle:
- Stock level queries
- Reorder predictions
- Shrinkage/anomaly detection
- Inter-warehouse transfers
- Equipment maintenance alerts

Respond conversationally with warehouse staff. If you don't know something, say so.
"""

KNOWLEDGE_AGENT_SYSTEM_PROMPT = """You are the Knowledge Agent for IntelliWMS.

You specialize in:
- Warehouse location lookups (where is SKU X?)
- Standard Operating Procedures (SOPs)
- Safety and compliance documents
- New-hire training
- Shift handoff notes

ALWAYS cite your sources. For example: "According to the Returns SOP (Section 2.3), ..."

If you don't find a document, say so clearly.
"""

FULFILLMENT_AGENT_SYSTEM_PROMPT = """You are the Fulfillment Agent for IntelliWMS.

You handle:
- Order status and delay explanations
- Vendor performance summaries
- Customer complaint triage
- Multilingual staff communication

When diagnosing order delays, always check with the Inventory Agent for real-time stock/ETA data.
"""

EOF
```

**Why:** Changing a system prompt doesn't require redeploying code. Edit this file, restart your app, and the new prompt is live.

---

### Step 3.7: Create `utils/logger.py` (structured logging)

**What it is:** Sets up logging for the entire app. Every agent decision gets logged for audit trails (Responsible AI requirement).

```bash
cat > utils/__init__.py << 'EOF'
"""Utilities package."""
EOF
```

```bash
cat > utils/logger.py << 'EOF'
import logging
import json
from datetime import datetime
from config.settings import settings

# Configure root logger
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log'),
        logging.StreamHandler()
    ]
)

class StructuredLogger:
    """Logger that outputs JSON for easier parsing and auditing."""
    
    def __init__(self, name):
        self.logger = logging.getLogger(name)
    
    def log_event(self, event_type, details):
        """Log an event as structured JSON."""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            **details
        }
        self.logger.info(json.dumps(entry))
    
    def log_agent_decision(self, agent_name, input_msg, decision, reasoning):
        """Log an agent's decision (for Responsible AI transparency)."""
        self.log_event("AGENT_DECISION", {
            "agent": agent_name,
            "input": input_msg,
            "decision": decision,
            "reasoning": reasoning
        })
    
    def log_security_event(self, event, user_id, details):
        """Log security-related events (auth, sanitization, RBAC)."""
        self.log_event("SECURITY_EVENT", {
            "security_event": event,
            "user_id": user_id,
            **details
        })

EOF
```

**Why:** JSON logs are machine-readable. You can grep/parse them for audits. And your Responsible AI evaluator can see exactly how agents decided.

---

## PHASE 4: Database Setup (20 min)

### Step 4.1: Create `database/__init__.py`

```bash
cat > database/__init__.py << 'EOF'
"""Database package."""
EOF
```

---

### Step 4.2: Create `database/connection.py` (database connection)

**What it is:** Sets up SQLAlchemy connection to PostgreSQL.

```bash
cat > database/connection.py << 'EOF'
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from config.settings import settings

# Create database engine
engine = create_engine(settings.DATABASE_URL)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for all models
Base = declarative_base()

def get_db():
    """Dependency injection for FastAPI routes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

EOF
```

**Why:** This is how your Python code talks to PostgreSQL. Every agent that needs to query the database uses this connection.

---

### Step 4.3: Create `database/models.py` (database schema)

**What it is:** Defines the tables in your database (User, Product, Order) using SQLAlchemy ORM.

```bash
cat > database/models.py << 'EOF'
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, Boolean
from sqlalchemy.sql import func
from database.connection import Base

class User(Base):
    """User/staff member."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String)  # "staff" or "manager"
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Product(Base):
    """Warehouse product/SKU."""
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String, unique=True, index=True)
    name = Column(String)
    quantity = Column(Integer)
    location = Column(String)  # e.g., "Aisle 12, Shelf B3"
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Order(Base):
    """Customer order."""
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String, unique=True, index=True)
    customer_name = Column(String)
    sku = Column(String, index=True)
    quantity = Column(Integer)
    status = Column(String)  # "pending", "shipped", "delayed"
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ConversationLog(Base):
    """Log of all queries for audit trail."""
    __tablename__ = "conversation_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String)
    message = Column(String)
    agent_routed_to = Column(String)
    response = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

EOF
```

**Why:** These tables store your warehouse data (inventory, orders, users). Agents query this data to answer questions.

---

### Step 4.4: Create `scripts/seed_database.py` (populate sample data)

**What it is:** A script that creates tables and fills them with fake data so you can test without manual entry.

```bash
cat > scripts/__init__.py << 'EOF'
"""Scripts package."""
EOF
```

```bash
cat > scripts/seed_database.py << 'EOF'
"""
Populate the database with sample data for testing.
Run this once after creating the database.
"""

from database.connection import engine, Base, SessionLocal
from database.models import User, Product, Order

def seed_database():
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    # Clear existing data (optional)
    db.query(User).delete()
    db.query(Product).delete()
    db.query(Order).delete()
    
    # Add sample users
    users = [
        User(username="john_staff", email="john@warehouse.com", hashed_password="hashed123", role="staff"),
        User(username="sarah_manager", email="sarah@warehouse.com", hashed_password="hashed456", role="manager"),
    ]
    db.add_all(users)
    
    # Add sample products
    products = [
        Product(sku="SKU-4521", name="Widget A", quantity=340, location="Aisle 12, Shelf B3"),
        Product(sku="SKU-7788", name="Widget B", quantity=150, location="Aisle 5, Shelf A1"),
        Product(sku="SKU-9012", name="Widget C", quantity=50, location="Aisle 3, Shelf C2"),
    ]
    db.add_all(products)
    
    # Add sample orders
    orders = [
        Order(order_id="4521", customer_name="Acme Corp", sku="SKU-4521", quantity=50, status="delayed"),
        Order(order_id="4522", customer_name="Widgets Inc", sku="SKU-7788", quantity=30, status="pending"),
        Order(order_id="4523", customer_name="Tools Ltd", sku="SKU-9012", quantity=20, status="shipped"),
    ]
    db.add_all(orders)
    
    # Commit all changes
    db.commit()
    print("✓ Database seeded with sample data")
    db.close()

if __name__ == "__main__":
    seed_database()

EOF
```

**Why:** When you run `python scripts/seed_database.py`, it creates all tables and fills them with 3 products and 3 orders. Now you have data to query.

---

### Step 4.5: Run the seeding script

```bash
python scripts/seed_database.py
```

**Verify:**
```bash
psql -U postgres -d intelliwms -c "SELECT * FROM products;"
```

You should see:
```
 id |   sku   |  name   | quantity |       location       | created_at
----+---------+---------+----------+----------------------+------------
  1 | SKU-4521 | Widget A |      340 | Aisle 12, Shelf B3   | 2026-08-...
  2 | SKU-7788 | Widget B |      150 | Aisle 5, Shelf A1    | 2026-08-...
  ...
```

---

## PHASE 5: Backend Server Setup (15 min)

### Step 5.1: Create `backend/__init__.py`

```bash
cat > backend/__init__.py << 'EOF'
"""Backend package."""
EOF
```

---

### Step 5.2: Create `backend/main.py` (FastAPI app)

**What it is:** The core FastAPI application. Defines routes, middleware, and starts the server.

```bash
cat > backend/main.py << 'EOF'
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config.settings import settings
from utils.logger import StructuredLogger

# Initialize FastAPI app
app = FastAPI(
    title="IntelliWMS",
    description="Agentic AI Warehouse Management System",
    version="0.1.0"
)

# Setup logging
logger = StructuredLogger(__name__)

# Add CORS middleware (allow React frontend to call backend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Vite/React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoint (to verify server is running)
@app.get("/health")
def health_check():
    """Simple health check endpoint."""
    return {"status": "ok", "message": "IntelliWMS backend is running"}

# Placeholder for /query endpoint (will be added in Task 3 of Coordinator setup)
@app.post("/query")
def query(request: dict):
    """Coordinator Agent endpoint."""
    return {"status": "error", "message": "Coordinator Agent not yet implemented"}

if __name__ == "__main__":
    import uvicorn
    logger.log_event("SERVER_START", {"message": "Starting IntelliWMS backend"})
    uvicorn.run(app, host="0.0.0.0", port=8000)

EOF
```

**Why:** This is your server. When you run `uvicorn backend.main:app --reload`, FastAPI starts listening on http://localhost:8000.

---

### Step 5.3: Create `backend/routes/__init__.py`

```bash
cat > backend/routes/__init__.py << 'EOF'
"""Routes package."""
EOF
```

---

### Step 5.4: Test the backend

```bash
uvicorn backend.main:app --reload
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete
```

Test the health endpoint in another terminal:
```bash
curl http://localhost:8000/health
```

Should return:
```json
{"status":"ok","message":"IntelliWMS backend is running"}
```

**Keep this running** for the next steps (React frontend needs it).

---

## PHASE 6: Frontend Setup (15 min)

### Step 6.1: Create `frontend/package.json`

**What it is:** React dependencies and build scripts. Like Python's `requirements.txt` but for JavaScript.

```bash
cat > frontend/package.json << 'EOF'
{
  "name": "intelliwms-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "19.2.8",
    "react-dom": "19.2.8",
    "axios": "1.7.9"
  },
  "devDependencies": {
    "vite": "6.0.7",
    "@vitejs/plugin-react": "4.3.4"
  }
}
EOF
```

---

### Step 6.2: Create `frontend/vite.config.js` (build configuration)

**What it is:** Tells Vite (the frontend bundler) how to build React code.

```bash
cat > frontend/vite.config.js << 'EOF'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000'  # Route /api calls to backend
    }
  }
})
EOF
```

**Why:** When React makes a call to `/api/query`, Vite proxies it to `http://localhost:8000/query`. Prevents CORS headaches during development.

---

### Step 6.3: Create `frontend/index.html`

**What it is:** The HTML entry point for your React app. Vite injects the React bundle here.

```bash
cat > frontend/index.html << 'EOF'
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>IntelliWMS</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
EOF
```

---

### Step 6.4: Create `frontend/src/main.jsx` (React entry)

**What it is:** Mounts the React app into the `<div id="root">` from index.html.

```bash
cat > frontend/src/main.jsx << 'EOF'
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
EOF
```

---

### Step 6.5: Create `frontend/src/App.jsx` (React component)

**What it is:** The main React component. Your chat interface lives here.

```bash
cat > frontend/src/App.jsx << 'EOF'
import { useState } from 'react'
import axios from 'axios'
import './App.css'

function App() {
  const [message, setMessage] = useState('')
  const [response, setResponse] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSend = async () => {
    if (!message.trim()) return

    setLoading(true)
    setError('')
    setResponse('')

    try {
      // For now, just test the backend health
      const res = await axios.get('http://localhost:8000/health')
      setResponse(`Backend is healthy: ${JSON.stringify(res.data)}`)
      setMessage('')
    } catch (err) {
      setError(`Error: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="container">
      <h1>IntelliWMS — Warehouse Query Assistant</h1>
      
      <div className="chat-box">
        <input
          type="text"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && handleSend()}
          placeholder="Ask about warehouse operations..."
          disabled={loading}
        />
        <button onClick={handleSend} disabled={loading}>
          {loading ? 'Sending...' : 'Send'}
        </button>
      </div>

      {response && (
        <div className="response">
          <strong>Backend Response:</strong>
          <p>{response}</p>
        </div>
      )}

      {error && (
        <div className="error">
          <strong>Error:</strong>
          <p>{error}</p>
        </div>
      )}
    </div>
  )
}

export default App
EOF
```

---

### Step 6.6: Create `frontend/src/index.css` (styling)

**What it is:** Basic CSS to make the chat interface look decent.

```bash
cat > frontend/src/index.css << 'EOF'
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", "Oxygen",
    "Ubuntu", "Cantarell", "Fira Sans", "Droid Sans", "Helvetica Neue",
    sans-serif;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.container {
  background: white;
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
  padding: 40px;
  max-width: 600px;
  width: 100%;
}

h1 {
  color: #333;
  margin-bottom: 30px;
  text-align: center;
}

.chat-box {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}

input {
  flex: 1;
  padding: 12px;
  border: 2px solid #ddd;
  border-radius: 8px;
  font-size: 14px;
  transition: border-color 0.3s;
}

input:focus {
  outline: none;
  border-color: #667eea;
}

button {
  padding: 12px 24px;
  background: #667eea;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-weight: bold;
  transition: background 0.3s;
}

button:hover {
  background: #5568d3;
}

button:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.response {
  background: #f0f4ff;
  padding: 15px;
  border-radius: 8px;
  border-left: 4px solid #667eea;
  margin-top: 20px;
}

.error {
  background: #ffe8e8;
  padding: 15px;
  border-radius: 8px;
  border-left: 4px solid #ff6b6b;
  margin-top: 20px;
  color: #c92a2a;
}

EOF
```

---

### Step 6.7: Install frontend dependencies and test

```bash
cd frontend
npm install
npm run dev
```

You should see:
```
  VITE v6.0.7  ready in 345 ms

  ➜  Local:   http://localhost:5173/
```

Open http://localhost:5173 in your browser. You should see the IntelliWMS interface.

Click "Send" (with the backend still running) and it should say "Backend is healthy."

---

## PHASE 7: Initialize Git & Commit (5 min)

### Step 7.1: Add and commit all files

```bash
git add .
git status  # Verify .env is NOT staged (should be gitignored)
git commit -m "Initial skeleton: backend, frontend, database, config"
```

---

### Step 7.2: Create the coordinator branch

```bash
git checkout -b feature/coordinator
git push -u origin feature/coordinator
```

---

## Verification Checklist

- [ ] `venv/` created and activated (`python --version` shows 3.12.13)
- [ ] `requirements.txt` installed (`pip show fastapi` shows 0.141.1)
- [ ] `spacy` NER model downloaded (`python -m spacy info en_core_web_sm`)
- [ ] PostgreSQL running locally (`psql -U postgres -c "SELECT 1"`)
- [ ] Database created and seeded (`psql -d intelliwms -c "SELECT COUNT(*) FROM products"` returns 3)
- [ ] Backend starts without errors (`uvicorn backend.main:app --reload`)
- [ ] Backend health check works (`curl http://localhost:8000/health` returns JSON)
- [ ] Frontend installs and runs (`npm install` in frontend/, `npm run dev` shows http://localhost:5173)
- [ ] Frontend can hit backend (`Send` button in UI returns "Backend is healthy")
- [ ] `.env` is gitignored (`git status` doesn't show `.env`)
- [ ] Code is committed to `feature/coordinator` branch

---

## What You've Built

**Backend skeleton:**
- FastAPI server running on :8000
- PostgreSQL database with User/Product/Order tables
- Centralized config (settings, LLM clients, prompts)
- Structured logging
- Health check endpoint

**Frontend skeleton:**
- React app running on :5173
- Chat UI with send button
- Axios for HTTP calls to backend
- CSS styling

**Development environment:**
- Python virtual environment with exact pinned versions
- `.env` for secrets (gitignored)
- `.gitignore` to prevent accidental commits
- Git history tracking all work

**Next step:** All 3 team members will now build the Coordinator Agent's 3 tasks (Task 1: Security, Task 2: Routing, Task 3: API Gateway) on the `feature/coordinator` branch you just created, using this skeleton as the foundation.

---

## If Something Goes Wrong

**Python: "No module named 'fastapi'"**
```bash
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

**PostgreSQL: "connection refused"**
```bash
# Start PostgreSQL (if not already running)
# Mac: brew services start postgresql
# Linux: sudo systemctl start postgresql
# Windows: Search "Services" and start PostgreSQL
```

**Frontend: "Cannot GET /api"**
Make sure backend is running on :8000 and vite.config.js has the proxy rule.

**React: "axios is not defined"**
```bash
cd frontend
npm install axios
```

---

Good luck! You've built the foundation. Now the Coordinator Agent goes on top of it.
