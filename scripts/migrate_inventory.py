"""Back up the configured twin and import legacy inventory without inventing bins.

python scripts/migrate_inventory.py --apply --pg-dump PATH
Without --apply this prints the SKU mapping plan only. Repeated imports are no-ops.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import text
from sqlalchemy.engine import make_url
from database.connection import SessionLocal
from database.models import Product
from database.twin.connection import twin_connection, twin_database_url, twin_schema
from database.twin.setup import ensure_twin_schema


def import_products(rows):
    """SKU is the cross-system key. Keep snapshots but never add conflicting balances."""
    mappings = []
    with twin_connection() as conn:
        conn.execute(text("select pg_advisory_xact_lock(hashtext('inventory_legacy_import'))"))
        for p in rows:
            previous = conn.execute(text('select product_id from inventory_product_mappings where application_product_id=:id'),
                                    {'id': p.id}).scalar()
            if previous:
                mappings.append((p.id, p.sku, previous, 'already mapped'))
                continue
            snapshot = {c.name: getattr(p,c.name) for c in Product.__table__.columns}
            pid = conn.execute(text('select id from products where upper(sku)=upper(:sku)'), {'sku':p.sku}).scalar()
            created = pid is None
            if created:
                conn.execute(text('lock table products in share row exclusive mode'))
                pid = conn.execute(text('''insert into products
                    (product_no,sku,name,category,unit,weight_kg,reorder_point,safety_stock,reorder_quantity,
                     daily_burn_rate,lead_time_days,unit_price,is_hazardous,data_source)
                    select coalesce(max(product_no),0)+1,:sku,:name,:category,:unit,:weight,:point,:safety,:reorder,
                           :burn,:lead,:price,:hazard,'imported' from products returning id'''),
                    {'sku':p.sku,'name':p.name,'category':p.category,'unit':p.unit or 'units','weight':p.weight_kg,
                     'point':p.reorder_point or 0,'safety':p.safety_stock,'reorder':p.reorder_quantity,
                     'burn':p.daily_burn_rate,'lead':p.lead_time_days,'price':p.unit_price,'hazard':p.is_hazardous}).scalar()
                conn.execute(text('''insert into unplaced_stock (product_id,quantity,reserved_quantity,updated_at)
                    values (:pid,:qty,:reserved,coalesce(:updated,now()))'''),
                    {'pid':pid,'qty':p.quantity or 0,'reserved':p.reserved_quantity or 0,'updated':p.updated_at})
            conn.execute(text('''insert into inventory_product_mappings
                (application_product_id,product_id,sku,legacy_snapshot) values (:id,:pid,:sku,cast(:snapshot as jsonb))'''),
                {'id':p.id,'pid':pid,'sku':p.sku,'snapshot':json.dumps(snapshot,default=str)})
            mappings.append((p.id,p.sku,pid,'imported unplaced' if created else 'existing twin balance retained'))
    return mappings


def backup(pg_dump):
    executable = pg_dump or shutil.which('pg_dump')
    if not executable:
        raise RuntimeError('pg_dump is required before modifying the configured database; pass --pg-dump PATH')
    directory = Path('logs/inventory_backups')
    directory.mkdir(parents=True,exist_ok=True)
    destination = directory / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f') + '.dump')
    url = make_url(twin_database_url())
    env = os.environ.copy()
    env['PGPASSWORD'] = url.password or ''
    result = subprocess.run([executable,'--format=custom','--no-password','--host',url.host or 'localhost',
        '--port',str(url.port or 5432),'--username',url.username or 'postgres','--dbname',url.database,
        '--schema',twin_schema(),'--file',str(destination)],env=env,capture_output=True)
    if result.returncode:
        raise RuntimeError('Database backup failed; migration not applied')
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--pg-dump')
    args = parser.parse_args()
    with SessionLocal() as db:
        rows = db.query(Product).order_by(Product.id).all()
        if not args.apply:
            with twin_connection() as conn:
                existing = {r.sku.upper():r.id for r in conn.execute(text('select id,sku from products'))}
            for p in rows:
                print(p.id,p.sku,existing.get(p.sku.upper(),'new stable ID; unassigned location'))
            return
        print('Backup:',backup(args.pg_dump))
        ensure_twin_schema(seed=False)
        for mapping in import_products(rows):
            print(*mapping)


if __name__ == '__main__':
    main()
