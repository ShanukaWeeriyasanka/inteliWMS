-- =====================================================================
--  DEMO SEED — Warehouse 1, three floors, connected by Lift A and
--  Stairs 1. Run AFTER schema.sql.  Units: metres (60 × 34 per floor).
--
--   Floor 1 (ground)  Main entrance + Dock A, bulk pallet racks, inbound crates
--   Floor 2           Pallet racks, crate racks, small-parts shelving units
--   Floor 3           Cold storage cabinets, small-parts shelving units
--
--  Rack names repeat across floors on purpose ("Rack 2" is on Floor 1
--  AND Floor 2) so you can test the "which floor?" clarification.
-- =====================================================================

insert into warehouses (id, name, address) values
  ('WH1', 'Warehouse 1', 'Colombo Logistics Park');

insert into floors (id, warehouse_id, level, name, width_m, height_m) values
  ('WH1-F1', 'WH1', 1, 'Floor 1', 60, 34),
  ('WH1-F2', 'WH1', 2, 'Floor 2', 60, 34),
  ('WH1-F3', 'WH1', 3, 'Floor 3', 60, 34);

insert into zones (id, floor_id, name, type, x, y, width_m, height_m) values
  ('WH1-F1-Z01', 'WH1-F1', 'Zone A — Bulk pallets',   'bulk',     4,  1, 56, 10),
  ('WH1-F1-Z02', 'WH1-F1', 'Zone B — Inbound crates', 'storage',  4, 22, 56, 10),
  ('WH1-F1-Z04', 'WH1-F1', 'Zone D — Dock & entrance','dock',     0, 12,  4, 10),
  ('WH1-F2-Z01', 'WH1-F2', 'Zone A — Pallets',        'storage',  4,  1, 56, 10),
  ('WH1-F2-Z02', 'WH1-F2', 'Zone B — Crates',         'storage',  4, 22, 22, 10),
  ('WH1-F2-Z03', 'WH1-F2', 'Zone C — Small parts',    'picking', 27, 22, 33, 10),
  ('WH1-F3-Z01', 'WH1-F3', 'Zone A — Cold storage',   'cold',     4,  1, 56, 10),
  ('WH1-F3-Z02', 'WH1-F3', 'Zone B — Small parts',    'picking',  4, 22, 56, 10);

-- ---------- Navigation graph: same aisle skeleton on every floor ----------
--   N001 lobby (F1: Main entrance)   N002 (F1: Dock A)
--   N003–N007 main aisle y=15        N008–N011 pallet/cold access y=11
--   N012–N018 lower aisle y=20       N019 charging bay
--   N020 Lift A (2,9)                N021 Stairs 1 (2,27)
do $$
declare
  f text; lvl int;
begin
  for f, lvl in select id, level from floors order by level loop
    insert into nav_nodes (id, floor_id, type, label, x, y) values
      (f || '-N001', f, (case when lvl = 1 then 'entrance' else 'aisle' end)::node_type,
                        case when lvl = 1 then 'Main entrance' else 'Lift lobby' end, 2, 15),
      (f || '-N002', f, (case when lvl = 1 then 'dock' else 'aisle' end)::node_type,
                        case when lvl = 1 then 'Dock A' end, 2, 20),
      (f || '-N003', f, 'intersection', null, 10, 15),
      (f || '-N004', f, 'intersection', null, 24, 15),
      (f || '-N005', f, 'intersection', null, 38, 15),
      (f || '-N006', f, 'intersection', null, 52, 15),
      (f || '-N007', f, 'aisle',        null, 58, 15),
      (f || '-N008', f, 'rack_access',  null, 10, 11),
      (f || '-N009', f, 'rack_access',  null, 24, 11),
      (f || '-N010', f, 'rack_access',  null, 38, 11),
      (f || '-N011', f, 'rack_access',  null, 52, 11),
      (f || '-N012', f, 'rack_access',  null,  8.5, 20),
      (f || '-N013', f, 'rack_access',  null, 15.5, 20),
      (f || '-N014', f, 'rack_access',  null, 22.5, 20),
      (f || '-N015', f, 'rack_access',  null, 30,   20),
      (f || '-N016', f, 'rack_access',  null, 35,   20),
      (f || '-N017', f, 'rack_access',  null, 42.5, 20),
      (f || '-N018', f, 'rack_access',  null, 54.5, 20),
      (f || '-N019', f, 'charging',     'Charging bay', 58, 20),
      (f || '-N020', f, 'lift',         'Lift A',   2,  9),
      (f || '-N021', f, 'stairs',       'Stairs 1', 2, 27);

    insert into nav_edges (from_node_id, to_node_id)
    select f || '-N' || a, f || '-N' || b
    from (values ('020','001'), ('002','001'), ('002','021'), ('002','012'),
                 ('001','003'), ('003','004'), ('004','005'), ('005','006'), ('006','007'), ('007','019'),
                 ('003','008'), ('004','009'), ('005','010'), ('006','011'),
                 ('003','012'), ('012','013'), ('013','014'), ('004','014'), ('014','015'),
                 ('015','016'), ('005','016'), ('016','017'), ('017','018'), ('006','018'),
                 ('018','019')) as e(a, b);
  end loop;
end $$;

-- Vertical connections between adjacent floors
insert into nav_edges (edge_type, from_node_id, to_node_id) values
  ('lift',   'WH1-F1-N020', 'WH1-F2-N020'),
  ('lift',   'WH1-F2-N020', 'WH1-F3-N020'),
  ('stairs', 'WH1-F1-N021', 'WH1-F2-N021'),
  ('stairs', 'WH1-F2-N021', 'WH1-F3-N021');

-- ---------- Racks ----------
insert into racks (id, zone_id, name, aliases, type, x, y, width_m, depth_m, access_node_id) values
  -- Floor 1
  ('WH1-F1-Z01-R01', 'WH1-F1-Z01', 'Rack 1',  '{}', 'pallet_grid',  6,  3, 8, 6, 'WH1-F1-N008'),
  ('WH1-F1-Z01-R02', 'WH1-F1-Z01', 'Rack 2',  '{}', 'pallet_grid', 20,  3, 8, 6, 'WH1-F1-N009'),
  ('WH1-F1-Z01-R03', 'WH1-F1-Z01', 'Rack 3',  '{}', 'pallet_grid', 34,  3, 8, 6, 'WH1-F1-N010'),
  ('WH1-F1-Z01-R04', 'WH1-F1-Z01', 'Rack 4',  '{}', 'pallet_grid', 48,  3, 8, 6, 'WH1-F1-N011'),
  ('WH1-F1-Z02-R01', 'WH1-F1-Z02', 'Crate 1', '{}', 'crate_rack',   6, 24, 5, 5, 'WH1-F1-N012'),
  ('WH1-F1-Z02-R02', 'WH1-F1-Z02', 'Crate 2', '{}', 'crate_rack',  13, 24, 5, 5, 'WH1-F1-N013'),
  ('WH1-F1-Z02-R03', 'WH1-F1-Z02', 'Crate 3', '{}', 'crate_rack',  20, 24, 5, 5, 'WH1-F1-N014'),
  ('WH1-F1-Z02-R04', 'WH1-F1-Z02', 'Crate 4', '{}', 'crate_rack',  40, 24, 5, 5, 'WH1-F1-N017'),
  ('WH1-F1-Z02-R05', 'WH1-F1-Z02', 'Crate 5', '{}', 'crate_rack',  52, 24, 5, 5, 'WH1-F1-N018'),
  -- Floor 2
  ('WH1-F2-Z01-R01', 'WH1-F2-Z01', 'Rack 1',  '{}', 'pallet_grid',  6,  3, 8, 6, 'WH1-F2-N008'),
  ('WH1-F2-Z01-R02', 'WH1-F2-Z01', 'Rack 2',  '{}', 'pallet_grid', 20,  3, 8, 6, 'WH1-F2-N009'),
  ('WH1-F2-Z01-R03', 'WH1-F2-Z01', 'Rack 3',  '{}', 'pallet_grid', 34,  3, 8, 6, 'WH1-F2-N010'),
  ('WH1-F2-Z01-R04', 'WH1-F2-Z01', 'Rack 4',  '{}', 'pallet_grid', 48,  3, 8, 6, 'WH1-F2-N011'),
  ('WH1-F2-Z02-R01', 'WH1-F2-Z02', 'Crate 1', '{}', 'crate_rack',   6, 24, 5, 5, 'WH1-F2-N012'),
  ('WH1-F2-Z02-R02', 'WH1-F2-Z02', 'Crate 2', '{}', 'crate_rack',  13, 24, 5, 5, 'WH1-F2-N013'),
  ('WH1-F2-Z02-R03', 'WH1-F2-Z02', 'Crate 3', '{}', 'crate_rack',  20, 24, 5, 5, 'WH1-F2-N014'),
  ('WH1-F2-Z03-R01', 'WH1-F2-Z03', 'Unit 1',  '{"shelf unit 1","shelving unit 1"}', 'shelf_unit', 28, 23, 4, 2, 'WH1-F2-N015'),
  ('WH1-F2-Z03-R02', 'WH1-F2-Z03', 'Unit 2',  '{"shelf unit 2","shelving unit 2"}', 'shelf_unit', 33, 23, 4, 2, 'WH1-F2-N016'),
  ('WH1-F2-Z03-R03', 'WH1-F2-Z03', 'Crate 4', '{}', 'crate_rack',  40, 24, 5, 5, 'WH1-F2-N017'),
  ('WH1-F2-Z03-R04', 'WH1-F2-Z03', 'Crate 5', '{}', 'crate_rack',  52, 24, 5, 5, 'WH1-F2-N018'),
  -- Floor 3
  ('WH1-F3-Z01-R01', 'WH1-F3-Z01', 'Cold 1',  '{"freezer 1"}', 'cabinet',  6,  3, 8, 6, 'WH1-F3-N008'),
  ('WH1-F3-Z01-R02', 'WH1-F3-Z01', 'Cold 2',  '{"freezer 2"}', 'cabinet', 20,  3, 8, 6, 'WH1-F3-N009'),
  ('WH1-F3-Z01-R03', 'WH1-F3-Z01', 'Cold 3',  '{"freezer 3"}', 'cabinet', 34,  3, 8, 6, 'WH1-F3-N010'),
  ('WH1-F3-Z01-R04', 'WH1-F3-Z01', 'Cold 4',  '{"freezer 4"}', 'cabinet', 48,  3, 8, 6, 'WH1-F3-N011'),
  ('WH1-F3-Z02-R01', 'WH1-F3-Z02', 'Unit 1',  '{"shelf unit 1","shelving unit 1"}', 'shelf_unit',  6, 23, 5, 3, 'WH1-F3-N012'),
  ('WH1-F3-Z02-R02', 'WH1-F3-Z02', 'Unit 2',  '{"shelf unit 2","shelving unit 2"}', 'shelf_unit', 13, 23, 5, 3, 'WH1-F3-N013'),
  ('WH1-F3-Z02-R03', 'WH1-F3-Z02', 'Unit 3',  '{"shelf unit 3","shelving unit 3"}', 'shelf_unit', 20, 23, 5, 3, 'WH1-F3-N014'),
  ('WH1-F3-Z02-R04', 'WH1-F3-Z02', 'Unit 4',  '{"shelf unit 4","shelving unit 4"}', 'shelf_unit', 40, 23, 5, 3, 'WH1-F3-N017'),
  ('WH1-F3-Z02-R05', 'WH1-F3-Z02', 'Unit 5',  '{"shelf unit 5","shelving unit 5"}', 'shelf_unit', 52, 23, 5, 3, 'WH1-F3-N018');

-- ---------- Shelves & bins, generated from rack type ----------
--   pallet_grid: 4 levels × 6 bins (50 units)   crate_rack: 3 × 4 (40)
--   shelf_unit : 5 levels × 3 bins (30 units)   cabinet   : 4 × 2 (20)
do $$
declare
  r record; lv int; pos int; n_levels int; n_bins int; cap int;
begin
  for r in select id, type from racks loop
    select l, b, c into n_levels, n_bins, cap
      from (values ('pallet_grid'::rack_type, 4, 6, 50),
                   ('crate_rack'::rack_type,  3, 4, 40),
                   ('shelf_unit'::rack_type,  5, 3, 30),
                   ('cabinet'::rack_type,     4, 2, 20)) as t(k, l, b, c)
     where k = r.type;
    for lv in 1..n_levels loop
      insert into shelves (id, rack_id, level_index, height_cm, max_weight_kg)
      values (r.id || '-S' || lpad(lv::text, 2, '0'), r.id, lv, 45, 500);
      for pos in 1..n_bins loop
        insert into bins (id, shelf_id, position_index, capacity_units)
        values (r.id || '-S' || lpad(lv::text, 2, '0') || '-B' || lpad(pos::text, 2, '0'),
                r.id || '-S' || lpad(lv::text, 2, '0'), pos, cap);
      end loop;
    end loop;
  end loop;
end $$;

-- ---------- Products ----------
insert into products (product_no, sku, name, aliases, category, weight_kg, reorder_point) values
  (1,  'EL-CBL-USB-C',   'USB-C Cable 1m',           '{"usb c","type c cable"}', 'Electronics', 0.05, 40),
  (2,  'EL-PWR-65W',     'Power Adapter 65W',        '{"charger","65w adapter"}', 'Electronics', 0.30, 25),
  (3,  'HW-BLT-M8',      'Hex Bolt M8 (box of 100)', '{"m8 bolts"}',              'Hardware',    1.20, 15),
  (4,  'HW-DRL-18V',     'Cordless Drill 18V',       '{"drill"}',                 'Tools',       1.80, 10),
  (5,  'PK-BOX-M',       'Shipping Box Medium',      '{"medium box","blue box"}', 'Packaging',   0.40, 100),
  (6,  'PK-TAPE-48',     'Packing Tape 48mm',        '{"tape"}',                  'Packaging',   0.25, 50),
  (7,  'FD-TEA-200',     'Ceylon Black Tea 200g',    '{"tea"}',                   'Food',        0.22, 60),
  (8,  'FD-COC-400',     'Coconut Milk 400ml',       '{"coconut milk"}',          'Food',        0.45, 60),
  (9,  'SF-GLV-L',       'Safety Gloves L',          '{"gloves"}',                'Safety',      0.10, 30),
  (10, 'SF-HLM-W',       'Safety Helmet White',      '{"helmet","hard hat"}',     'Safety',      0.40, 12),
  (11, 'EL-LED-9W',      'LED Bulb 9W',              '{"bulb","led"}',            'Electronics', 0.06, 80),
  (12, 'HW-SCR-4X40',    'Wood Screw 4x40 (box)',    '{"screws"}',                'Hardware',    0.60, 20);

-- ---------- Stock (via move_stock so movements + alerts are logged) ----------
select move_stock('PRD-00001', 30, 'receive', null, 'WH1-F2-Z03-R01-S02-B01', 'seed');
select move_stock('PRD-00001', 20, 'receive', null, 'WH1-F2-Z03-R01-S03-B02', 'seed');
select move_stock('PRD-00001', 15, 'receive', null, 'WH1-F2-Z03-R01-S03-B03', 'seed');
select move_stock('PRD-00002', 30, 'receive', null, 'WH1-F2-Z01-R02-S03-B04', 'seed');
select move_stock('PRD-00002', 12, 'receive', null, 'WH1-F2-Z03-R03-S01-B02', 'seed');
select move_stock('PRD-00002',  8, 'receive', null, 'WH1-F1-Z01-R01-S01-B01', 'seed');
select move_stock('PRD-00003', 10, 'receive', null, 'WH1-F1-Z02-R01-S02-B03', 'seed');   -- low stock
select move_stock('PRD-00004', 22, 'receive', null, 'WH1-F2-Z01-R03-S01-B05', 'seed');
select move_stock('PRD-00005', 50, 'receive', null, 'WH1-F1-Z01-R01-S01-B02', 'seed');
select move_stock('PRD-00005', 50, 'receive', null, 'WH1-F1-Z01-R01-S02-B01', 'seed');
select move_stock('PRD-00005', 35, 'receive', null, 'WH1-F1-Z01-R02-S01-B01', 'seed');
select move_stock('PRD-00006', 38, 'receive', null, 'WH1-F1-Z02-R02-S01-B01', 'seed');   -- low stock
select move_stock('PRD-00007', 30, 'receive', null, 'WH1-F3-Z02-R03-S02-B02', 'seed');
select move_stock('PRD-00007', 30, 'receive', null, 'WH1-F3-Z02-R03-S02-B03', 'seed');
select move_stock('PRD-00007', 20, 'receive', null, 'WH1-F3-Z02-R03-S03-B01', 'seed');
select move_stock('PRD-00008', 20, 'receive', null, 'WH1-F3-Z01-R03-S02-B02', 'seed');   -- low stock
select move_stock('PRD-00008',  5, 'receive', null, 'WH1-F3-Z01-R03-S03-B01', 'seed');
select move_stock('PRD-00009', 30, 'receive', null, 'WH1-F2-Z03-R02-S04-B01', 'seed');
select move_stock('PRD-00009', 30, 'receive', null, 'WH1-F2-Z03-R02-S04-B02', 'seed');
select move_stock('PRD-00010',  5, 'receive', null, 'WH1-F2-Z01-R04-S04-B06', 'seed');   -- low stock
select move_stock('PRD-00011', 30, 'receive', null, 'WH1-F2-Z03-R02-S01-B03', 'seed');
select move_stock('PRD-00011', 30, 'receive', null, 'WH1-F2-Z03-R02-S02-B03', 'seed');
select move_stock('PRD-00011', 30, 'receive', null, 'WH1-F2-Z03-R02-S03-B03', 'seed');
select move_stock('PRD-00012', 40, 'receive', null, 'WH1-F1-Z01-R02-S02-B03', 'seed');
-- PRD-00012 later gets fully picked → out-of-stock alert demo
select move_stock('PRD-00012', 40, 'pick', 'WH1-F1-Z01-R02-S02-B03', null, 'seed');
