"""Use only Supabase public.products as the operational inventory catalog.

Default: read-only plan. --apply backs up first, then archives unrelated products.
No product, placement, movement, mapping or legacy application row is deleted.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import text
from database.models import Product
from database.twin.connection import twin_connection
from database.twin.setup import ensure_twin_schema
from scripts.migrate_inventory import backup, import_products


def select_catalog(rows):
    if not rows:
        raise ValueError('Supabase catalog is empty; refusing to archive all products')
    mappings = import_products(rows, source_system='supabase_public')
    allowed = [mapping[2] for mapping in mappings]
    with twin_connection() as conn:
        conn.execute(text("select pg_advisory_xact_lock(hashtext('inventory_catalog_selection'))"))
        # Set is_active only; archived quantities/history remain intact for review.
        conn.execute(text('''update products set is_active=(id=any(cast(:ids as text[])))
            where is_active is distinct from (id=any(cast(:ids as text[])))'''),{'ids':allowed})
    return mappings


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--pg-dump')
    args=parser.parse_args()
    with twin_connection() as conn:
        rows=[Product(**dict(r._mapping)) for r in conn.execute(text('select * from public.products order by id'))]
        current=[dict(r._mapping) for r in conn.execute(text('select id,sku,is_active from products order by product_no'))]
    if not rows:
        raise RuntimeError('Supabase public.products is empty; no changes applied')
    skus={p.sku.upper() for p in rows}
    print('Supabase catalog:',sorted(skus))
    print('Archive unrelated catalog records:',[p['sku'] for p in current if p['is_active'] and p['sku'].upper() not in skus])
    if args.apply:
        print('Backup:',backup(args.pg_dump))
        ensure_twin_schema(seed=False)
        for mapping in select_catalog(rows): print('supabase_public',*mapping)
        print('Operational products:',len(rows))


if __name__=='__main__':
    main()
