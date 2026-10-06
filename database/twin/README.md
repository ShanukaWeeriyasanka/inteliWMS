# Warehouse Digital Twin — schema and IDs

The interactive warehouse map is driven entirely by this PostgreSQL schema (`twin`).
Files: [schema.sql](schema.sql) (tables, views, functions), [seed.sql](seed.sql) (demo
warehouse), [ui_command.schema.json](ui_command.schema.json) (agent → map contract).

## One ID per physical place

Every place has one hierarchical text ID. A child ID always starts with its parent's ID,
and CHECK constraints reject any ID that breaks this rule.

| Level     | Example                  | Meaning                                    |
|-----------|--------------------------|--------------------------------------------|
| Warehouse | `WH1`                    | Building                                   |
| Floor     | `WH1-F2`                 | Floor 2                                    |
| Zone      | `WH1-F2-Z01`             | Zone 1 on floor 2                          |
| Rack      | `WH1-F2-Z01-R02`         | Rack 2 in that zone                        |
| Shelf     | `WH1-F2-Z01-R02-S03`     | Shelf 3 (`S01` = floor level)              |
| Bin       | `WH1-F2-Z01-R02-S03-B04` | Bin 4 (`B01` = left-most, seen from aisle) |
| Nav node  | `WH1-F2-N009`            | Point on the walking graph                 |
| Product   | `PRD-00002`              | Product number 2                           |

Lifts and stairs keep the **same node number on every floor** (Lift A = `WH1-F1-N020`,
`WH1-F2-N020`, `WH1-F3-N020`), so a route can only change floor through a real connector.

## How a question becomes an exact spot on the map

1. The user asks *"where is product number 2?"*.
2. The Inventory Agent calls `resolve_product()` → `PRD-00002` (score 0.95, match on the product number).
3. It sends the map a command containing **IDs only**, for example:
   `{"action": "locate_product", "product_ids": ["PRD-00002"], "route": {"prefer": "lift"}}`.
4. The map validates the command (zod, mirroring `ui_command.schema.json`), checks that every
   ID exists, then reads quantities from `v_product_locations` and the route from
   `find_route()` / `get_directions()`.
5. Every SVG element carries `data-loc-id` equal to its database ID. Highlighting is a lookup
   by that exact string, never by name, so the orange bin is always the one in the database.

## Main tables and views

| Object                    | Used for                                                   |
|---------------------------|------------------------------------------------------------|
| `floors`, `zones`, `racks`, `shelves`, `bins` | Drawing the floor plan (metres, origin top-left) |
| `products`, `stock_locations` | What is stored where (one product can sit in many bins) |
| `stock_movements`         | Audit trail; "Recent movements" in the product panel      |
| `alerts`                  | Low stock / out of stock / over capacity (kept in sync by a trigger) |
| `nav_nodes`, `nav_edges`  | Walking graph for routes (`blocked` closes an aisle or lift) |
| `ui_commands`             | Agent → browser channel, delivered live via `NOTIFY`      |
| `v_product_locations`     | Every stock row with its full location path               |
| `v_product_totals`, `v_rack_fill` | Totals, low-stock flags, rack fill (heatmap)       |

Always change stock with `move_stock()`; it updates the stock row, writes the movement and
refreshes alerts in one transaction, and the map updates live.

Reset the demo data: `python scripts/setup_twin.py --reset`.
