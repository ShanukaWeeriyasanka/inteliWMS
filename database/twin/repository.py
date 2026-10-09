"""
Read/write access to the Warehouse Digital Twin.

Every function goes through the views and functions defined in schema.sql
(v_product_locations, find_route, get_directions, ...). Nothing here computes
quantities or routes itself, so the agents, the API and the map all read the
same numbers.
"""
import json
from contextvars import ContextVar
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import text

from database.twin.connection import twin_connection

ROUTE_PREFERENCES = ("lift", "stairs", "fastest")
_snapshot_connection = ContextVar('inventory_snapshot_connection', default=None)


def _value(v: Any) -> Any:
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return v


def _rows(result) -> List[Dict[str, Any]]:
    return [{k: _value(v) for k, v in row._mapping.items()} for row in result]


def _query(sql: str, **params: Any) -> List[Dict[str, Any]]:
    current = _snapshot_connection.get()
    if current is not None:
        return _rows(current.execute(text(sql), params))
    with twin_connection() as conn:
        return _rows(conn.execute(text(sql), params))


def get_inventory_snapshot():
    """All map quantities from one repeatable-read database snapshot."""
    with twin_connection() as conn:
        conn.execute(text('set transaction isolation level repeatable read, read only'))
        token = _snapshot_connection.set(conn)
        try:
            return {'products':get_product_totals(), 'locations':get_product_locations(),
                    'rack_fill':get_rack_fill(), 'alerts':get_open_alerts(),
                    'as_of':conn.execute(text('select transaction_timestamp()')).scalar().isoformat()}
        finally:
            _snapshot_connection.reset(token)


def get_stock_placements(product_id):
    """Per-lot rows for optimistic updates; the map uses the aggregate bin view."""
    return _query('select * from stock_locations where product_id=:pid order by bin_id,lot_code',pid=product_id)


# ── Static layout ────────────────────────────────────────────────────────────

def get_layout() -> Dict[str, List[Dict[str, Any]]]:
    """Everything needed to draw every floor. A few hundred rows for the demo."""
    with twin_connection() as conn:
        def q(sql: str) -> List[Dict[str, Any]]:
            return _rows(conn.execute(text(sql)))

        return {
            "warehouses": q("select id, name, address from warehouses order by id"),
            "floors": q("select id, warehouse_id, level, name, width_m, height_m from floors order by level"),
            "zones": q("select id, floor_id, name, type::text as type, x, y, width_m, height_m from zones order by id"),
            "racks": q("select id, zone_id, floor_id, name, aliases, type::text as type, x, y, width_m, depth_m, "
                       "rotation_deg, access_node_id from racks order by id"),
            "shelves": q("select id, rack_id, level_index, height_cm from shelves order by id"),
            "bins": q("select id, shelf_id, position_index, capacity_units, status::text as status from bins order by id"),
            "nav_nodes": q("select id, floor_id, type::text as type, label, x, y from nav_nodes order by id"),
            "nav_edges": q("select id, edge_type::text as edge_type, from_node_id, to_node_id, from_floor_id, "
                           "to_floor_id, bidirectional, blocked, distance_m, cost_s from v_nav_edges order by id"),
        }


def get_nav_edges() -> List[Dict[str, Any]]:
    return _query("select id, edge_type::text as edge_type, from_node_id, to_node_id, from_floor_id, to_floor_id, "
                  "bidirectional, blocked, distance_m, cost_s from v_nav_edges order by id")


# ── Products & stock ─────────────────────────────────────────────────────────

def get_product_totals() -> List[Dict[str, Any]]:
    return _query(
        "select t.product_id, t.product_no, t.sku, t.name, t.reorder_point, t.total_quantity, t.bin_count, "
        "       t.is_low_stock, t.is_out_of_stock, t.reserved_quantity, t.quarantined_quantity, "
        "       t.available_quantity, t.unplaced_quantity, t.updated_at, t.data_source, "
        "       p.category, p.unit, p.image_url, p.aliases, p.weight_kg, p.safety_stock, "
        "       p.reorder_quantity, p.daily_burn_rate, p.lead_time_days, p.unit_price, p.is_hazardous "
        "from v_product_totals t join products p on p.id = t.product_id "
        "where p.is_active order by t.product_no"
    )


def get_product_locations(product_ids: Optional[Iterable[str]] = None,
                          location_prefix: Optional[str] = None) -> List[Dict[str, Any]]:
    ids = list(product_ids or [])
    return _query(
        "select product_id, product_no, sku, product_name, quantity, reserved_quantity, quarantined_quantity, "
        "       available_quantity, data_sources, updated_at, bin_id, position_index, "
        "       capacity_units, bin_status::text as bin_status, shelf_id, level_index, rack_id, rack_name, "
        "       rack_type::text as rack_type, rack_x, rack_y, rack_width_m, rack_depth_m, access_node_id, zone_id, "
        "       zone_name, floor_id, floor_name, floor_level, warehouse_id, warehouse_name, location_label "
        "from v_inventory_placements "
        "where (cardinality(cast(:ids as text[])) = 0 or product_id = any(cast(:ids as text[]))) "
        "  and (cast(:prefix as text) is null or bin_id like cast(:prefix as text) || '%') "
        "order by quantity desc, floor_level, bin_id",
        ids=ids, prefix=location_prefix,
    )


def get_rack_fill(floor_id: Optional[str] = None) -> List[Dict[str, Any]]:
    return _query(
        "select rack_id, rack_name, zone_id, floor_id, total_units, distinct_products, capacity_units, fill_ratio "
        "from v_rack_fill where cast(:floor as text) is null or floor_id = cast(:floor as text) order by rack_id",
        floor=floor_id,
    )


def get_locations(ids: Iterable[str]) -> List[Dict[str, Any]]:
    return _query(
        "select location_id, level, label, floor_id, floor_name, floor_level, rack_id, access_node_id "
        "from v_locations where location_id = any(cast(:ids as text[]))",
        ids=list(ids),
    )


def get_racks(ids: Iterable[str]) -> List[Dict[str, Any]]:
    return _query(
        "select r.id, r.name, r.type::text as type, r.floor_id, f.name as floor_name, f.level as floor_level, "
        "       z.name as zone_name "
        "from racks r join zones z on z.id = r.zone_id join floors f on f.id = r.floor_id "
        "where r.id = any(cast(:ids as text[])) order by f.level, r.id",
        ids=list(ids),
    )


def get_open_alerts() -> List[Dict[str, Any]]:
    """Open alerts placed on the map: the alert's bin, else the product's fullest bin.
    Emptied stock rows are kept at quantity 0, so an out-of-stock product still
    points at the bin it was last picked from.

    A stock alert's stored message is written once, when the alert opens; the quantity
    keeps changing after that. Its message is therefore rebuilt from the live totals
    (v_product_totals) on every read, so it never shows a stale count."""
    return _query(
        "select a.id, a.type::text as type, a.level::text as level, a.product_id, a.bin_id, "
        "       case when a.type = 'low_stock' and t.product_id is not null then "
        "              t.name || ' (' || t.sku || '): ' || t.total_quantity || ' left, reorder point ' "
        "              || t.reorder_point "
        "            when a.type = 'out_of_stock' and t.product_id is not null then "
        "              t.name || ' (' || t.sku || ') is out of stock' "
        "            else a.message end as message, "
        "       a.created_at, "
        "       p.name as product_name, "
        "       substring(loc.bin_id from '^WH\\d+-F\\d+') as floor_id, "
        "       substring(loc.bin_id from '^WH\\d+-F\\d+-Z\\d{2}-R\\d{2}') as rack_id "
        "from alerts a left join products p on p.id = a.product_id "
        "left join v_product_totals t on t.product_id = a.product_id "
        "cross join lateral (select coalesce(a.bin_id, "
        "    (select sl.bin_id from stock_locations sl where sl.product_id = a.product_id "
        "      order by sl.quantity desc, sl.updated_at desc limit 1)) as bin_id) loc "
        "where a.resolved_at is null order by a.level desc, a.created_at desc"
    )


def get_movements(product_id: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
    return _query(
        "select m.id, m.product_id, p.name as product_name, m.from_bin_id, m.to_bin_id, m.quantity, "
        "       m.type::text as type, m.actor, m.note, m.created_at "
        "from stock_movements m join products p on p.id = m.product_id "
        "where cast(:pid as text) is null or m.product_id = cast(:pid as text) "
        "order by m.created_at desc, m.id desc limit :lim",
        pid=product_id, lim=limit,
    )


def get_movements_by_hour() -> List[Dict[str, Any]]:
    """Units moved per hour today (server time zone), every hour present even when zero."""
    return _query(
        "select to_char(h.hour, 'HH24:00') as hour, coalesce(sum(m.quantity), 0)::int as units "
        "from generate_series(date_trunc('day', now()), date_trunc('hour', now()), interval '1 hour') as h(hour) "
        "left join stock_movements m on date_trunc('hour', m.created_at) = h.hour "
        "group by h.hour order by h.hour"
    )


# ── Resolution (what did the user mean?) ─────────────────────────────────────

def resolve_product(q: str) -> List[Dict[str, Any]]:
    return _query("select * from resolve_product(:q)", q=q)


def resolve_location(q: str) -> List[Dict[str, Any]]:
    return _query("select * from resolve_location(:q)", q=q)


def access_node(location_id: Optional[str]) -> Optional[str]:
    rows = _query("select location_access_node(:id) as node", id=location_id)
    return rows[0]["node"] if rows else None


# ── Routing ──────────────────────────────────────────────────────────────────

def get_route(to_id: str, from_id: Optional[str] = None, prefer: str = "lift") -> Dict[str, Any]:
    """
    Path geometry (find_route) and turn-by-turn steps (get_directions) for one trip.

    Endpoints are resolved exactly the way get_directions resolves them, and the
    path falls back to 'fastest' under the same rule, so the line on the map and
    the written directions always describe the same walk.
    """
    if prefer not in ROUTE_PREFERENCES:
        raise ValueError(f"prefer must be one of {', '.join(ROUTE_PREFERENCES)}")

    with twin_connection() as conn:
        to_node = conn.execute(text("select location_access_node(:id)"), {"id": to_id}).scalar()
        from_node = conn.execute(text("select location_access_node(:id)"), {"id": from_id}).scalar()
        if to_node and not from_node:
            from_node = conn.execute(text(
                "select n.id from nav_nodes n join floors f on f.id = n.floor_id "
                "where n.type = 'entrance' and f.warehouse_id = split_part(:to_node, '-', 1) "
                "order by f.level, n.id limit 1"), {"to_node": to_node}).scalar()

        path: List[Dict[str, Any]] = []
        prefer_used = prefer
        if to_node and from_node:
            path = _rows(conn.execute(text(
                "select seq, node_id, floor_id, floor_level, x, y, node_type::text as node_type, label, "
                "       via::text as via, segment_m, total_m, total_s from find_route(:a, :b, :p)"),
                {"a": from_node, "b": to_node, "p": prefer}))
            if not path and prefer != "fastest":
                prefer_used = "fastest"
                path = _rows(conn.execute(text(
                    "select seq, node_id, floor_id, floor_level, x, y, node_type::text as node_type, label, "
                    "       via::text as via, segment_m, total_m, total_s from find_route(:a, :b, 'fastest')"),
                    {"a": from_node, "b": to_node}))

    # get_directions uses temp tables dropped on commit: run it in its own transaction.
    directions = _query(
        "select step, kind, floor_id, floor_name, instruction, distance_m, total_s, node_ids "
        "from get_directions(:t, :f, :p) order by step",
        t=to_id, f=from_id, p=prefer,
    )
    return {
        "to_id": to_id,
        "from_id": from_id,
        "from_node": from_node,
        "to_node": to_node,
        "prefer": prefer,
        "prefer_used": prefer_used if path else None,
        "path": path,
        "directions": directions,
    }


# ── Agent → UI channel ───────────────────────────────────────────────────────

def insert_ui_command(session_id: str, query_text: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    rows = _query(
        "insert into ui_commands (session_id, query_text, payload) values (:s, :q, cast(:p as jsonb)) "
        "returning id::text as id, session_id, query_text, payload, created_at",
        s=session_id, q=query_text, p=json.dumps(payload),
    )
    return rows[0]


def get_ui_commands(session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    return _query(
        "select id::text as id, session_id, query_text, payload, created_at from ui_commands "
        "where session_id = :s order by created_at desc limit :lim",
        s=session_id, lim=limit,
    )


def floor_with_most_units() -> Optional[str]:
    rows = _query("select floor_id from v_product_locations group by floor_id "
                  "order by sum(quantity) desc, floor_id limit 1")
    return rows[0]["floor_id"] if rows else None
