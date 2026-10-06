# 🚀 How to Run IntelliWMS (Full Stack)

> **Use PowerShell** for everything. Not CMD.  
> Open it from VS Code: `Ctrl + Shift + `` ` (backtick)

Project folder on this machine:

```
C:\Users\rxrat\Documents\Sliit\Y3S2\IRWA\inteliWMS
```

---

## ⚠️ One-Time Setup (Do This First, Ever)

Open **PowerShell** and run this **once** on your machine to allow scripts to run:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force
```

You only ever need to do this once. After this, everything works normally.

---

## 📦 After Pulling New Changes (Install Dependencies)

`venv\` and `frontend\node_modules\` already exist. Run this again whenever
`requirements.txt` or `frontend\package.json` changes:

```powershell
cd C:\Users\rxrat\Documents\Sliit\Y3S2\IRWA\inteliWMS

.\venv\Scripts\python.exe -m pip install -r requirements.txt

cd frontend
npm install
```

Also make sure `GEMINI_API_KEY` is set in `.env` (in the project folder).

---

## 🖥️ Step-by-Step: Open 3 Terminals

In VS Code press **`Ctrl + Shift + `` `** to open a terminal.  
Click the **`+`** button in the terminal panel to open more tabs.  
You need **3 tabs open at the same time** (4 if you want the digital-twin map, see Optional step below).

---

## Terminal 1 — Backend API (Port 8000)

```powershell
cd C:\Users\rxrat\Documents\Sliit\Y3S2\IRWA\inteliWMS

.\venv\Scripts\python.exe -m uvicorn backend.main:app --reload --port 8000 --timeout-graceful-shutdown 3
```

✅ It's working when you see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

> Keep `--timeout-graceful-shutdown 3`. The warehouse map keeps a live connection open, and without
> this limit every auto-reload (after a code change) waits for that connection forever. The backend
> then stops answering, and login hangs on "Authenticating...".

📄 Swagger API docs → http://localhost:8000/docs

---

## Terminal 2 — Knowledge Agent (Port 8002)

```powershell
cd C:\Users\rxrat\Documents\Sliit\Y3S2\IRWA\inteliWMS

.\venv\Scripts\python.exe -m uvicorn agents.knowledge_agent.server:app --reload --port 8002
```

✅ It's working when you see:
```
INFO:     Uvicorn running on http://127.0.0.1:8002
INFO:     Application startup complete.
```

📄 Knowledge Agent docs → http://localhost:8002/docs

---

## Terminal 3 — Frontend (Port 5173)

```powershell
cd C:\Users\rxrat\Documents\Sliit\Y3S2\IRWA\inteliWMS\frontend

npm run dev
```

✅ It's working when you see:
```
  VITE v6.x.x  ready in 600ms
  ➜  Local:   http://localhost:5173/
```

🌐 Open your browser → **http://localhost:5173**

---

## 🗺️ Optional — Warehouse Digital Twin Map (PostgreSQL)

The live floor-plan map behind the chat needs PostgreSQL. With only SQLite
(the default in `.env`), the app still works, but the map stays off.

> ℹ️ This machine already has **PostgreSQL installed on Windows**, listening on port 5432.
> Use that one (Option A). Docker's Postgres (Option B) wants the same port 5432 and will clash.

### Option A — Use your installed PostgreSQL (recommended here)

**1.** Open **pgAdmin** (or `psql`) as the `postgres` superuser and create a database:

```sql
CREATE DATABASE intelliwms;
```

**2. Add this line to `.env`** (one time), using your own `postgres` password:

```
TWIN_DATABASE_URL=postgresql://postgres:YOUR_POSTGRES_PASSWORD@localhost:5432/intelliwms
```

**3. Restart Terminal 1 (Backend).** It creates and seeds the `twin` schema on first start.

### Option B — Docker Postgres (only if you stop the local PostgreSQL first)

```powershell
# Stop the Windows PostgreSQL service first (run PowerShell as Administrator)
Get-Service postgresql* | Stop-Service

# Start Docker Desktop, then:
cd C:\Users\rxrat\Documents\Sliit\Y3S2\IRWA\inteliWMS
docker compose up -d postgres
```

Then add to `.env`:

```
TWIN_DATABASE_URL=postgresql://intelliwms_user:intelliwms_pass@localhost:5432/intelliwms
```

and restart Terminal 1.

To reset the demo warehouse later:

```powershell
.\venv\Scripts\python.exe scripts\setup_twin.py --reset
```

To stop Postgres: `docker compose stop postgres`

---

## 🧭 Summary — What Runs Where

| Terminal | Command location | URL |
|---|---|---|
| 1 — Backend API | `inteliWMS\` | http://localhost:8000 |
| 2 — Knowledge Agent | `inteliWMS\` | http://localhost:8002 |
| 3 — Frontend | `inteliWMS\frontend\` | http://localhost:5173 |
| (optional) Postgres | Windows service (or Docker) | localhost:5432 |

> The frontend **automatically** talks to the backend at port 8000.  
> You only ever open **http://localhost:5173** in your browser.

---

## 📦 Inventory MCP Server, Conversations & Monitoring

**Inventory tools run on an MCP server.** The inventory agent reaches them through a gateway that only lets each agent use its own allowlisted tools.

**MCP transports:**
- **Default:** `INVENTORY_MCP_TRANSPORT=memory`. The MCP server runs inside the backend (same MCP protocol, no extra process), so nothing more is needed.
- **Optional standalone server (Terminal 4):**

  ```powershell
  cd C:\Users\rxrat\Documents\Sliit\Y3S2\IRWA\inteliWMS
  $env:INVENTORY_MCP_TOKEN = "pick-a-long-random-token"
  .\venv\Scripts\python.exe -m mcp_servers.inventory_mcp_server --transport streamable-http --port 8003
  ```

  Then put this in `.env` and restart Terminal 1:

  ```
  INVENTORY_MCP_TRANSPORT=streamable_http
  INVENTORY_MCP_URL=http://127.0.0.1:8003/mcp
  INVENTORY_MCP_TOKEN=pick-a-long-random-token
  ```

  Docker: `docker compose --profile mcp-http up -d inventory-mcp`, with `INVENTORY_MCP_URL=http://inventory-mcp:8003/mcp`.

**Checking the MCP setup:** http://localhost:8000/health has an `inventory_mcp` block. If the configuration is wrong, its `problems` list says exactly what is missing (for example `INVENTORY_MCP_TOKEN is required when INVENTORY_MCP_TRANSPORT=streamable_http`). Secrets are never shown.

**Conversations:**
- Each chat is saved as a thread for the signed-in user.
- **URLs:**
  - `/` is a new chat; its thread is created with the first answer.
  - `/chat/<thread-id>` opens a saved one.
  - `?view=map` means the warehouse map is open.
- Refreshing the page and using browser Back/Forward keep you on the same conversation.

**Logs, traces and metrics:**
- **Logs:** `logs/app.log` holds JSON lines.
- **IDs on every request:** each response carries an `X-Request-ID` and `X-Trace-ID`, and every log line includes `request_id`, `trace_id`, `thread_id` and `agent`.
- **Spans:** recorded as `SPAN_END` events.
- **Metrics:** Prometheus text at http://localhost:8000/metrics. Set `METRICS_TOKEN` to protect them.
- **Message text in logs:** omitted unless `LOG_INCLUDE_CONTENT=true`.
- **Per-logger levels:** set with `LOG_LEVELS` (e.g. `mcp=WARNING`).

**How decisions are made (rules first, LLM last):**
1. **Code rules** decide whenever they can. Each rule has an id:
   - Conversation:
     - `meta.greeting`, `meta.capability`, `meta.help`, `meta.weak`
     - `social.ack`, `social.bye`
   - Follow-ups in a conversation:
     - `context.clarification_reply`, `context.inventory_follow_up`
   - Domains (strongest first):
     - `knowledge.strong`, `fulfillment.strong`, `inventory.strong`
     - `*.keywords`
     - `inventory.twin_entity`
   - Security: `security.prompt_injection`
   - Inside the inventory agent:
     - `sub_intent.*` (which kind of inventory question)
     - `product_ref.*` (how the product was identified)
     - `twin.*` (whether the warehouse map's answer was used)
2. **The LLM** is consulted only when no rule decides:
   - It rewrites broken text, and the rewrite is rejected if it adds an ID the user didn't type.
   - It suggests a domain, which is accepted only as valid JSON with confidence ≥ 0.6.
   - It words replies to unrecognised small talk.
   - Every call has a timeout (`LLM_TIMEOUT_S`).
3. **Fallbacks** apply when the LLM is unusable (invalid, low confidence, timeout or no key):
   - If a weak rule matched, it decides (e.g. `inventory.twin_hint` for "where is …" wording).
   - Otherwise the user is asked a fixed clarification question (`clarify.domain`).

**Where to see every decision:**
- **In each `/query` response:** `routing.rule_id`, `routing.decided_by` (`rule` / `llm` / `fallback`), `routing.llm_status`, and `routing.decisions`. The decisions list shows the full path: route, normalize, reply, and the inventory sub-intent / product / twin.
- **In `logs/app.log`:** `DECISION` and `LLM_CALL` lines. These never contain message text.
- **In `/metrics`:** `decisions_total{stage,decided_by,rule}`, `llm_calls_total{purpose,outcome}` and `llm_call_duration_seconds`.

---

## 🧪 Running Tests

```powershell
cd C:\Users\rxrat\Documents\Sliit\Y3S2\IRWA\inteliWMS
.\venv\Scripts\python.exe -m pytest

cd frontend
npm test
```

**Test types:**

| Type | Files | What it uses |
|---|---|---|
| Unit (mocks/fakes) | `test_routing_inventory.py`, parts of `test_mcp_gateway.py`, `test_observability.py` | No MCP session, no network |
| In-memory MCP | `test_inventory_agent_mcp.py`, `test_query_threads.py`, `test_mcp_gateway.py` | The real MCP protocol (server + client) in one process, over a throwaway seeded database |
| **Live MCP** | `test_inventory_mcp_live.py` | Starts the MCP server as a separate process over HTTP with token auth. **Skipped unless enabled** |

Run the live MCP tests:

```powershell
$env:RUN_LIVE_MCP = "1"; .\venv\Scripts\python.exe -m pytest tests/test_inventory_mcp_live.py; Remove-Item Env:RUN_LIVE_MCP
```

Chat threads written by tests go to a temporary database, never `intelliwms.db`.

**Manual browser checks (after `npm run dev`):**
1. Ask "how many wireless barcode scanners are on hand?", then "and where is it?". Both answers stay in one conversation, and the URL becomes `/chat/<id>`.
2. Refresh the page. The same conversation and its messages come back.
3. Start a **New query**, ask something else, then use browser **Back**. You return to the first conversation.
4. Use **Forward**, and click conversations in the sidebar. Each one loads its own messages.
5. Ask "where is the coconut milk" with the twin map enabled. The map opens and the URL gets `?view=map`; browser Back closes the map.
6. Open `/chat/not-a-real-id`. A notice appears and a new chat starts.
7. Log out and log in as another user. No previous chat is visible.

---

## ❌ Common Errors & Fixes

### `cannot be loaded because running scripts is disabled`
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force
```
Then re-run your command.

---

### `ModuleNotFoundError: No module named 'fastapi'` (or any other module)
You ran `python` instead of the venv python, or dependencies are out of date.  
Always use:
```powershell
.\venv\Scripts\python.exe -m uvicorn ...
```
**Not** `python -m uvicorn ...`

If it still fails, re-run `.\venv\Scripts\python.exe -m pip install -r requirements.txt`.

---

### `Port 8000 already in use`
```powershell
# Find the process using the port
netstat -ano | findstr :8000

# Kill it (replace 12345 with the PID number you see)
taskkill /PID 12345 /F
```

> ⚠️ Don't run `docker compose up` (full stack) at the same time as the manual
> terminals: the Docker backend also uses port 8000 and will clash with Terminal 1.

---

### `localhost refused to connect` (ERR_CONNECTION_REFUSED) in the browser
The server for that URL isn't running. Check which ones are up:
```powershell
netstat -ano | findstr "LISTENING" | findstr ":8000 :8002 :5173"
```
- No `:5173` → start **Terminal 3** (frontend) — that's the page you open.
- No `:8000` → start **Terminal 1** (backend).
- Look in that terminal for a red error and fix it before retrying.

---

### Login says `Network Error` + console shows `blocked by CORS policy` / `405 Not Allowed (nginx)`
**Terminal 1 (backend) is not running**, so the request lands on another program that also
uses port 8000. On this machine that's the `jitsi-feature4-web-1` Docker container (nginx).
Check: `curl.exe -s http://127.0.0.1:8000/health` must return `IntelliWMS API Gateway...`,
not an HTML page.
Fix:
1. Start **Terminal 1**. Once uvicorn is up it wins `127.0.0.1:8000` over the container.
2. `frontend\.env.local` must contain `VITE_API_BASE_URL=http://127.0.0.1:8000` (not `localhost`).
   After changing it, restart Terminal 3 (`Ctrl + C`, `npm run dev`).
3. Hard-refresh the browser (`Ctrl + Shift + R`).

Or stop the other container while you work on this project: `docker stop jitsi-feature4-web-1`.

---

### Login says `POST http://127.0.0.1:8000/auth/login 404 (Not Found)`
Port 8000 is answered by the **Knowledge Agent** instead of the backend. Its `/health` shows
`"service":"knowledge_agent"`. This happens when Terminal 2 was started with `--port 8000`.
Fix:
1. In the Knowledge Agent terminal press `Ctrl + C` and start it on **8002**:
   ```powershell
   .\venv\Scripts\python.exe -m uvicorn agents.knowledge_agent.server:app --reload --port 8002
   ```
2. In Terminal 1 start the backend on **8000** (command above).
3. Check: `curl.exe -s http://127.0.0.1:8000/health` must print `"IntelliWMS API Gateway is running smoothly"`.

If `docker ps` lists `intelliwms_backend` (an older Docker build of the backend, on port 8002), stop it while
you use the manual terminals: `docker stop intelliwms_backend`.

---

### Login hangs on "Authenticating..." after editing code
The backend was started **without** `--timeout-graceful-shutdown 3`. After a code change, `--reload`
waits for the browser's live map connection (`/twin/stream`) to close, which never happens. Port 8000
stays open but nothing answers (`curl.exe -s -m 5 http://127.0.0.1:8000/health` prints nothing).
Fix: press `Ctrl + C` in Terminal 1 (close the terminal if it doesn't stop) and start the backend
with the Terminal 1 command above, which includes `--timeout-graceful-shutdown 3`.

---

### `no such column: users.is_active` (or any `no such column` error)
Your `intelliwms.db` was created by older code. `init_db()` never adds new columns to
existing tables, so rebuild it (the old file is kept as a backup):
```powershell
cd C:\Users\rxrat\Documents\Sliit\Y3S2\IRWA\inteliWMS
# stop Terminal 1 and 2 first (Ctrl + C)
Rename-Item intelliwms.db intelliwms.db.bak -Force
.\venv\Scripts\python.exe scripts\seed_database.py
```
This resets the demo data (users, products, orders).

---

### `npm error enoent Could not read package.json`
You ran `npm` in the project root. The frontend lives in the `frontend` folder:
```powershell
cd C:\Users\rxrat\Documents\Sliit\Y3S2\IRWA\inteliWMS\frontend
npm run dev
```
Your prompt should end in `...\inteliWMS\frontend>` before you run any `npm` command.

---

### `npm : cannot be loaded` (script disabled)
Run the one-time fix at the top of this file, then try `npm run dev` again.

---

### Map doesn't appear
- Is PostgreSQL running? (`netstat -ano | findstr :5432` should show `LISTENING`)
- Is `TWIN_DATABASE_URL` in `.env` with the right user/password, and did you restart the backend after adding it?

---

## 🛑 To Stop Everything

Go to each terminal and press **`Ctrl + C`**.  
If you used Docker Postgres (Option B): `docker compose stop postgres`
