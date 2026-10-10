"""Remove only the agents50 demo batch, preserving all other PostgreSQL rows."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor
from config.settings import settings


def main():
    conn = psycopg2.connect(settings.TWIN_DATABASE_URL, connect_timeout=20)
    schema = settings.TWIN_DB_SCHEMA
    selected = {}
    primary_keys = {}
    report_path = Path('data/undo_backups/agents50_removed_rows.json')
    report_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT pg_advisory_xact_lock(hashtext('intelliwms_dummy_seed'))")
            cur.execute(sql.SQL('SET LOCAL search_path TO {}, public, extensions').format(sql.Identifier(schema)))
            cur.execute("SET LOCAL statement_timeout = '60s'")

            def select(namespace, name, predicate, params):
                query = sql.SQL('SELECT * FROM {}.{} WHERE {} FOR UPDATE').format(
                    sql.Identifier(namespace), sql.Identifier(name), sql.SQL(predicate))
                cur.execute(query, params)
                rows = [dict(row) for row in cur.fetchall()]
                if len(rows) != 50:
                    raise RuntimeError(f'{namespace}.{name}: found {len(rows)} batch rows instead of 50; rollback.')
                selected[namespace, name] = rows
                return rows

            def prefix(namespace, name, column, value):
                return select(namespace, name, f'starts_with({column}, %s)', (value,))

            tag = 'DEMO-agents50'
            prefix('public', 'users', 'username', 'demo_agents50_')
            prefix('public', 'security_audit_logs', 'event_id', tag + '-SEC-')
            prefix('public', 'warehouse_locations', 'location_code', tag + '-LOC-')
            prefix('public', 'products', 'sku', tag + '-SKU-')
            prefix('public', 'inventory_transactions', 'reference_id', tag + '-RCV-')
            prefix('public', 'orders', 'order_id', tag + '-ORD-')
            prefix('public', 'order_items', 'order_id', tag + '-ORD-')
            prefix('public', 'shipments', 'tracking_number', tag + '-TRK-')
            prefix('public', 'returns', 'return_id', tag + '-RET-')
            prefix('public', 'shift_handoffs', 'summary', tag + ':')
            prefix('public', 'compliance_incidents', 'description', tag + ':')
            threads = prefix('public', 'chat_threads', 'title', tag + ':')
            thread_ids = [row['id'] for row in threads]
            select('public', 'chat_messages', 'thread_id=ANY(%s)', (thread_ids,))
            select('public', 'conversation_logs', 'session_id=ANY(%s)', (thread_ids,))

            products = prefix(schema, 'products', 'sku', tag + '-SKU-')
            product_ids = [row['id'] for row in products]
            warehouses = prefix(schema, 'warehouses', 'name', tag + ' Warehouse ')
            floors = select(schema, 'floors', 'warehouse_id=ANY(%s)', ([r['id'] for r in warehouses],))
            zones = select(schema, 'zones', 'floor_id=ANY(%s)', ([r['id'] for r in floors],))
            nodes = select(schema, 'nav_nodes', 'floor_id=ANY(%s)', ([r['id'] for r in floors],))
            node_ids = [r['id'] for r in nodes]
            select(schema, 'nav_edges', 'from_node_id=ANY(%s) OR to_node_id=ANY(%s)', (node_ids, node_ids))
            racks = select(schema, 'racks', 'zone_id=ANY(%s)', ([r['id'] for r in zones],))
            shelves = select(schema, 'shelves', 'rack_id=ANY(%s)', ([r['id'] for r in racks],))
            select(schema, 'bins', 'shelf_id=ANY(%s)', ([r['id'] for r in shelves],))
            select(schema, 'stock_locations', 'product_id=ANY(%s)', (product_ids,))
            prefix(schema, 'stock_movements', 'note', tag + ':')
            prefix(schema, 'alerts', 'message', tag + ':')
            select(schema, 'ui_commands', 'session_id=ANY(%s)', (thread_ids,))
            select(schema, 'unplaced_stock', 'product_id=ANY(%s)', (product_ids,))
            select(schema, 'inventory_product_mappings', 'source_system=%s', ('demo:agents50',))

            cur.execute('''SELECT n.nspname AS namespace, c.relname AS table_name,
                array_agg(a.attname ORDER BY k.ordinality) AS columns
                FROM pg_constraint con JOIN pg_class c ON c.oid=con.conrelid
                JOIN pg_namespace n ON n.oid=c.relnamespace
                CROSS JOIN LATERAL unnest(con.conkey) WITH ORDINALITY AS k(attnum, ordinality)
                JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum=k.attnum
                WHERE con.contype='p' AND n.nspname IN ('public', %s)
                GROUP BY n.nspname,c.relname''', (schema,))
            for row in cur.fetchall():
                primary_keys[row['namespace'], row['table_name']] = row['columns']

            # Check every inbound FK, including references from other schemas.
            # A later non-demo record must never be removed by ON DELETE CASCADE.
            cur.execute('''SELECT cn.nspname AS child_schema, cc.relname AS child_table,
                pn.nspname AS parent_schema, pc.relname AS parent_table,
                array_agg(ca.attname ORDER BY k.ordinality) AS child_columns,
                array_agg(pa.attname ORDER BY k.ordinality) AS parent_columns
                FROM pg_constraint con
                JOIN pg_class cc ON cc.oid=con.conrelid JOIN pg_namespace cn ON cn.oid=cc.relnamespace
                JOIN pg_class pc ON pc.oid=con.confrelid JOIN pg_namespace pn ON pn.oid=pc.relnamespace
                CROSS JOIN LATERAL unnest(con.conkey,con.confkey) WITH ORDINALITY AS k(cnum,pnum,ordinality)
                JOIN pg_attribute ca ON ca.attrelid=cc.oid AND ca.attnum=k.cnum
                JOIN pg_attribute pa ON pa.attrelid=pc.oid AND pa.attnum=k.pnum
                WHERE con.contype='f' AND pn.nspname IN ('public', %s)
                GROUP BY con.oid,cn.nspname,cc.relname,pn.nspname,pc.relname''', (schema,))
            foreign_keys = list(cur.fetchall())
            for fk in foreign_keys:
                parent = (fk['parent_schema'], fk['parent_table'])
                if parent not in selected:
                    continue
                if len(fk['parent_columns']) != 1:
                    raise RuntimeError('Unexpected composite FK; stop to preserve external data.')
                child = (fk['child_schema'], fk['child_table'])
                values = [row[fk['parent_columns'][0]] for row in selected[parent]]
                cur.execute(sql.SQL('SELECT * FROM {}.{} WHERE {}=ANY(%s)').format(
                    sql.Identifier(child[0]), sql.Identifier(child[1]),
                    sql.Identifier(fk['child_columns'][0])), (values,))
                dependents = list(cur.fetchall())
                keys = primary_keys.get(child)
                allowed = {tuple(row[k] for k in keys) for row in selected.get(child, [])} if keys else set()
                for row in dependents:
                    if not keys or tuple(row[k] for k in keys) not in allowed:
                        raise RuntimeError(f'Non-demo record in {child} references this demo batch; rollback.')

            before = {}
            for namespace, name in selected:
                cur.execute(sql.SQL('SELECT count(*) AS count FROM {}.{}').format(
                    sql.Identifier(namespace), sql.Identifier(name)))
                before[namespace, name] = cur.fetchone()['count']
            backup = {'batch': 'agents50', 'rows': {f'{s}.{t}': rows for (s,t),rows in selected.items()}}
            report_path.write_text(json.dumps(backup, indent=2, default=str), encoding='utf-8')
            cur.execute(sql.SQL('UPDATE {}.products SET is_active=false WHERE id=ANY(%s)').format(
                sql.Identifier(schema)), (product_ids,))

            order = [
                ('public', name) for name in ['chat_messages', 'conversation_logs', 'chat_threads',
                'security_audit_logs', 'compliance_incidents', 'shift_handoffs', 'returns',
                'shipments', 'order_items', 'orders', 'inventory_transactions', 'products',
                'warehouse_locations', 'users']
            ] + [(schema, name) for name in ['ui_commands', 'alerts', 'stock_movements',
                'inventory_product_mappings', 'stock_locations', 'unplaced_stock', 'products',
                'nav_edges', 'bins', 'shelves', 'racks', 'nav_nodes', 'zones', 'floors', 'warehouses']]
            deleted = {}
            for key in order:
                keys = primary_keys[key]
                where = sql.SQL(' AND ').join(sql.SQL('{}=%s').format(sql.Identifier(k)) for k in keys)
                query = sql.SQL('DELETE FROM {}.{} WHERE {}').format(
                    sql.Identifier(key[0]), sql.Identifier(key[1]), where)
                cur.executemany(query, [tuple(row[k] for k in keys) for row in selected[key]])
                if cur.rowcount != 50:
                    raise RuntimeError(f'{key}: unexpected deletion count {cur.rowcount}; rollback.')
                cur.execute(sql.SQL('SELECT count(*) AS count FROM {}.{}').format(
                    sql.Identifier(key[0]), sql.Identifier(key[1])))
                after = cur.fetchone()['count']
                if before[key] - after != 50:
                    raise RuntimeError(f'{key}: unexpected count delta; rollback.')
                deleted['.'.join(key)] = 50
        conn.commit()
        Path('data/undo_backups/agents50_undo_report.json').write_text(
            json.dumps({'deleted': deleted, 'total_deleted': sum(deleted.values())}, indent=2), encoding='utf-8')
        print(f'COMMITTED: removed exactly {sum(deleted.values())} demo rows from {len(deleted)} tables.')
        print('All non-demo FK references checked; other records preserved.')
        print('Removed-row backup:', report_path)
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    main()
