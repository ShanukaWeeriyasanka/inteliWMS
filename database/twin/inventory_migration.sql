-- Additive inventory migration. Existing IDs, balances and movement history stay intact.
alter table products add column if not exists safety_stock int check (safety_stock >= 0);
alter table products add column if not exists reorder_quantity int check (reorder_quantity >= 0);
alter table products add column if not exists daily_burn_rate numeric(10,3);
alter table products add column if not exists lead_time_days int check (lead_time_days >= 0);
alter table products add column if not exists unit_price numeric(14,2);
alter table products add column if not exists is_hazardous boolean;
alter table products add column if not exists updated_at timestamptz not null default now();
alter table products add column if not exists data_source text not null default 'unverified'
  check (data_source in ('unverified','demo','imported','operational'));

alter table stock_locations add column if not exists reserved_quantity int not null default 0;
alter table stock_locations add column if not exists quarantined_quantity int not null default 0;
alter table stock_locations add column if not exists data_source text not null default 'unverified';
do $$ begin
  if not exists (select 1 from pg_constraint where conrelid = 'stock_locations'::regclass
                 and conname = 'inventory_stock_quantities') then
    alter table stock_locations add constraint inventory_stock_quantities
      check (reserved_quantity >= 0 and quarantined_quantity >= 0
             and reserved_quantity + quarantined_quantity <= quantity
             and data_source in ('unverified','demo','imported','operational'));
  end if;
end $$;

-- A one-time migration snapshot, never summed as another stock source.
create table if not exists inventory_product_mappings (
  application_product_id bigint primary key,
  product_id text not null unique references products(id),
  sku text not null unique,
  legacy_snapshot jsonb not null,
  imported_at timestamptz not null default now()
);
-- Legacy aisle text cannot safely be converted to a particular physical box.
create table if not exists unplaced_stock (
  product_id text primary key references products(id),
  quantity int not null check (quantity >= 0),
  reserved_quantity int not null default 0 check (reserved_quantity >= 0),
  quarantined_quantity int not null default 0 check (quarantined_quantity >= 0),
  data_source text not null default 'imported' check (data_source in ('imported','operational','unverified','demo')),
  updated_at timestamptz not null default now(),
  check (reserved_quantity + quarantined_quantity <= quantity)
);

drop trigger if exists unplaced_stock_twin_notify on unplaced_stock;
create trigger unplaced_stock_twin_notify after insert or update or delete on unplaced_stock
  for each row execute function twin_notify_change();

-- Label only products whose entire recorded history is explicitly seed-generated.
update products p set data_source = 'demo' where p.data_source = 'unverified'
  and exists (select 1 from stock_movements m where m.product_id=p.id and m.actor='seed')
  and not exists (select 1 from stock_movements m where m.product_id=p.id and m.actor is distinct from 'seed');
update stock_locations s set data_source='demo' from products p
  where p.id=s.product_id and p.data_source='demo' and s.data_source='unverified';

-- Preserve the original columns and append new fields so dependent views/functions remain valid.
create or replace view v_product_totals as
select p.id as product_id, p.product_no, p.sku, p.name, p.reorder_point,
  (coalesce(b.qty,0)+coalesce(u.quantity,0))::int as total_quantity,
  coalesce(b.bins,0)::int as bin_count,
  coalesce(b.qty,0)+coalesce(u.quantity,0) <= p.reorder_point as is_low_stock,
  coalesce(b.qty,0)+coalesce(u.quantity,0) = 0 as is_out_of_stock,
  (coalesce(b.reserved,0)+coalesce(u.reserved_quantity,0))::int as reserved_quantity,
  (coalesce(b.quarantine,0)+coalesce(u.quarantined_quantity,0))::int as quarantined_quantity,
  (coalesce(b.qty,0)+coalesce(u.quantity,0)-coalesce(b.reserved,0)-coalesce(u.reserved_quantity,0)
    -coalesce(b.quarantine,0)-coalesce(u.quarantined_quantity,0))::int as available_quantity,
  coalesce(u.quantity,0)::int as unplaced_quantity,
  greatest(p.updated_at,b.updated_at,u.updated_at) as updated_at,
  case when cardinality(array(select distinct unnest(coalesce(b.sources,'{}'::text[]) ||
       case when coalesce(u.quantity,0)>0 then array[u.data_source] else '{}'::text[] end))) > 1 then 'mixed'
       else coalesce(b.sources[1], case when u.quantity>0 then u.data_source end,p.data_source) end as data_source
from products p
left join lateral (
  select sum(quantity) qty, sum(reserved_quantity) reserved, sum(quarantined_quantity) quarantine,
    count(distinct bin_id) filter (where quantity>0) bins, max(updated_at) updated_at,
    array_agg(distinct data_source) filter (where quantity>0) sources
  from stock_locations where product_id=p.id
) b on true
left join unplaced_stock u on u.product_id=p.id;

-- A physical bin row aggregates lots exactly once. Zero rows retain their known box assignment.
create or replace view v_inventory_placements as
select p.id product_id, p.product_no, p.sku, p.name product_name,
  sum(sl.quantity)::int quantity, sum(sl.reserved_quantity)::int reserved_quantity,
  sum(sl.quarantined_quantity)::int quarantined_quantity,
  sum(sl.quantity-sl.reserved_quantity-sl.quarantined_quantity)::int available_quantity,
  max(sl.updated_at) updated_at,
  array_agg(distinct sl.data_source) data_sources,
  b.id bin_id, b.position_index, b.capacity_units, b.status bin_status,
  s.id shelf_id, s.level_index,
  r.id rack_id, r.name rack_name, r.type rack_type, r.x rack_x, r.y rack_y,
  r.width_m rack_width_m, r.depth_m rack_depth_m, r.access_node_id,
  z.id zone_id, z.name zone_name, f.id floor_id, f.name floor_name, f.level floor_level,
  w.id warehouse_id, w.name warehouse_name,
  format('%s · %s · %s · %s · Shelf %s · Bin %s',w.name,f.name,z.name,r.name,s.level_index,b.position_index) location_label
from stock_locations sl join products p on p.id=sl.product_id
join bins b on b.id=sl.bin_id join shelves s on s.id=b.shelf_id
join racks r on r.id=s.rack_id join zones z on z.id=r.zone_id
join floors f on f.id=z.floor_id join warehouses w on w.id=f.warehouse_id
group by p.id,b.id,s.id,r.id,z.id,f.id,w.id;

create or replace function inventory_stamp() returns trigger language plpgsql as $$
begin new.updated_at=now(); return new; end $$;
do $$ declare t text; begin
  foreach t in array array['products','stock_locations','unplaced_stock'] loop
    execute format('drop trigger if exists inventory_updated on %I',t);
    execute format('create trigger inventory_updated before update on %I for each row execute function inventory_stamp()',t);
  end loop;
end $$;

-- Threshold alerts must also follow unassigned balances and edited product policies.
create or replace function inventory_sync_threshold(p_product text) returns void language plpgsql as $$
declare t record;
begin
  select * into t from v_product_totals where product_id=p_product;
  if not found then return; end if;
  update alerts set resolved_at=now() where product_id=p_product and resolved_at is null
    and ((type='low_stock' and (not t.is_low_stock or t.is_out_of_stock))
      or (type='out_of_stock' and not t.is_out_of_stock));
  if t.is_out_of_stock then
    insert into alerts(type,level,product_id,message)
    values('out_of_stock','critical',p_product,format('%s (%s) is out of stock',t.name,t.sku)) on conflict do nothing;
  elsif t.is_low_stock then
    insert into alerts(type,level,product_id,message)
    values('low_stock','warning',p_product,format('%s (%s): %s left',t.name,t.sku,t.total_quantity)) on conflict do nothing;
  end if;
end $$;
create or replace function inventory_threshold_trigger() returns trigger language plpgsql as $$
begin
  if tg_table_name='products' then perform inventory_sync_threshold(coalesce(new.id,old.id));
  else perform inventory_sync_threshold(coalesce(new.product_id,old.product_id)); end if;
  return null;
end $$;
do $$ declare t text; p record; begin
  foreach t in array array['products','unplaced_stock'] loop
    execute format('drop trigger if exists inventory_thresholds on %I',t);
    execute format('create trigger inventory_thresholds after insert or update or delete on %I
                    for each row execute function inventory_threshold_trigger()',t);
  end loop;
  for p in select id from products loop perform inventory_sync_threshold(p.id); end loop;
end $$;
