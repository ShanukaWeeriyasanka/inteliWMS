# Inventory collection query consistency

The screenshot's saved requests were `products that have equal number of units`
and `products that have eqal number of units`. The typo missed collection parsing.
The coordinator context fallback still routed to inventory, where the individual
product handler asked for a SKU. Both now resolve to the same validated collection
plan and `query_inventory` tool, independently of previous product IDs.

## Execution and comparison

Relation and measure parsing runs first, including equal/same/identical phrasing
and bounded spelling corrections. Unfamiliar collection wording can use one
structured language interpretation when an LLM key is configured. Code validates
JSON, confidence, operation and status, binds the allowlisted report tool and
executes its fixed flow. The interpreter cannot supply SQL, tools, quantities,
IDs or scope. Invalid interpretations ask which collection comparison is intended.

Scope precedence is explicit warehouse/floor, manually selected map floor sent
as `inventory_scope`, then stored thread scope. The default is all warehouses,
including unassigned stock. `all warehouses` explicitly clears selected scope.
Automatic map focus does not silently change the next query's scope.

Each product contributes once. Scoped balances sum the authoritative per-bin
view, where lots have already been aggregated; reservations are separate fields.
Exact numeric comparisons use normalized unit labels without conversions or
rounding. Only groups with at least two distinct products are returned; result
limits preserve complete groups. Confirmed zero groups have separate labels.
Missing stock records or comparable quantities/units are excluded and disclosed,
never inferred as zero. Missing records may prevent a complete comparison.

Group tables contain product ID, product name, quantity, unit and warehouse/floor
locations. General stock wording uses on-hand; explicit available, reserved or
quarantined wording selects that measure. Source update timestamps and the oldest
included record are separate from query/snapshot time. Optional
`INVENTORY_STOCK_MAX_AGE_SECONDS` defines an age policy for marking balances stale.
Default `0` shows timestamps without asserting that physical stock is current.

Intent, scope, handler, tool, result count, duration and errors use existing
correlated logging. Thread context stores scope and keeps the same thread ID.
No schema migration or production stock write is required for this change.

## Run and verify

From the repository root, start/restart the backend:

```powershell
.\venv\Scripts\python.exe -m uvicorn backend.main:app --reload --port 8000 --timeout-graceful-shutdown 3
```

Restart a separately hosted inventory MCP server if configured. In another terminal:

```powershell
cd frontend
npm run dev
```

Ask these in the same conversation:

1. `products that have equal number of units` twice.
2. `products that have eqal number of units`.
3. `items with the same stock quantity`.
4. `products with equal available units in WH1-F2`.
5. Repeat without the floor to check stored scope.
6. `products with equal units in all warehouses` to clear scope.

The active Supabase catalog has no equal on-hand groups, so a no-match answer is
expected. Bin-scoped results require verified assignments, currently absent for
the active imported catalog. Tool failure and missing stock data have separate
outcomes and do not trigger SKU questions.

## Files changed for this fix

| Area | Files |
| --- | --- |
| Query understanding and execution | `agents/inventory_agent/report_queries.py`, `agent.py`, `tools.py` |
| Inventory contracts and configuration | `agents/inventory_agent/tool_contracts.py`, `schemas.py`, `config.py`, `.env.example` |
| Source flags and actual stock timestamps | `database/twin/repository.py` |
| Scope handoff and persistence | `agents/coordinator/context_builder.py`, `agent_dispatcher.py`, `backend/routes/query.py`, `backend/threads/schemas.py` |
| Inventory MCP contract and missing-data status | `mcp_servers/inventory_mcp_server.py`, `mcp_tool_client.py` |
| Selected scope sent by UI | `frontend/src/App.jsx`, `services/api.js`, `twin/WarehouseTwin.jsx` |
| Inventory-only table rendering | `frontend/src/chat/markdown.js`, `markdown.test.js`, `components/coordinator UI/MarkdownText.jsx`, `ChatMessage.jsx`, `twin/components/AgentDock.jsx`, `twin/twin.css` |
| Tests | `tests/test_inventory_reports.py`, `test_query_threads.py`, `test_inventory_authority.py` |

## Verification

- Full backend suite: 510 passed, 28 opt-in skipped.
- Final focused report, MCP, edge-case and thread suite: 157 passed.
- PostgreSQL: 11 existing cases passed; the new equality/lot/missing-data case
  passed on rerun after correcting its fixture and missing-data expectation.
- Frontend: 83 tests passed; production build passed with existing warnings.
- Real Supabase MCP reads: repeated question, saved typo, paraphrases and available
  comparisons selected the report handler consistently and returned no matches.

Tests cover equal/different quantities, different units, multiple bins/lots,
warehouse/floor scope, exact decimals, zero groups, missing data, configured
staleness, transport/tool failures, repeated API requests and structured-plan
validation. Table rendering and HTML escaping were verified by static React
render tests. Tables are enabled only for inventory chat and the inventory map
dock; other agents retain their existing text rendering. Provider interpretation
used controlled test responses; live provider interpretation and interactive
browser layout remain unverified.
