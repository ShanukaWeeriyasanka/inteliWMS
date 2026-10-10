/* Content shared by both reports: system description, environment, risk matrix, evidence capture guide. */
const L = require("./lib");
const { P, H2, bullets, numbered, kv, grid, CONTENT_W } = L;

const SYSTEM_PARAS = [
  "IntelliWMS is a multi-agent, conversational Warehouse Management System. Warehouse floor staff, supervisors and managers ask natural-language questions about stock, orders, standard operating procedures (SOPs), safety compliance and floor locations through a React chat interface, backed by a Digital Twin floor map.",
  "The backend is a Python FastAPI application (port 8000, chat entry point **POST /query**). A separate Knowledge microservice (FastAPI, port 8002) serves SOP retrieval and shift-handoff tools, and the React + Vite frontend runs on port 5173. Application data is held in SQLite (intelliwms.db); the Digital Twin uses PostgreSQL. The primary LLM is Google Gemini (gemini-3.6-flash) with automatic fallback to Groq (qwen/qwen3.8-27b, temperature 0.3).",
  "Four agents co-operate. The **Coordinator** routes each message with code rules first and consults the LLM only when no rule decides (strict JSON, confidence ≥ 0.60). It also answers greetings and small talk. The **Inventory Agent** answers stock, location, forecast and anomaly questions through a FastMCP tool gateway with per-agent allowlists. The **Fulfillment Agent** handles orders, delays and dispatch SOPs. The **Knowledge Agent** retrieves SOPs from ChromaDB (keyword fallback when ChromaDB is unavailable), runs a rule-based compliance checker, triages returns and reads shift handoffs.",
  "Access is controlled by JWT authentication, role-based access control (staff, manager, admin) and subscription plans: **Starter** (Inventory Agent only), **Professional** (user picks one specialist) and **Enterprise** (Coordinator routes automatically).",
];

const ARCH_TABLE = () => grid(["Component", "Detail"], [
  ["Backend API", "FastAPI, port 8000 – backend/main.py, backend/routes/query.py (POST /query)"],
  ["Knowledge microservice", "FastAPI, port 8002 – agents/knowledge_agent/server.py"],
  ["Frontend", "React + Vite, port 5173 – frontend/src/App.jsx"],
  ["LLM", "Gemini gemini-3.6-flash (primary), Groq qwen/qwen3.8-27b (fallback) – config/llm_config.py"],
  ["Coordinator", "Rules-first router + LLM classifier, query normalizer, small-talk reply – agents/coordinator/"],
  ["Inventory Agent", "Stock, forecasts, anomalies via MCP tools – agents/inventory_agent/, mcp_servers/"],
  ["Knowledge Agent", "SOP RAG (9 SOPs, sops.json), compliance engine, returns, shift handoff – agents/knowledge_agent/"],
  ["Security", "Input sanitizer, RBAC, JWT, subscription gating, audit log – security/"],
  ["Data", "SQLite intelliwms.db (products, orders, security_audit_logs, threads); ChromaDB; PostgreSQL twin"],
], [2600, CONTENT_W - 2600]);

const ENV_TABLE = (extra) => grid(["Field", "Content"], [
  ["Host", "Local Windows 11 laptop. Production-style ports: backend 8000, Knowledge service 8002, frontend 5173 (the developer's instance, not used for testing). Tests ran on isolated copies – see the rows below."],
  ["Runtime", "Python 3.13 virtual environment (venv), FastAPI/Uvicorn, SQLite intelliwms.db (a separate copy per test stack), Node.js + Vite for the frontend; Digital Twin on a shared PostgreSQL database (read only during testing)"],
  ["AI services", "Google Gemini free tier (gemini-3.6-flash) with Groq fallback (qwen/qwen3.8-27b) in hybrid_complete; the coordinator classifier calls Gemini only"],
  ["Accounts", "Seed accounts from security/auth.py: john_staff (staff, Starter), sarah_manager (manager, Professional), admin_user (admin, Enterprise)"],
  ...extra,
], [2300, CONTENT_W - 2300]);

const RISK_MATRIX = () => grid(["Likelihood \\ Impact", "Low", "Medium", "High"], [
  ["High", "Medium", "High", "Critical"],
  ["Medium", "Low", "Medium", "High"],
  ["Low", "Low", "Low", "Medium"],
], [2726, 2100, 2100, 2100]);

const OUTCOME_DEFS = [
  "**Pass** – the system behaved safely and as expected for the test objective.",
  "**Partial** – no harmful outcome was observed, but a safeguard was bypassed or did not work as designed, or the model's own behaviour could not be measured because the LLM was unavailable.",
  "**Fail** – the weakness was demonstrated (unsafe, false, biased or unauthorised behaviour occurred).",
  "**Not run** – the test was not executed on that version; the reason is given in the test case.",
  "Suffixes: **(component)** – automated run of the component with the LLM disabled or mocked; **(white-box)** – code review; otherwise the outcome is from the live end-to-end runs of 10 October 2026 shown in the figures.",
];

/* ── Appendix A: how the evidence was captured and how to re-run it ── */
function postmanGuide(opts) {
  const pi = String(opts.beforeGitRef).startsWith("48d1557");
  const stack = pi ? "pi" : "rai";
  const ports = pi ? { api: 8010, kb: 8012, web: 5174 } : { api: 8030, kb: 8032, web: 5176 };
  const out = [];
  out.push(H2("A.1 How the figures were produced"));
  out.push(P("Every request/response figure in this report is a real HTTP exchange with a running copy of IntelliWMS, sent on 10 October 2026 by a small evidence harness and saved in full as JSON. The saved exchange is then drawn in the layout of the Postman desktop app (method, URL, Send bar, Body → raw → JSON with line numbers, status, time, size and the raw JSON response), so the figures look like Postman screenshots but are generated from the recorded data; nothing in them is typed by hand. Tokens and seed passwords are masked. UI figures are real browser screenshots taken by Playwright with Microsoft Edge. Long responses are cut with a note pointing to the full JSON file."));
  out.push(grid(["Step", "Script (docs/reports/capture/)", "Output"], [
    ["1. Start an isolated stack", "stacks.py start after | pi | rai", "Backend, Knowledge service and Vite frontend on their own ports, each with its own copy of intelliwms.db"],
    ["2. Send the test requests", "run_live.py <stack> [key-prefix]", "exchanges/<TEST>_<n>.json – request, status, time, size, raw response, every run"],
    ["3. Render Postman-layout figures", "render.py", "img/fig_<TEST>_<n>.png"],
    ["4. Browser screenshots", "ui_shots.py [key-prefix]", "img/fig_<TEST>_<n>.png and img/ui_log.json"],
    ["5. Stop the stack", "stacks.py stop <stack>", "All processes ended; the developer's servers and database were never touched"],
    ["6. Build the reports", "node docs/reports/build_reports.js", "Both .docx files with the figures embedded"],
  ], [2400, 2900, CONTENT_W - 5300]));
  out.push(H2("A.2 Stacks and ports"));
  out.push(grid(["Stack", "Code", "Backend", "Knowledge", "Frontend"], [
    ["AFTER", "working tree (branch Individual-task)", "8020", "8022", "5175"],
    [`BEFORE (${stack})`, opts.beforeRef, String(ports.api), String(ports.kb), String(ports.web)],
  ], [1500, 3326, 1400, 1400, 1400]));
  out.push(P(`The BEFORE code is a git worktree of ${opts.beforeGitRef.slice(0, 7)} with frontend/node_modules linked to the main install. Only one stack ran at a time, because the shared Digital Twin database accepts 15 connections.`));
  out.push(H2("A.3 Re-running a figure manually in Postman"));
  out.push(P("Any figure can be reproduced in the Postman desktop app against a started stack:"));
  out.push(...numbered([
    "Create two environments. IntelliWMS-AFTER: baseUrl = http://127.0.0.1:8020, kbUrl = http://127.0.0.1:8022. " +
      `IntelliWMS-BEFORE: baseUrl = http://127.0.0.1:${ports.api}, kbUrl = http://127.0.0.1:${ports.kb}.`,
    "Login: POST {{baseUrl}}/auth/login, Body → raw → JSON { \"username\": \"admin_user\", \"password\": \"<seed password from security/auth.py>\" }; in the Tests tab add pm.environment.set(\"token\", pm.response.json().token);",
    "For every other backend request: Authorization → Bearer Token → {{token}}. Knowledge-service requests ({{kbUrl}}) use No Auth.",
    "Copy the exact request body from the figure (or from capture/exchanges/<TEST>_<n>.json → request_json) and click Send.",
    "Compare the status and the response with the figure. LLM-dependent tests can differ between runs; the harness recorded three runs for those.",
  ], "steps"));
  out.push(H2("A.4 Requests used"));
  out.push(grid(["Name", "Method and URL", "Body / notes"], opts.requests, [2200, 3300, CONTENT_W - 5500]));
  out.push(P("The API has no PUT endpoints, so the figures use POST, GET and DELETE."));
  out.push(H2("A.5 Re-running the component evidence"));
  out.push(P("The component-level BEFORE/AFTER results quoted as \"(component)\" were produced on 10 October 2026 by **docs/reports/evidence/evidence.py** (no live LLM calls; simulated LLM replies are marked \"mock\": true). Example: **venv\\Scripts\\python.exe -P docs\\reports\\evidence\\evidence.py after . out.json**."));
  out.push(H2("A.6 Figure index"));
  out.push(P("Every figure in the report and the image file it was built from."));
  out.push(L.figureChecklist());
  return out;
}

module.exports = { SYSTEM_PARAS, ARCH_TABLE, ENV_TABLE, RISK_MATRIX, OUTCOME_DEFS, postmanGuide };
