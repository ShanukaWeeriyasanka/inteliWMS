-- =====================================================================
--  WAREHOUSE DIGITAL TWIN — PostgreSQL / Supabase schema
-- ---------------------------------------------------------------------
--  ID RULES (the core of accuracy)
--  Every physical place has ONE human-readable, hierarchical text ID.
--  The same string is used in the database, in the agent's answer,
--  and as the `data-loc-id` attribute of the SVG element on the map.
--
--    Warehouse  WH1
--    Floor      WH1-F2
--    Zone       WH1-F2-Z03
--    Rack       WH1-F2-Z03-R07
--    Shelf      WH1-F2-Z03-R07-S04        (S01 = bottom level)
--    Bin        WH1-F2-Z03-R07-S04-B02    (B01 = left-most, seen from aisle)
--    Nav node   WH1-F2-N015
--    Product    PRD-00002                 (product_no = 2)
--
--  MULTI-FLOOR RULE: a lift or staircase has the SAME node number on
--  every floor it serves (Lift A = WH1-F1-N020, WH1-F2-N020, WH1-F3-N020).
--  Vertical edges may only join nodes with the same number, so the route
--  engine can never "teleport" between unrelated points.
--
--  A child ID must start with its parent ID — enforced by CHECK
--  constraints below, so a wrong or orphaned ID can never be stored.
-- =====================================================================

create extension if not exists pg_trgm;

-- ---------- Enumerations ----------
create type zone_type   as enum ('storage', 'cold', 'bulk', 'picking', 'staging', 'dock', 'charging');
create type rack_type   as enum ('pallet_grid', 'crate_rack', 'shelf_unit', 'cabinet');
create type bin_status  as enum ('active', 'blocked', 'maintenance');
create type node_type   as enum ('aisle', 'intersection', 'entrance', 'dock', 'rack_access', 'charging', 'lift', 'stairs');
create type edge_type   as enum ('walk', 'lift', 'stairs');
create type alert_type  as enum ('low_stock', 'out_of_stock', 'bin_over_capacity');
create type alert_level as enum ('info', 'warning', 'critical');
create type movement_type as enum ('receive', 'pick', 'transfer', 'adjust');

-- =====================================================================
--  LOCATION HIERARCHY
--  Map coordinates are in METRES, origin top-left of the floor,
--  x to the right, y downward (same as SVG).
-- =====================================================================
create table warehouses (
  id          text primary key check (id ~ '^WH\d+$'),
  name        text not null,
  address     text,
  created_at  timestamptz not null default now()
);

create table floors (
  id            text primary key,
  warehouse_id  text not null references warehouses(id) on delete cascade,
  level         int  not null,
  name          text not null,                 -- "Floor 2"
  width_m       numeric(8,2) not null,
  height_m      numeric(8,2) not null,
  unique (warehouse_id, level),
  check (id ~ '^WH\d+-F\d+$' and id like warehouse_id || '-F%')
);

create table zones (
  id         text primary key,
  floor_id   text not null references floors(id) on delete cascade,
  name       text not null,                    -- "Zone 3 — Electronics"
  type       zone_type not null default 'storage',
  x numeric(8,2) not null, y numeric(8,2) not null,
  width_m numeric(8,2) not null, height_m numeric(8,2) not null,
  check (id ~ '^WH\d+-F\d+-Z\d{2}$' and id like floor_id || '-Z%')
);

create table nav_nodes (
  id        text primary key,
  floor_id  text not null references floors(id) on delete cascade,
  type      node_type not null default 'aisle',
  label     text,                              -- "Main entrance", "Dock A"
  x numeric(8,2) not null, y numeric(8,2) not null,
  check (id ~ '^WH\d+-F\d+-N\d{3}$' and id like floor_id || '-N%')
);

-- Walk edges join two nodes on the same floor.
-- Lift / stairs edges join the same connector on two ADJACENT floors.
create table nav_edges (
  id            bigint generated always as identity primary key,
  edge_type     edge_type not null default 'walk',
  from_node_id  text not null references nav_nodes(id) on delete cascade,
  to_node_id    text not null references nav_nodes(id) on delete cascade,
  bidirectional boolean not null default true,
  blocked       boolean not null default false,  -- closed aisle, lift out of service…
  traverse_s    numeric(6,1),                    -- optional time override in seconds
  unique (from_node_id, to_node_id),
  check (from_node_id <> to_node_id),
  check (
    (edge_type = 'walk'
       and split_part(from_node_id, '-N', 1) = split_part(to_node_id, '-N', 1))
    or
    (edge_type <> 'walk'
       and split_part(from_node_id, '-N', 2) = split_part(to_node_id, '-N', 2)
       and split_part(from_node_id, '-N', 1) <> split_part(to_node_id, '-N', 1))
  )
);

create table racks (
  id              text primary key,
  zone_id         text not null references zones(id) on delete cascade,
  floor_id        text generated always as (substring(id from '^WH\d+-F\d+')) stored,
  name            text not null,               -- "Rack 7" (unique per floor)
  aliases         text[] not null default '{}',-- other names people use: {"freezer 1","A7"}
  type            rack_type not null,
  x numeric(8,2) not null, y numeric(8,2) not null,          -- top-left corner
  width_m numeric(6,2) not null, depth_m numeric(6,2) not null,
  rotation_deg    numeric(5,1) not null default 0,
  access_node_id  text references nav_nodes(id),  -- where a picker stands to reach it
  unique (floor_id, name),
  check (id ~ '^WH\d+-F\d+-Z\d{2}-R\d{2}$' and id like zone_id || '-R%'),
  check (access_node_id is null or access_node_id like floor_id || '-N%')
);

create table shelves (
  id            text primary key,
  rack_id       text not null references racks(id) on delete cascade,
  level_index   int  not null check (level_index >= 1),   -- 1 = floor level
  height_cm     numeric(6,1),
  max_weight_kg numeric(8,2),
  unique (rack_id, level_index),
  check (id ~ '^WH\d+-F\d+-Z\d{2}-R\d{2}-S\d{2}$' and id like rack_id || '-S%')
);

create table bins (
  id              text primary key,
  shelf_id        text not null references shelves(id) on delete cascade,
  position_index  int  not null check (position_index >= 1),
  capacity_units  int  not null default 100 check (capacity_units > 0),
  max_weight_kg   numeric(8,2),
  status          bin_status not null default 'active',
  unique (shelf_id, position_index),
  check (id ~ '^WH\d+-F\d+-Z\d{2}-R\d{2}-S\d{2}-B\d{2}$' and id like shelf_id || '-B%')
);

-- =====================================================================
--  PRODUCTS & STOCK
-- =====================================================================
create table products (
  product_no     int  not null unique check (product_no > 0),   -- "product number 2"
  id             text generated always as ('PRD-' || lpad(product_no::text, 5, '0')) stored primary key,
  sku            text not null unique,
  name           text not null,
  aliases        text[] not null default '{}',  -- nicknames users type: {"blue box","widget a"}
  category       text,
  unit           text not null default 'pcs',
  weight_kg      numeric(8,3),
  reorder_point  int  not null default 0 check (reorder_point >= 0),
  image_url      text,
  is_active      boolean not null default true,  -- archive instead of deleting (keeps audit trail)
  created_at     timestamptz not null default now()
);
create index products_name_trgm on products using gin (name gin_trgm_ops);
create index products_aliases_gin on products using gin (aliases);

-- One product can live in MANY bins; one bin can hold MANY products.
create table stock_locations (
  id          bigint generated always as identity primary key,
  product_id  text not null references products(id) on delete cascade,
  bin_id      text not null references bins(id) on delete restrict,
  quantity    int  not null check (quantity >= 0),
  lot_code    text not null default '',
  expires_on  date,
  updated_at  timestamptz not null default now(),
  unique (product_id, bin_id, lot_code)
);
create index stock_locations_bin_idx on stock_locations (bin_id);

-- Append-only audit trail of every change.
create table stock_movements (
  id           bigint generated always as identity primary key,
  product_id   text not null references products(id),
  from_bin_id  text references bins(id),
  to_bin_id    text references bins(id),
  quantity     int  not null check (quantity > 0),
  type         movement_type not null,
  actor        text,                            -- user id, robot id, agent name
  note         text,
  created_at   timestamptz not null default now(),
  check (from_bin_id is not null or to_bin_id is not null)
);

create table alerts (
  id           bigint generated always as identity primary key,
  type         alert_type  not null,
  level        alert_level not null,
  product_id   text references products(id) on delete cascade,
  bin_id       text references bins(id) on delete cascade,
  message      text not null,
  created_at   timestamptz not null default now(),
  resolved_at  timestamptz
);
-- At most one OPEN alert of each type per product.
create unique index alerts_one_open_per_product
  on alerts (type, product_id) where resolved_at is null and product_id is not null;

-- =====================================================================
--  AGENT → UI CHANNEL
--  The multi-agent system inserts one row per answered question.
--  The UI subscribes (Supabase Realtime) filtered by session_id and
--  pops up as soon as the row arrives. Payload format:
--  see ui_command.schema.json
-- =====================================================================
create table ui_commands (
  id          uuid primary key default gen_random_uuid(),
  session_id  text not null,
  query_text  text not null,
  payload     jsonb not null check (payload ? 'action' and payload ? 'version'),
  created_at  timestamptz not null default now()
);
create index ui_commands_session_idx on ui_commands (session_id, created_at desc);

-- =====================================================================
--  VIEWS — what the UI and the agents read
-- =====================================================================

-- Every unit of stock with its full location path + map coordinates.
create view v_product_locations as
select
  p.id            as product_id,
  p.product_no,
  p.sku,
  p.name          as product_name,
  sl.quantity,
  sl.lot_code,
  sl.updated_at,
  b.id  as bin_id,   b.position_index,  b.capacity_units, b.status as bin_status,
  s.id  as shelf_id, s.level_index,
  r.id  as rack_id,  r.name as rack_name, r.type as rack_type,
  r.x as rack_x, r.y as rack_y, r.width_m as rack_width_m, r.depth_m as rack_depth_m,
  r.access_node_id,
  z.id  as zone_id,  z.name as zone_name,
  f.id  as floor_id, f.name as floor_name, f.level as floor_level,
  w.id  as warehouse_id, w.name as warehouse_name,
  format('%s · %s · %s · Shelf %s · Bin %s',
         f.name, z.name, r.name, s.level_index, b.position_index) as location_label
from stock_locations sl
join products   p on p.id = sl.product_id
join bins       b on b.id = sl.bin_id
join shelves    s on s.id = b.shelf_id
join racks      r on r.id = s.rack_id
join zones      z on z.id = r.zone_id
join floors     f on f.id = z.floor_id
join warehouses w on w.id = f.warehouse_id
where sl.quantity > 0;

-- One row per product: total stock and low-stock flag.
create view v_product_totals as
select
  p.id as product_id, p.product_no, p.sku, p.name, p.reorder_point,
  coalesce(sum(sl.quantity), 0)::int                       as total_quantity,
  count(sl.id) filter (where sl.quantity > 0)::int         as bin_count,
  coalesce(sum(sl.quantity), 0) <= p.reorder_point          as is_low_stock,
  coalesce(sum(sl.quantity), 0) = 0                         as is_out_of_stock
from products p
left join stock_locations sl on sl.product_id = p.id
group by p.id;

-- Fill level per rack — drives the heatmap and count badges.
create view v_rack_fill as
select
  r.id as rack_id, r.name as rack_name, z.id as zone_id, z.floor_id,
  coalesce(sum(sl.quantity), 0)::int                         as total_units,
  count(distinct sl.product_id) filter (where sl.quantity > 0)::int as distinct_products,
  (select coalesce(sum(b2.capacity_units), 0) from shelves s2
     join bins b2 on b2.shelf_id = s2.id where s2.rack_id = r.id)::int as capacity_units,
  round(coalesce(sum(sl.quantity), 0)::numeric / nullif(
    (select sum(b2.capacity_units) from shelves s2
       join bins b2 on b2.shelf_id = s2.id where s2.rack_id = r.id), 0), 3) as fill_ratio
from racks r
join zones z on z.id = r.zone_id
left join shelves s on s.rack_id = r.id
left join bins b on b.shelf_id = s.id
left join stock_locations sl on sl.bin_id = b.id
group by r.id, z.id;

-- Navigation edges with their length, for client-side Dijkstra.
-- Navigation edges with length and travel time.
-- Walking speed 1.2 m/s; lift 25 s per floor (incl. waiting); stairs 18 s per floor.
create view v_nav_edges as
select e.id, e.edge_type, e.from_node_id, e.to_node_id,
       a.floor_id as from_floor_id, b.floor_id as to_floor_id,
       e.bidirectional, e.blocked,
       case when e.edge_type = 'walk'
            then round(sqrt(power(b.x - a.x, 2) + power(b.y - a.y, 2)), 2) else 0 end as distance_m,
       coalesce(e.traverse_s,
         case e.edge_type
           when 'walk'   then round(sqrt(power(b.x - a.x, 2) + power(b.y - a.y, 2)) / 1.2, 1)
           when 'lift'   then 25
           when 'stairs' then 18 end) as cost_s
from nav_edges e
join nav_nodes a on a.id = e.from_node_id
join nav_nodes b on b.id = e.to_node_id;

-- Every addressable place (floor → bin) with a readable label.
-- Used by resolve_location() and by the UI for captions.
create view v_locations as
select f.id as location_id, 'floor'::text as level, f.name as label,
       f.id as floor_id, f.name as floor_name, f.level as floor_level,
       null::text as rack_id, null::text as access_node_id
from floors f
union all
select z.id, 'zone', format('%s, %s', z.name, f.name), f.id, f.name, f.level, null, null
from zones z join floors f on f.id = z.floor_id
union all
select r.id, 'rack', format('%s, %s, %s', r.name, z.name, f.name), f.id, f.name, f.level, r.id, r.access_node_id
from racks r join zones z on z.id = r.zone_id join floors f on f.id = z.floor_id
union all
select s.id, 'shelf', format('%s, shelf %s, %s', r.name, s.level_index, f.name), f.id, f.name, f.level, r.id, r.access_node_id
from shelves s join racks r on r.id = s.rack_id join zones z on z.id = r.zone_id join floors f on f.id = z.floor_id
union all
select b.id, 'bin', format('%s, shelf %s, bin %s, %s', r.name, s.level_index, b.position_index, f.name),
       f.id, f.name, f.level, r.id, r.access_node_id
from bins b join shelves s on s.id = b.shelf_id join racks r on r.id = s.rack_id
join zones z on z.id = r.zone_id join floors f on f.id = z.floor_id;

-- =====================================================================
--  FUNCTIONS
-- =====================================================================

-- Turns what the user typed into ranked product candidates. Works on a
-- bare value ("2", "EL-PWR-65W", "charger") or a whole sentence
-- ("where is product number 2?", "how many M8 bolts?"). A number only
-- counts as a product number when it is the whole input or follows
-- "product", "item", "no", "number" or "#" — so "M8 bolts" never
-- resolves to product 8. The agent should call this instead of guessing.
-- score 1.0 = exact SKU / ID, 0.95 = product number, 0.9 = alias.
create or replace function resolve_product(q text)
returns table (product_id text, product_no int, sku text, name text, match_type text, score real)
language sql stable as $$
  with input as (
    select lower(trim(q)) as raw,
           -- question words removed, so "where is the box" is compared as "box"
           trim(regexp_replace(regexp_replace(lower(q),
             '\m(where|is|are|the|a|an|how|many|much|do|does|we|have|has|find|locate|show|me|my|of|in|on|at|stock|left|there|any|what|which|can|you|please|get|i|our|product|products|item|items)\M|[?!.,]',
             ' ', 'g'), '\s+', ' ', 'g')) as cleaned,
           coalesce(
             (regexp_match(q, '^\s*#?\s*(\d{1,7})\s*$'))[1],
             (regexp_match(q, '(?:product|item|prod|no\.?|number|num|#)\s*(?:no\.?|number|num|#)?\s*(\d{1,7})\M', 'i'))[1]
           )::int as num
  ),
  scored as (
    select p.*,
      i.raw like '%' || lower(p.sku) || '%'                     as hit_sku,
      i.raw like '%' || lower(p.id)  || '%'                     as hit_id,
      i.num is not null and p.product_no = i.num                as hit_no,
      exists (select 1 from unnest(p.aliases) a
               where i.raw ~ ('\m' || regexp_replace(lower(a), '([.^$*+?()\[\]{}|\\])', '\\\1', 'g') || '\M')) as hit_alias,
      case when i.cleaned ~ '[a-z]{2}' then
        greatest(similarity(lower(p.name), i.cleaned),
                 word_similarity(i.cleaned, lower(p.name)),
                 word_similarity(lower(p.name), i.cleaned))
      else 0 end                                                as name_sim
    from products p, input i where p.is_active
  )
  select s.id, s.product_no, s.sku, s.name,
         case when s.hit_sku or s.hit_id then 'sku'
              when s.hit_no    then 'product_no'
              when s.hit_alias then 'alias'
              else 'name' end,
         greatest(case when s.hit_sku or s.hit_id then 1.0 else 0 end,
                  case when s.hit_no    then 0.95 else 0 end,
                  case when s.hit_alias then 0.9  else 0 end,
                  s.name_sim)::real as score
  from scored s
  where s.hit_sku or s.hit_id or s.hit_no or s.hit_alias or s.name_sim >= 0.45
  order by score desc, s.product_no
  limit 5;
$$;

-- Safe stock change: updates stock_locations AND writes the audit row
-- in one transaction. Use this from the app/agents, never raw UPDATEs.
create or replace function move_stock(
  p_product_id text, p_quantity int, p_type movement_type,
  p_from_bin text default null, p_to_bin text default null,
  p_actor text default null, p_lot text default '', p_note text default null
) returns void language plpgsql as $$
begin
  if p_quantity <= 0 then raise exception 'quantity must be positive'; end if;

  if p_from_bin is not null then
    update stock_locations
       set quantity = quantity - p_quantity, updated_at = now()
     where product_id = p_product_id and bin_id = p_from_bin and lot_code = p_lot
       and quantity >= p_quantity;
    if not found then
      raise exception 'not enough % in bin %', p_product_id, p_from_bin;
    end if;
  end if;

  if p_to_bin is not null then
    insert into stock_locations (product_id, bin_id, quantity, lot_code)
    values (p_product_id, p_to_bin, p_quantity, p_lot)
    on conflict (product_id, bin_id, lot_code)
    do update set quantity = stock_locations.quantity + excluded.quantity, updated_at = now();
  end if;

  insert into stock_movements (product_id, from_bin_id, to_bin_id, quantity, type, actor, note)
  values (p_product_id, p_from_bin, p_to_bin, p_quantity, p_type, p_actor, p_note);
end $$;

-- ---------------------------------------------------------------------
--  LOCATION SEARCH
--  "where is rack 2?", "rack 2 on floor 3", "cold 3", "zone B floor 1",
--  "shelf 3 of crate 4", "the cold storage", "WH1-F2-Z01-R02".
--  If a rack name exists on several floors and no floor is given, every
--  match is returned with the same score so the agent can ask
--  "Rack 2 on Floor 1 or Floor 2?".
-- ---------------------------------------------------------------------
create or replace function resolve_location(q text)
returns table (location_id text, level text, label text, floor_id text, floor_name text,
               floor_level int, match_type text, score real)
language sql stable as $$
  with input as (
    select lower(q) as raw,
      upper((regexp_match(q, '(wh\d+-f\d+(?:-z\d{2}(?:-r\d{2}(?:-s\d{2}(?:-b\d{2})?)?)?)?)', 'i'))[1]) as exact_id,
      coalesce(
        (regexp_match(q, 'floor\s*(?:no\.?|number|#)?\s*(\d+)', 'i'))[1]::int,
        (regexp_match(q, '(\d+)\s*(?:st|nd|rd|th)?\s+floor', 'i'))[1]::int,
        case when q ~* '\m(ground|first)\s+floor' then 1
             when q ~* '\msecond\s+floor' then 2
             when q ~* '\mthird\s+floor'  then 3
             when q ~* '\mfourth\s+floor' then 4 end) as floor_level,
      (regexp_match(q, 'shelf\s*(?:no\.?|#)?\s*(\d+)', 'i'))[1]::int as shelf_level,
      (regexp_match(q, 'bin\s*(?:no\.?|#)?\s*(\d+)', 'i'))[1]::int   as bin_pos
  ),
  exact as (
    select l.*, 'id'::text as match_type, 1.0::real as score
    from v_locations l, input i
    where l.location_id = i.exact_id
  ),
  rack_hits as (
    select r.id as rack_id, r.floor_id
    from racks r, input i
    where i.exact_id is null
      and ( i.raw ~ ('\m' || regexp_replace(lower(r.name), '\s+', '\\s*#?\\s*', 'g') || '\M')
         or exists (select 1 from unnest(r.aliases) a
                     where i.raw ~ ('\m' || regexp_replace(lower(a), '([.^$*+?()\[\]{}|\\])', '\\\1', 'g') || '\M')) )
  ),
  rack_results as (
    -- narrow to shelf / bin when the user named them, else the rack itself
    select l.*, case when i.floor_level is not null then 'rack+floor' else 'rack' end as match_type,
           case when i.floor_level is not null then 1.0 else 0.9 end::real as score
    from rack_hits h
    cross join input i
    join v_locations l on l.location_id = coalesce(
          (select b.id from bins b join shelves s on s.id = b.shelf_id
            where s.rack_id = h.rack_id and s.level_index = i.shelf_level and b.position_index = i.bin_pos),
          (select s.id from shelves s where s.rack_id = h.rack_id and s.level_index = i.shelf_level),
          h.rack_id)
    where i.floor_level is null or l.floor_level = i.floor_level
  ),
  zone_results as (
    select l.*, 'zone'::text, 0.85::real
    from zones z
    join v_locations l on l.location_id = z.id
    cross join input i
    where i.exact_id is null
      and not exists (select 1 from rack_hits)
      and (i.floor_level is null or l.floor_level = i.floor_level)
      and ( i.raw ~ ('\m' || lower(split_part(z.name, ' — ', 1)) || '\M')
         or word_similarity(lower(split_part(z.name, ' — ', 2)), i.raw) >= 0.8 )
  ),
  -- vague words like "the shelf rack", "pallet racks", "freezers":
  -- return every rack of that kind (on the named floor, if any) so the
  -- agent can list them or ask which one.
  type_results as (
    select l.*, 'rack_type'::text, 0.6::real
    from (values ('\m(shelf|shelves|shelving)\M', 'shelf_unit'::rack_type),
                 ('\mpallets?\M',                 'pallet_grid'::rack_type),
                 ('\mcrates?\M',                  'crate_rack'::rack_type),
                 ('\m(cabinets?|freezers?|fridges?|cold)\M', 'cabinet'::rack_type)) as k(pattern, kind)
    cross join input i
    join racks r on r.type = k.kind
    join v_locations l on l.location_id = r.id
    where i.exact_id is null
      and i.raw ~ k.pattern
      and not exists (select 1 from rack_hits)
      and not exists (select 1 from zone_results)
      and (i.floor_level is null or l.floor_level = i.floor_level)
  ),
  floor_results as (
    select l.*, 'floor'::text, 0.8::real
    from v_locations l, input i
    where l.level = 'floor' and l.floor_level = i.floor_level
      and i.exact_id is null
      and not exists (select 1 from rack_hits)
      and not exists (select 1 from zone_results)
      and not exists (select 1 from type_results)
  )
  select location_id, level, label, floor_id, floor_name, floor_level, match_type, score
  from (select * from exact union all select * from rack_results
        union all select * from zone_results union all select * from type_results
        union all select * from floor_results) x
  order by score desc, floor_level, location_id
  limit 10;
$$;

-- Where a picker should walk to for any ID: nav node, rack/shelf/bin,
-- zone (its first rack), floor (its entrance/lift) or product (the bin
-- holding the most units).
create or replace function location_access_node(p_id text)
returns text language plpgsql stable as $$
declare v text;
begin
  if p_id is null then return null; end if;
  p_id := upper(trim(p_id));
  if p_id ~ '^PRD-\d{5}$' then
    select bin_id into p_id from v_product_locations
     where product_id = p_id order by quantity desc, floor_level limit 1;
    if p_id is null then return null; end if;
  end if;
  if p_id ~ '^WH\d+-F\d+-N\d{3}$' then
    select id into v from nav_nodes where id = p_id;
  elsif p_id ~ '^WH\d+-F\d+-Z\d{2}-R\d{2}' then
    select access_node_id into v from racks where id = substring(p_id from '^WH\d+-F\d+-Z\d{2}-R\d{2}');
  elsif p_id ~ '^WH\d+-F\d+-Z\d{2}$' then
    select access_node_id into v from racks where zone_id = p_id order by id limit 1;
  elsif p_id ~ '^WH\d+-F\d+$' then
    select id into v from nav_nodes where floor_id = p_id and type in ('entrance', 'lift', 'stairs')
     order by case type when 'entrance' then 0 when 'lift' then 1 else 2 end, id limit 1;
  end if;
  return v;
end $$;

-- ---------------------------------------------------------------------
--  ROUTING — Dijkstra over the whole building (all floors).
--  p_prefer: 'lift' (default — safe with goods/trolleys), 'stairs',
--  or 'fastest'. Returns the ordered path; `via` is how you ARRIVED at
--  each node (walk / lift / stairs). Empty result = no open route.
-- ---------------------------------------------------------------------
create or replace function find_route(p_from text, p_to text, p_prefer text default 'lift')
returns table (seq int, node_id text, floor_id text, floor_level int, x numeric, y numeric,
               node_type node_type, label text, via edge_type,
               segment_m numeric, total_m numeric, total_s numeric)
language plpgsql volatile as $$
#variable_conflict use_column
declare
  v_cur text; v_cost numeric; v_dist numeric;
begin
  perform set_config('client_min_messages', 'warning', true);  -- hide "temp table exists" notices
  if p_prefer not in ('lift', 'stairs', 'fastest') then
    raise exception 'p_prefer must be lift, stairs or fastest';
  end if;
  if not exists (select 1 from nav_nodes where id = p_from) then raise exception 'unknown start node %', p_from; end if;
  if not exists (select 1 from nav_nodes where id = p_to)   then raise exception 'unknown end node %', p_to; end if;

  create temp table if not exists _rt_edges (a text, b text, kind edge_type, dist numeric, cost numeric) on commit drop;
  create temp table if not exists _rt_dist (node text primary key, cost numeric, dist numeric, prev text,
                                            via edge_type, seg numeric, done boolean) on commit drop;
  truncate _rt_edges; truncate _rt_dist;

  insert into _rt_edges
  select e.from_node_id, e.to_node_id, e.edge_type, e.distance_m, e.cost_s from v_nav_edges e
   where not e.blocked
     and (p_prefer = 'fastest' or (p_prefer = 'lift' and e.edge_type <> 'stairs')
                               or (p_prefer = 'stairs' and e.edge_type <> 'lift'))
  union all
  select e.to_node_id, e.from_node_id, e.edge_type, e.distance_m, e.cost_s from v_nav_edges e
   where not e.blocked and e.bidirectional
     and (p_prefer = 'fastest' or (p_prefer = 'lift' and e.edge_type <> 'stairs')
                               or (p_prefer = 'stairs' and e.edge_type <> 'lift'));

  insert into _rt_dist values (p_from, 0, 0, null, null, 0, false);
  loop
    v_cur := null;
    select d.node, d.cost, d.dist into v_cur, v_cost, v_dist
      from _rt_dist d where not d.done order by d.cost limit 1;
    exit when v_cur is null or v_cur = p_to;
    update _rt_dist set done = true where node = v_cur;
    insert into _rt_dist (node, cost, dist, prev, via, seg, done)
    select distinct on (e.b) e.b, v_cost + e.cost, v_dist + e.dist, v_cur, e.kind, e.dist, false
      from _rt_edges e where e.a = v_cur
     order by e.b, e.cost
    on conflict (node) do update
      set cost = excluded.cost, dist = excluded.dist, prev = excluded.prev,
          via = excluded.via, seg = excluded.seg
      where _rt_dist.cost > excluded.cost and not _rt_dist.done;
  end loop;

  if not exists (select 1 from _rt_dist where node = p_to) then return; end if;

  return query
  with recursive path as (
    select d.node, d.prev, d.via, d.seg, d.dist, d.cost, 1 as depth from _rt_dist d where d.node = p_to
    union all
    select d.node, d.prev, d.via, d.seg, d.dist, d.cost, p.depth + 1
      from _rt_dist d join path p on d.node = p.prev
  )
  select (row_number() over (order by p.depth desc))::int, n.id, n.floor_id, f.level, n.x, n.y,
         n.type, n.label, p.via, round(p.seg, 1), round(p.dist, 1), round(p.cost, 0)
    from path p join nav_nodes n on n.id = p.node join floors f on f.id = n.floor_id
   order by p.depth desc;
end $$;

create or replace function _ordinal(n int) returns text language sql immutable as $$
  select n || case when n % 100 between 11 and 13 then 'th'
                   when n % 10 = 1 then 'st' when n % 10 = 2 then 'nd'
                   when n % 10 = 3 then 'rd' else 'th' end;
$$;

-- ---------------------------------------------------------------------
--  TURN-BY-TURN DIRECTIONS
--  p_target: product ID, any location ID (floor → bin) or nav node ID.
--  p_from:   same kinds of ID; default = the building's main entrance.
--  One row per instruction. The agent reads `instruction` aloud / in
--  chat; the UI uses node_ids + floor_id to highlight each step.
-- ---------------------------------------------------------------------
create or replace function get_directions(p_target text, p_from text default null, p_prefer text default 'lift')
returns table (step int, kind text, floor_id text, floor_name text, instruction text,
               distance_m numeric, total_s numeric, node_ids text[])
language plpgsql volatile as $$
#variable_conflict use_column
declare
  v_target text := upper(trim(p_target));
  v_to text; v_from text; v_note text; v_n int; i int; j int;
  acc numeric := 0; acc_nodes text[]; a record; b record; c record;
  ang numeric; v_turn text; v_rack record; v_shelf int; v_bin int; v_side text;
  v_step int := 0; v_total_s numeric;
begin
  if v_target ~ '^PRD-\d{5}$' then
    select bin_id into v_target from v_product_locations
     where product_id = upper(trim(p_target)) order by quantity desc, floor_level limit 1;
    if v_target is null then
      step := 1; kind := 'error'; instruction := format('%s is not in stock anywhere.', upper(p_target));
      return next; return;
    end if;
  end if;

  perform set_config('client_min_messages', 'warning', true);
  v_to := location_access_node(v_target);
  if v_to is null then
    step := 1; kind := 'error'; instruction := format('Unknown location %s.', p_target); return next; return;
  end if;

  v_from := location_access_node(p_from);
  if v_from is null then
    select n.id into v_from from nav_nodes n join floors f on f.id = n.floor_id
     where n.type = 'entrance' and f.warehouse_id = split_part(v_to, '-', 1)
     order by f.level, n.id limit 1;
  end if;

  create temp table if not exists _dir (seq int, node_id text, floor_id text, floor_level int, x numeric, y numeric,
    node_type node_type, label text, via edge_type, segment_m numeric, total_m numeric, total_s numeric) on commit drop;
  truncate _dir;
  insert into _dir select * from find_route(v_from, v_to, p_prefer);
  if not exists (select 1 from _dir) and p_prefer <> 'fastest' then
    insert into _dir select * from find_route(v_from, v_to, 'fastest');
    if exists (select 1 from _dir) then
      v_note := format('No open route using the %s, so this uses the fastest open route.', p_prefer);
    end if;
  end if;
  select count(*), max(total_s) into v_n, v_total_s from _dir;
  if v_n = 0 then
    step := 1; kind := 'error';
    instruction := 'No open route: an aisle, lift or stairway on the way is blocked.';
    return next; return;
  end if;

  -- start
  select * into a from _dir where seq = 1;
  v_step := v_step + 1; step := v_step; kind := 'start'; floor_id := a.floor_id;
  floor_name := (select name from floors where id = a.floor_id);
  instruction := format('Start at %s on %s.',
    coalesce((select r.name from racks r
               where r.id = substring(upper(p_from) from '^WH\d+-F\d+-Z\d{2}-R\d{2}')),
             a.label, 'your position'), floor_name);
  distance_m := 0; total_s := 0; node_ids := array[a.node_id]; return next;
  if v_note is not null then
    v_step := v_step + 1; step := v_step; kind := 'note'; instruction := v_note; return next;
  end if;

  acc_nodes := array[a.node_id];
  i := 2;
  while i <= v_n loop
    select * into a from _dir where seq = i - 1;
    select * into b from _dir where seq = i;

    if b.via in ('lift', 'stairs') then
      if acc >= 0.5 then
        v_step := v_step + 1; step := v_step; kind := 'walk'; floor_id := a.floor_id;
        floor_name := (select name from floors where id = a.floor_id);
        instruction := format('Walk %s m to %s.', round(acc), coalesce(a.label, 'the ' || b.via::text));
        distance_m := round(acc); total_s := a.total_s; node_ids := acc_nodes; return next;
      end if;
      j := i;
      while j < v_n and (select d.via from _dir d where d.seq = j + 1) = b.via loop j := j + 1; end loop;
      select * into c from _dir where seq = j;
      v_step := v_step + 1; step := v_step; kind := 'floor_change'; floor_id := c.floor_id;
      floor_name := (select name from floors where id = c.floor_id);
      instruction := format('Take %s %s to %s.', coalesce(a.label, initcap(b.via::text)),
                            case when c.floor_level > a.floor_level then 'up' else 'down' end, floor_name);
      distance_m := 0; total_s := c.total_s;
      node_ids := (select array_agg(d.node_id order by d.seq) from _dir d where d.seq between i - 1 and j);
      return next;
      acc := 0; acc_nodes := array[c.node_id]; i := j + 1;
      continue;
    end if;

    acc := acc + b.segment_m; acc_nodes := acc_nodes || b.node_id;
    if i < v_n then
      select * into c from _dir where seq = i + 1;
      if c.via = 'walk' then
        -- screen coordinates (y down): positive angle = right turn
        ang := degrees(atan2((b.x - a.x) * (c.y - b.y) - (b.y - a.y) * (c.x - b.x),
                             (b.x - a.x) * (c.x - b.x) + (b.y - a.y) * (c.y - b.y)));
        if abs(ang) > 35 then
          v_turn := case when abs(ang) > 150 then 'turn around'
                         when ang > 0 then 'turn right' else 'turn left' end;
          v_step := v_step + 1; step := v_step; kind := 'walk'; floor_id := b.floor_id;
          floor_name := (select name from floors where id = b.floor_id);
          instruction := format('Walk %s m%s, then %s.', round(acc),
                                case when b.label is not null then ' to ' || b.label else '' end, v_turn);
          distance_m := round(acc); total_s := b.total_s; node_ids := acc_nodes; return next;
          acc := 0; acc_nodes := array[b.node_id];
        end if;
      end if;
    end if;
    i := i + 1;
  end loop;

  -- final walk + arrival
  select * into b from _dir where seq = v_n;
  select * into a from _dir where seq = greatest(v_n - 1, 1);
  select r.id, r.name, z.name as zone_name, f.name as floor_name,
         r.x + r.width_m / 2 as cx, r.y + r.depth_m / 2 as cy
    into v_rack
    from racks r join zones z on z.id = r.zone_id join floors f on f.id = z.floor_id
   where r.id = substring(v_target from '^WH\d+-F\d+-Z\d{2}-R\d{2}');

  if acc >= 0.5 then
    v_step := v_step + 1; step := v_step; kind := 'walk'; floor_id := b.floor_id;
    floor_name := (select name from floors where id = b.floor_id);
    instruction := format('Walk %s m to %s.', round(acc), coalesce(v_rack.name, b.label, 'your destination'));
    distance_m := round(acc); total_s := b.total_s; node_ids := acc_nodes; return next;
  end if;

  v_step := v_step + 1; step := v_step; kind := 'arrive'; floor_id := b.floor_id;
  floor_name := (select name from floors where id = b.floor_id);
  distance_m := 0; total_s := v_total_s; node_ids := array[b.node_id];
  if v_rack.id is not null then
    v_side := 'in front of you';
    if v_n > 1 and (b.x <> a.x or b.y <> a.y) then
      ang := degrees(atan2((b.x - a.x) * (v_rack.cy - b.y) - (b.y - a.y) * (v_rack.cx - b.x),
                           (b.x - a.x) * (v_rack.cx - b.x) + (b.y - a.y) * (v_rack.cy - b.y)));
      v_side := case when abs(ang) <= 45 then 'straight ahead'
                     when abs(ang) >= 135 then 'behind you'
                     when ang > 0 then 'on your right' else 'on your left' end;
    end if;
    v_shelf := (substring(v_target from '-S(\d{2})'))::int;
    v_bin   := (substring(v_target from '-B(\d{2})'))::int;
    instruction := format('You have arrived. %s (%s, %s) is %s.', v_rack.name, v_rack.zone_name, v_rack.floor_name, v_side)
      || case when v_shelf is not null then format(' Go to shelf %s (%s level up from the floor)', v_shelf, _ordinal(v_shelf)) else '' end
      || case when v_bin is not null then format(', bin %s (%s from the left as you face the rack).', v_bin, _ordinal(v_bin))
              when v_shelf is not null then '.' else '' end;
  else
    instruction := format('You have arrived at %s.', coalesce(b.label, floor_name));
  end if;
  return next;
end $$;

-- Keeps the alerts table in sync with stock levels automatically.
create or replace function sync_stock_alerts() returns trigger language plpgsql as $$
declare
  v_product text := coalesce(new.product_id, old.product_id);
  v_bin     text := coalesce(new.bin_id, old.bin_id);
  t record;
  v_bin_units int;
  v_bin_cap   int;
begin
  select * into t from v_product_totals where product_id = v_product;
  if not found then return null; end if;   -- product itself is being deleted

  if t.is_out_of_stock then
    update alerts set resolved_at = now()
     where product_id = v_product and type = 'low_stock' and resolved_at is null;
    insert into alerts (type, level, product_id, message)
    values ('out_of_stock', 'critical', v_product, format('%s (%s) is out of stock', t.name, t.sku))
    on conflict do nothing;
  elsif t.is_low_stock then
    update alerts set resolved_at = now()
     where product_id = v_product and type = 'out_of_stock' and resolved_at is null;
    insert into alerts (type, level, product_id, message)
    values ('low_stock', 'warning', v_product,
            format('%s (%s): %s left, reorder point %s', t.name, t.sku, t.total_quantity, t.reorder_point))
    on conflict do nothing;
  else
    update alerts set resolved_at = now()
     where product_id = v_product and type in ('low_stock', 'out_of_stock') and resolved_at is null;
  end if;

  -- Bin over capacity check
  select coalesce(sum(quantity), 0), max(b.capacity_units) into v_bin_units, v_bin_cap
    from bins b left join stock_locations sl on sl.bin_id = b.id
   where b.id = v_bin;
  if v_bin_units > v_bin_cap and not exists (
       select 1 from alerts where bin_id = v_bin and type = 'bin_over_capacity' and resolved_at is null) then
    insert into alerts (type, level, bin_id, message)
    values ('bin_over_capacity', 'warning', v_bin,
            format('Bin %s holds %s units (capacity %s)', v_bin, v_bin_units, v_bin_cap));
  elsif v_bin_units <= v_bin_cap then
    update alerts set resolved_at = now()
     where bin_id = v_bin and type = 'bin_over_capacity' and resolved_at is null;
  end if;

  return null;
end $$;

create trigger stock_locations_alerts
after insert or update or delete on stock_locations
for each row execute function sync_stock_alerts();

-- =====================================================================
--  REALTIME (Supabase) — the UI listens to these tables
--  (nav_edges: when an aisle or the lift is blocked, routes are redrawn)
-- =====================================================================
do $$
begin
  if exists (select 1 from pg_publication where pubname = 'supabase_realtime') then
    alter publication supabase_realtime add table stock_locations, alerts, ui_commands, nav_edges;
  end if;
end $$;

-- =====================================================================
--  ROW LEVEL SECURITY
--  Front-end (anon/authenticated key): read-only.
--  Agents/back-end: use the service_role key (bypasses RLS) to write.
-- =====================================================================
do $$
declare t text;
begin
  foreach t in array array['warehouses','floors','zones','nav_nodes','nav_edges','racks','shelves',
                           'bins','products','stock_locations','stock_movements','alerts','ui_commands']
  loop
    execute format('alter table %I enable row level security', t);
    if exists (select 1 from pg_roles where rolname = 'authenticated') then
      execute format('create policy %I on %I for select to anon, authenticated using (true)',
                     t || '_read', t);
    end if;
  end loop;
end $$;

-- Views run with the caller's permissions so RLS still applies.
alter view v_product_locations set (security_invoker = true);
alter view v_product_totals    set (security_invoker = true);
alter view v_rack_fill         set (security_invoker = true);
alter view v_nav_edges         set (security_invoker = true);
alter view v_locations         set (security_invoker = true);
