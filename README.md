# IntelliWMS — Agentic Warehouse Management System

IntelliWMS is an intelligent, multi-agent warehouse management platform featuring a **Coordinator Agent** (API Gateway, Security, Intent Classification), **Inventory Specialist Agent** (Stock prediction, anomaly detection, automated reordering), and **Knowledge Agent** (RAG SOP retrieval).

---

## 🚀 Running for Teammates (Docker — Recommended)

The quickest way for anyone on the team to get IntelliWMS up and running with all databases, agents, and frontend pre-configured:

```bash
# 1. Copy environment template
cp .env.example .env

# 2. Add your GEMINI_API_KEY in .env

# 3. Launch the full stack
docker compose up --build
```

- **Frontend App**: [http://localhost:3000](http://localhost:3000)
- **Backend API & Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Detailed Guide**: See [DOCKER_GUIDE.md](DOCKER_GUIDE.md)

---

## 💻 Running Locally (Manual Development)

If developing without Docker:
- See [HOW_TO_RUN.md](HOW_TO_RUN.md) for step-by-step local terminal setup.
- Backend runs at `http://localhost:8000`
- Frontend runs at `http://localhost:5173`