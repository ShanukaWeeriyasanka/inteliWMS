Inventory now uses the existing PostgreSQL twin as its authoritative source when
`TWIN_DATABASE_URL` is configured. A connection failure returns an error; it never
substitutes the application's SQLite quantities. Without PostgreSQL, existing
application inventory tools remain available and the floor map is disabled.

The supplied `inventory_schema.sql` was reviewed as a reference. Its standalone
`inventory` schema was not applied: that would introduce a third catalogue and
unnecessary supplier, forecasting, and equipment tables. The implementation reuses
the twin's products, locations, placements, movements, alerts, routes, and UI.

Applied changes
---------------

* `database/twin/inventory_migration.sql` adds reservation/quarantine quantities,
  product policy metadata, timestamps, provenance, legacy ID mappings, and unassigned
  imported balances. Existing product/bin IDs and movement records are retained.
* `v_product_totals` sums physical placements plus unassigned balances once.
  `v_inventory_placements` groups lots by product/bin, so each box appears once.
  Available = on-hand - reserved - quarantined. Zero-stock products remain searchable.
* Inventory MCP stock/search/low-stock/movement tools read the same source as the map.
  Numeric and existing alphanumeric SKUs work. Forecast/transfer calculations use
  canonical product metadata. The existing tool allowlist is enforced by the gateway;
  no stock-write tool is exposed to the LLM. Existing legacy anomaly history and
  document/equipment capabilities remain available.
* The UI loads one repeatable-read snapshot for cards, map, rack quantities, and alerts.
  It shows timestamps and source labels, all product locations, and the selected floor's
  warehouse. Product and exact-bin selection are separate. Only occupied boxes are
  highlighted. Older snapshot/command/movement/route responses cannot overwrite a
  newer selection. Refresh uses notifications, reconnect recovery, and 15-second polling.
* Inventory handoffs carry the conversation thread ID, including the first request.
  Correlated product retrieval, resolution, tool, response, and failure logs reuse
  the existing tracing infrastructure. Browser session IDs remain distinct.

Mapping applied on this machine
-------------------------------

| Application ID | SKU | Authoritative product ID | On-hand | Reserved | Available |
|---|---|---|---|---|---|
| 1 | SKU-4521 | PRD-00013 | 340 | 10 | 330 |
| 2 | SKU-7788 | PRD-00014 | 15 | 2 | 13 |
| 3 | SKU-9012 | PRD-00015 | 5 | 0 | 5 |
| 4 | SKU-1088 | PRD-00016 | 120 | 20 | 100 |
| 5 | SKU-2045 | PRD-00017 | 42 | 5 | 37 |

These quantities are **imported**, not externally verified live stock. Their exact
physical box assignments are unknown. The old aisle/shelf strings are preserved in
`inventory_product_mappings.legacy_snapshot`; they are not guessed into bin IDs.
The original application rows are retained for other agents and as migration history;
inventory does not sum their quantities or continue reading them after cutover.
Subsequent stock integrations must write the authoritative PostgreSQL balances.

The twelve existing map products retain PRD-00001 through PRD-00012. Their recorded
seed history is labelled **demo**. Mixed-provenance balances are labelled **mixed**.
Sibling-warehouse transfer data still comes from the existing local JSON snapshot;
responses explicitly identify that source. No external WMS/ERP stock feed is connected.

Backup and migration
--------------------

The initial database backup is
`logs/inventory_backups/20261009T085904366625.dump` (ignored by Git). It was created
before any migration/import. Application tables were not migrated or deleted.

On another installation, first configure `DATABASE_URL` and `TWIN_DATABASE_URL`
in `.env`, then run from the repository root in PowerShell:

```powershell
# Preview SKU-based mappings without changing data.
.\venv\Scripts\python.exe scripts\migrate_inventory.py

# Back up PostgreSQL, apply the additive migration, and import legacy products.
.\venv\Scripts\python.exe scripts\migrate_inventory.py --apply --pg-dump "C:\Program Files\PostgreSQL\18\bin\pg_dump.exe"
```

Use your installed `pg_dump` path. The migration is transactional; imports are
transactional and repeatable. Matching existing SKUs retain the twin balance; the
legacy record is archived in the mapping instead of double-counted or overwritten.
The importer assumes one application's legacy IDs per configured database.

Run the feature
---------------

Restart the backend to load the changed code and realtime triggers:

```powershell
.\venv\Scripts\python.exe -m uvicorn backend.main:app --reload --port 8000 --timeout-graceful-shutdown 3
```

In a second terminal:

```powershell
cd frontend
npm run dev
```

Open `http://localhost:5173` and sign in. Search in the inventory map for
`PRD-00002`, `EL-PWR-65W`, `Power Adapter`, or `charger`. The existing demo adapter
has boxes on two floors. Select each location to switch floor/warehouse and focus
the exact box. Search `SKU-4521`: its card and chat should show 340 on-hand,
10 reserved, 330 available, imported source, and location unassigned.

Ask `How many SKU-4521 are on hand?`, then `Where is it?` in the same chat.
Also try `Where is PRD-00002?` and `How many HW-SCR-4X40 are on hand?` (demo zero stock).

Stock changes and verified box mappings
--------------------------------------

The existing visual design remains a read interface. Managers/admins can use
`http://localhost:8000/docs` with their bearer token:

1. `GET /twin/layout` lists stable box IDs and their hierarchy.
2. `GET /twin/stock-placement?product_id=PRD-00002` returns individual lot rows
   and their exact `updated_at` values.
3. `PATCH /twin/stock-placement` updates a confirmed placement. Supply its current
   `expected_updated_at`; an outdated timestamp returns HTTP 409. For a new
   placement, use `expected_updated_at: null`. Missing reservation/quarantine
   values preserve the current amounts.

Example body for allocating 20 imported, unassigned units into a **physically
confirmed** empty box (replace IDs with your confirmed mapping):

```json
{
  "product_id": "PRD-00013",
  "bin_id": "WH1-F1-Z01-R01-S04-B06",
  "lot_code": "",
  "quantity": 20,
  "reserved_quantity": 0,
  "quarantined_quantity": 0,
  "expected_updated_at": null,
  "allocate_unplaced": true
}
```

`quantity` is the new placement total, not an increment. Allocation transfers the
quantity and supplied commitments out of the unassigned balance, preserving total
on-hand/reserved/available stock. Normal updates use `allocate_unplaced: false`.
Writes validate product/bin existence, capacity, blocked bins, and quantity limits,
lock affected balances, and record movements atomically. Authenticated staff can
read; only manager/admin roles can write. Notifications refresh affected views.
No example allocation above was applied to the configured database.

Tests
-----

```powershell
# Actual PostgreSQL acceptance tests use randomly named invtest_* schemas.
# SQLite test records are isolated from the application database.
$env:DATABASE_URL = "sqlite:///./inventory-verification.db"
$env:RUN_INVENTORY_PG_TESTS = "1"
.\venv\Scripts\python.exe -m pytest tests/test_inventory_authority.py -q -p no:cacheprovider
Remove-Item Env:DATABASE_URL
Remove-Item Env:RUN_INVENTORY_PG_TESTS

cd frontend
npm test
npm run build
```

The PostgreSQL test user must be able to create/drop the disposable test schemas.
Tests cover single/multiple bins, multiple floors and warehouses, ambiguous aliases,
zero stock, multiple lots, idempotent imports, unassigned allocation, reservations,
quarantine, capacity, stale writes, API authorization, MCP tools, thread context,
and connection failure. Frontend tests include rendered exact-box highlighting,
multi-warehouse location details, and response ordering.

Verified: PostgreSQL migration/import and real MCP smoke checks on the configured
database; isolated PostgreSQL acceptance tests; frontend tests/build; and the
existing backend regression suite, including unrelated agents.

Final results: 441 backend regression tests passed (24 skipped, including the seven
inventory PostgreSQL tests run separately); all seven isolated PostgreSQL inventory
tests passed; all 77 frontend tests passed; production build passed. The remaining
17 opt-in tests require separate live MCP/original PostgreSQL route test configuration.

Remaining: no browser session was available for interactive visual QA. No external
live warehouse feed or verified box mapping for the five imported SKUs was provided.
The existing opt-in live HTTP MCP and original PostgreSQL route acceptance suites
remain separate from the inventory acceptance tests. Configure a throwaway
`TWIN_TEST_DATABASE_URL` before running the original route database tests: they
reset their target schema. The inventory acceptance tests never reset `twin`.
# Supabase connection update (2026-10-09)

Inventory and the map now use the Supabase session pooler configured privately in
`.env` (`TWIN_DATABASE_URL`, SSL required, port 5432). The application database
remains SQLite, preserving existing users, chat history, orders, and other agents.
Supabase's `public` records differ from SQLite and were not overwritten or merged.

Before cloud changes, the existing `twin` schema was saved to
`logs/inventory_backups/supabase_before_20261009T093858.dump`; the import also made
`logs/inventory_backups/20261009T093958892876.dump`. Both are ignored by Git.
The additive migration and five-product import completed. Existing 12 products and
24 placements remain; imported IDs PRD-00013 through PRD-00017 have unplaced stock.
Seeded stock is demo data, and imported stock is labelled imported.

The exact question "which product have the lowest stocks" now routes in code to
inventory. The existing allowlisted `list_low_stock` MCP tool supports a validated
`selection=lowest_on_hand` mode, which compares all products and includes zero and
ties. Its default reorder-threshold behavior is preserved.

Verification: 140 existing routing/inventory/MCP regression tests passed, plus all
five new lowest-stock tests. Eight PostgreSQL acceptance tests passed in disposable
schemas on Supabase. Cloud read checks returned 17 products and 24 placements; the
authenticated inventory snapshot returned HTTP 200, and the session pooler's
LISTEN connection succeeded. The actual MCP answer identified HW-SCR-4X40 with
zero stock and explicitly labelled its source demo. No production quantities were
changed by these checks.

Restart the backend and any standalone inventory MCP process to reload `.env`.
Frontend tests (77) and production build passed for the details-panel layout fix.
Credentials remain in ignored `.env`; tracked examples contain placeholders only.

The subsequent full inventory update is documented in
[INVENTORY_QUESTIONS.md](INVENTORY_QUESTIONS.md). It adds source-qualified ID mappings,
imports the sixth Supabase application product (SKU-3300 → PRD-00018), and preserves
the overlapping SKU balances. The cloud now has 18 products, 24 physical placements
and 8 stock alerts. Catalog reports cover rankings, counts, summaries, status lists,
category grouping and warehouse/floor scopes. Alert cards display provenance and
unassigned balances; map commands highlight all returned products within their
requested scope. Summary/count reports do not imply a single selected product.

Final checks: 467 backend regressions passed (27 opt-in skipped), 10 separate
Supabase acceptance tests passed, and the focused report suite passed 22 tests,
including the additional reserved-zero ranking regression. Frontend tests passed
81 checks across 8 files; the production build passed with existing dependency
annotation and bundle-size warnings. Git whitespace checks passed. Actual cloud
MCP checks returned both zero-stock products for "lowest stock" and all 8 stock
alerts for "list low stock products". Interactive browser QA remains unverified.

## Supabase catalog selection — latest state

The user selected the supplied PostgreSQL database as the inventory catalog.
`scripts/select_inventory_catalog.py --apply` backed up the twin to
`logs/inventory_backups/20261009T102702880955.dump`, selected its six
`public.products` records, and archived the twelve unrelated demo products using
`is_active=false`. No product, placement, mapping or history row was deleted.
Active product totals, placements, search, alerts, rack fill and capacity checks
exclude archived products. Inventory history sessions and legacy inventory helpers
connect to PostgreSQL when configured, with no local SQLite catalog reads.

Current UI/API catalog: 6 products, 3 stock alerts, 0 verified physical placements.
All 18 product records and the 24 demo placement records remain stored for review.
Lowest-stock answers now identify only SKU-3300 at zero. Current Supabase application
and twin SKU sets agree. Restart/setup retains the active catalog selection.

Verification: 468 backend regressions passed; 28 opt-in tests skipped. All 11
PostgreSQL acceptance cases passed, with the two mapping/catalog tests rerun after
correcting their test layout. Authenticated map snapshot and real inventory MCP
checks confirmed the selected PostgreSQL catalog. No frontend files changed in
this catalog-selection update; previous 81 frontend tests and build remain valid.

## Highest-stock wording and stale context correction

The coordinator and inventory report parser now share ranking recognition for
stock, quantities, units, items and pieces. A bounded correction recognizes
"heights stock" as "highest stock". Catalog comparisons run before product
resolution and do not inherit a prior SKU. Unrecognized short searches no longer
borrow the previous product merely because they contain few words; explicit
follow-up references retain their existing behavior.

After the context change, 123 report, inventory MCP, edge-case and thread tests
passed. Earlier routing and deterministic checks passed 163 tests. Real Supabase
MCP verification of both screenshot phrases, with archived HW-SCR-4X40 in the
conversation, returned SKU-4521 at 340 units. One initial live attempt timed out;
a bounded direct database probe and both subsequent MCP queries succeeded.

## Equal-stock questions and inventory knowledge guidance

Added deterministic equal-quantity grouping and numeric stock filters to the
existing inventory report tool. Coordinator routing recognizes these operations;
results use current snapshots, preserve explicit metric and location scopes,
include zero commitments, and compare equality within the same unit of measure.
The existing map command supports returned comparison/filter product IDs.
No database schema or product data changed in this update.

Added knowledge document GUIDE-INV-001 for stock definitions, supported questions
and missing-location/source guidance. It contains no cached product quantities.
The current environment uses keyword fallback because chromadb is not installed;
persistent vector retrieval remains unverified. Restart services to load the guide.

Verification: 493 backend tests passed, 28 opt-in skipped. Real Supabase inventory
MCP reads confirmed no equal on-hand matches in the current catalog, two zero-
reserved roll products, and the correct more-than-100 count results. Tests cover
matching groups, no matches, different units, zero commitments, scoped placement
aggregation, numeric boundaries, stale chat context and knowledge retrieval.
No frontend code changed in this update; interactive browser QA was not repeated.
