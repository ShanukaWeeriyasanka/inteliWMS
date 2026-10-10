# Inventory questions and schema integration

Latest repeated-question and scope behavior is documented in [INVENTORY_QUERY_FIX.md](INVENTORY_QUERY_FIX.md).

Inventory reads the Supabase `twin` schema through the allowlisted MCP tools.
Product cards, details, placements, rankings and stock alerts use those balances.
Catalog reports are parsed and calculated in code. They do not generate SQL or
ask an LLM to select a workflow.

| Question | Behavior |
|---|---|
| `lowest stock` / `which product has the lowest stocks?` | Lowest on-hand quantity, including zeros and tied products |
| `highest stock` | Highest on-hand quantity, including ties |
| `top 3 products by stock` | Three products ordered by on-hand quantity |
| `lowest available stock` | Rank by available quantity, separately from reserved/quarantined |
| `lowest reserved stock` | Rank by reserved quantity, including zero commitments |
| `inventory summary` | Distinct product count and quantity breakdown, separated by unit of measure |
| `how many products do we have?` | Count active product records, including zero-stock products |
| `list all products` | Current catalog with quantities, locations, source and timestamps |
| `list low stock products` | Products at/below reorder point; same stock conditions as the alerts panel |
| `list out of stock products` | Products with zero on-hand quantity |
| `show reserved stock` | Products with reservations |
| `which products are quarantined?` | Products with quarantined quantities |
| `show unassigned inventory` | Positive inventory still awaiting bin assignment |
| `list products in category Electronics` | Category filter against stored category names |
| `total stock by category` / `total stock by floor` / `total stock by warehouse` | Grouped balances; units kept separate |
| `lowest stock in WH1-F2` | Quantity at that location only, with scoped map highlighting |
| `lowest stock in warehouse 1` | Assigned quantity in that warehouse; no invented warehouse for unplaced balances |
| `how many SKU-3300 are on hand?` | Specific product lookup; zero is a valid answer |
| `where is PRD-00013?` / `where is the scanner?` | Existing product/alias resolution; reports unassigned until actual bins are confirmed |
| `how many products are in rack 2?` | Existing map workflow; repeated rack names require a location choice |
| `stock movements for SKU-4521` | Existing recorded movement history |
| `when will SKU-9012 run out?` | Existing forecast, with missing/default policy inputs disclosed |

Existing document parsing, equipment triage, anomaly checks, transfer advice,
directions, rack fill, ambiguous-name selection and chat follow-ups are preserved.
Historical anomaly checks use the supplied PostgreSQL application's transaction ledger;
current product and placement balances are the authoritative twin records.
Sibling-warehouse transfer figures remain labelled local snapshots.

## Completed cloud migration

Supabase already had six application products, including `SKU-3300`, which was
absent from the SQLite application's five-product catalog. The additive mapping
migration now keys legacy records by `(source_system, application_product_id)`.
Two different legacy IDs can map to one stable product ID without summing balances.

| SKU | SQLite ID | Supabase public ID | Authoritative product ID |
|---|---:|---:|---|
| SKU-4521 | 1 | 24 | PRD-00013 |
| SKU-7788 | 2 | 25 | PRD-00014 |
| SKU-9012 | 3 | 26 | PRD-00015 |
| SKU-1088 | 4 | 27 | PRD-00016 |
| SKU-2045 | 5 | 28 | PRD-00017 |
| SKU-3300 | absent | 29 | PRD-00018 |

Existing PRD-00001–PRD-00012 and 24 physical placements remain unchanged.
This import initially produced 18 products and 8 stock alerts. The subsequent
Supabase catalog selection archives the twelve map demo products, leaving
**6 active products and 3 visible stock alerts**. The actual lowest-stock
query now returns SKU-3300 at zero. Existing balances were retained
for overlapping SKUs. Original rows in SQLite and Supabase `public` remain intact.
Snapshots archive their legacy metadata. Imported stock is unassigned until
someone confirms its physical bin; demo stock remains labelled demo.

The active catalog is exclusively the six SKUs in Supabase `public.products`.
No inventory query reads the local SQLite catalog. Inventory history sessions,
standalone forecasts, transfer advice and legacy location helpers now connect
to the configured PostgreSQL database. Archived demo quantities are excluded
from placements, rack fill, active product resolution, alerts and capacity checks.
All 18 twin product records and 24 archived physical placement records remain
stored; none were deleted. Current active products have no verified bin placements.

Catalog-selection backup: `logs/inventory_backups/20261009T102702880955.dump`.

```powershell
.\venv\Scripts\python.exe scripts/select_inventory_catalog.py
.\venv\Scripts\python.exe scripts/select_inventory_catalog.py --apply --pg-dump 'C:\Program Files\PostgreSQL\18\bin\pg_dump.exe'
```

The first command previews the PostgreSQL catalog and unrelated records to archive.
The second backs up first, imports/maps PostgreSQL records only, and activates that
catalog. It never reads SQLite products. Restarting the backend does not reactivate
archived demo records. Repeat this command when adding products to `public.products`;
authoritative quantity changes belong in the twin stock-placement API.

Backup before the final migration:
`logs/inventory_backups/20261009T100620052222.dump` (ignored by Git).

That earlier backup records the initial legacy import. For the current PostgreSQL-only
inventory catalog, use `select_inventory_catalog.py` above. The legacy SQLite importer
is retained for compatibility with other installations, rather than used for this catalog.

## Run and verify

Restart the backend and any standalone MCP process after pulling these changes
or editing `.env`; an already running process may still have the previous code
or connection settings. Keep Supabase's session pooler on port 5432 with SSL.

```powershell
.\venv\Scripts\python.exe -m uvicorn backend.main:app --reload --port 8000 --timeout-graceful-shutdown 3
```

In the frontend terminal, run `npm run dev`, reload the browser, then try the
questions in the table. `lowest stock` must return SKU-3300 at zero,
and `list low stock products` must agree with the alerts panel. Alert cards now
show provenance, stock update times and unassigned quantities. The panel labels
products and alerts as covering all warehouses; racks remain floor-specific.

Automated verification on a separately seeded, disposable SQLite database:

```powershell
$env:DATABASE_URL='sqlite:///./inventory-regression.db'
$env:TWIN_DATABASE_URL='disabled'
.\venv\Scripts\python.exe scripts/seed_database.py
.\venv\Scripts\python.exe -m pytest tests -q
Remove-Item Env:DATABASE_URL
Remove-Item Env:TWIN_DATABASE_URL
```

Only use this seeder on the disposable path: it replaces seeded application
records. The non-PostgreSQL `disabled` value prevents `.env` from activating the
cloud twin for the legacy regression suite.

PostgreSQL tests create and drop only random `invtest_...` schemas:

```powershell
$env:DATABASE_URL='sqlite:///./inventory-verification.db'
$env:RUN_INVENTORY_PG_TESTS='1'
.\venv\Scripts\python.exe -m pytest tests/test_inventory_authority.py -q
Remove-Item Env:DATABASE_URL
Remove-Item Env:RUN_INVENTORY_PG_TESTS
```

Verified: 468 backend regressions passed, 28 opt-in tests skipped; 11 PostgreSQL
acceptance tests passed separately on Supabase, including catalog archival without
deleting data and repeated startup preserving that selection. Real cloud MCP queries
verified rankings, summaries, counts, low stock, reservations, category groups,
floor-scoped stock and the missing product. Frontend results are recorded in
INVENTORY_IMPLEMENTATION.md. Interactive browser QA remains unverified.

## Equal quantities and numeric stock filters

The following questions now use the live inventory MCP query, without needing a
selected product or borrowing one from chat history:

- `which products have equal number of units`
- `products with the same available quantity`
- `which products have equal reserved quantities`
- `products with more than 100 units`
- `show products with at least 10 available units`
- `products with exactly 0 units`
- `products with fewer than 8 units`
- `products with at most 8 units`

Equality compares each product's aggregate balance once, within its stored unit
of measure, and includes zero balances. Scoped queries compare assigned bin
balances in the requested location. A comparison with no matches reports that
explicitly. Numeric filters compare stored counts and display each result's unit.
These calculations always use the current inventory source, not document facts.

Added `GUIDE-INV-001` to the knowledge documents with quantity definitions,
supported question examples, source requirements and unassigned-location guidance.
Restart the coordinator and knowledge service to load it. The current Python
environment lacks `chromadb`, so the knowledge agent uses its existing keyword
fallback; vector retrieval was not verified. ChromaDB is declared in
`requirements.txt` and is needed for persistent vector indexing. The bundled
guide reloads at startup even when using the fallback.

Verified the screenshot question against Supabase: no two current products have
equal on-hand balances. The same-reserved-quantity query correctly returns the
two roll products with zero reserved balances. More-than-100 queries return the
120-roll and 340-unit products, with distinct units displayed.

Ranking wording also accepts "which product have highest number of units" and
the bounded typo "heights stock". Both are catalog comparisons, even when chat
history contains a previously selected product. An unrecognized short product
search does not silently borrow that old SKU; explicit follow-up references
continue to use conversation context.

Verified these exact phrases through the inventory MCP against Supabase: both
returned SKU-4521 with 340 on-hand units. The focused report, agent, edge-case
and thread regression suites passed 123 tests after the context fallback fix.

Verification after adding equality and filters: 493 backend tests passed and 28
opt-in tests were skipped. This includes knowledge retrieval, coordinator routing,
inventory MCP, thread context and unrelated agent regressions. Real Supabase
read-only MCP checks verified equality, reserved equality and numeric filtering.

## Data requirements

The database connection does not turn seeded inventory into live ERP data.
Verified physical bin assignments and an external operational feed are still
needed where those records are absent. Questions about unavailable expiry dates,
supplier histories or historical stock at an arbitrary date require those data
sources; the system cannot truthfully answer every possible question from the
current schema. Existing application accounts, orders and chat history remain
in SQLite. Credentials stay in ignored `.env`.
