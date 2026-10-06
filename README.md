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
---

## 🗺️ Warehouse Digital Twin (map behind the chat)

When the **Inventory Agent** answers a "where is / how do I get to / how many / what's low"
question, the background behind the chat turns into a live floor plan: the target rack is
highlighted, the walking route plays floor by floor (lift or stairs), and a small card beside
the conversation shows the exact shelf and bin. The chat itself stays exactly where it is.
Any other kind of question brings the normal background back (or press Esc / ✕ on the map).

| Piece | Where |
|---|---|
| Schema, demo data, command contract | `database/twin/` (`schema.sql`, `seed.sql`, `ui_command.schema.json`, `realtime.sql`) |
| Data access (views + SQL functions only) | `database/twin/repository.py` |
| Question → map command | `agents/inventory_agent/twin_navigator.py` |
| REST + live updates (SSE) | `backend/twin/` → `GET /twin/*`, `GET /twin/stream` |
| React map | `frontend/src/twin/` |

- **Needs PostgreSQL.** In Docker it uses the `postgres` service automatically; the backend
  creates and seeds the `twin` schema on first start. Locally, set `TWIN_DATABASE_URL` to a
  PostgreSQL database. With SQLite only, the map stays off and the classic SKU answers are used.
- **Reset the demo warehouse:** `python scripts/setup_twin.py --reset`
- **Accuracy:** the agent sends IDs only; the map fetches every quantity, label and route from
  the database (`find_route` / `get_directions`), so the line on the map and the written
  directions always come from the same calculation.
- **Live:** stock moves, new alerts, closed aisles/lifts and agent commands arrive via
  PostgreSQL `NOTIFY` → Server-Sent Events. A blocked lift re-routes the shown route via the stairs.
- **Tests:** `npm test` (frontend) and `pytest tests/test_twin.py`; set `TWIN_TEST_DATABASE_URL`
  to a **throwaway** PostgreSQL to also run the acceptance scenarios (they rebuild the schema).
