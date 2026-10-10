"""Real PostgreSQL acceptance tests in disposable, randomly named schemas only.

RUN_INVENTORY_PG_TESTS=1 enables these against the configured twin connection.
No existing application/twin tables are modified.
"""
import os
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import text
from fastapi.testclient import TestClient

from database.twin import repository as repo
from database.twin.connection import get_engine, twin_connection
from database.twin.setup import ensure_twin_schema
from database.inventory_writes import update_placement, InventoryConflict
from agents.inventory_agent import tools as tools
from agents.inventory_agent.agent import handle_inventory_query_async
from database.models import Product
from config.settings import settings
from scripts.migrate_inventory import import_products

pytestmark = pytest.mark.skipif(os.getenv('RUN_INVENTORY_PG_TESTS')!='1',reason='opt in to isolated PostgreSQL acceptance tests')


@pytest.fixture
def inventory_pg(monkeypatch):
    schema = 'invtest_' + uuid.uuid4().hex
    monkeypatch.setattr(settings,'TWIN_DB_SCHEMA',schema)
    ensure_twin_schema(seed=True)
    try:
        yield schema
    finally:
        assert schema.startswith('invtest_') and len(schema)==40
        with get_engine().begin() as conn:
            conn.execute(text(f'drop schema "{schema}" cascade'))


def stock(ref):
    return tools.get_product_stock(None,ref).item


def test_lowest_stock_query_uses_authority(inventory_pg):
    result = tools.list_low_stock(None, selection='lowest_on_hand')
    assert result.total_checked == 12
    assert [(i.product_id, i.quantity_on_hand) for i in result.items] == [('PRD-00012', 0)]


def test_two_source_ids_map_to_one_product_without_doubling(inventory_pg):
    a=Product(id=5,sku='SKU-8001',name='Scanner',quantity=45,reserved_quantity=3,unit='units',reorder_point=50)
    first=import_products([a])[0][2]
    b=Product(id=5,sku='SKU-8001',name='Scanner',quantity=999,reserved_quantity=0,unit='units',reorder_point=50)
    assert import_products([b],source_system='supabase_public')[0][2]==first
    assert stock(first).quantity_on_hand==45
    with twin_connection() as c:
        assert c.execute(text('select count(*) from inventory_product_mappings')).scalar()==2
    ensure_twin_schema(seed=False)
    import_products([b],source_system='supabase_public')
    assert stock(first).quantity_on_hand==45


def test_selected_catalog_excludes_demo_everywhere_without_deleting(inventory_pg):
    from scripts.select_inventory_catalog import select_catalog
    rows=[Product(id=24,sku='SKU-4521',name='Actual scanner',quantity=340,reserved_quantity=10,
                  unit='units',reorder_point=60),
          Product(id=25,sku='SKU-7788',name='Actual printer',quantity=15,reserved_quantity=2,
                  unit='units',reorder_point=20)]
    select_catalog(rows)
    snap=repo.get_inventory_snapshot()
    assert {p['sku'] for p in snap['products']}=={'SKU-4521','SKU-7788'}
    assert snap['locations']==[]
    assert all(r['total_units']==0 and r['distinct_products']==0 for r in snap['rack_fill'])
    assert {a['product_id'] for a in snap['alerts']}=={'PRD-00014'}
    assert repo.resolve_product('HW-SCR-4X40')==[]
    assert tools.get_product_stock(None,'HW-SCR-4X40').status=='not_found'
    assert tools.query_inventory(None,'lowest stock').items[0].sku=='SKU-7788'
    with twin_connection() as c:
        assert c.execute(text('select count(*) from products')).scalar()==14
        assert c.execute(text('select count(*) from stock_locations')).scalar()==24
    ensure_twin_schema(seed=False)
    select_catalog(rows)
    assert len(repo.get_product_totals())==2


def test_inventory_reports_use_scoped_balances_and_current_snapshot(inventory_pg):
    summary=tools.query_inventory(None,'inventory summary')
    assert summary.status=='ok' and summary.matched_count==12 and summary.as_of
    assert 'Snapshot checked:' in summary.response and 'demo' in summary.response
    rank=tools.query_inventory(None,'lowest stock in WH1-F2')
    assert rank.status=='ok' and rank.location_scope=='WH1-F2'
    assert all(r['floor_id']=='WH1-F2' for i in rank.items for r in i.placements)
    for item in rank.items:
        assert item.quantity_on_hand==sum(r['quantity'] for r in item.placements)
    low=tools.query_inventory(None,'list low stock products')
    expected={p['product_id'] for p in repo.get_product_totals() if p['is_low_stock']}
    assert {i.product_id for i in low.items}==expected
    assert tools.query_inventory(None,'list products in warehouse 999').status=='empty'


def test_single_multiple_bins_floors_and_zero(inventory_pg):
    single = stock('HW-DRL-18V')
    assert single.product_id=='PRD-00004' and single.quantity_on_hand==22 and len(single.placements)==1
    multi = stock('PRD-00002')
    assert multi.quantity_on_hand==50 and len(multi.placements)==3
    assert len({r['floor_id'] for r in multi.placements})==2
    assert all(r['warehouse_name'] and r['bin_id'] in r['shelf_id']+'-B'+str(r['position_index']).zfill(2) for r in multi.placements)
    zero = stock('HW-SCR-4X40')
    assert zero.quantity_on_hand==0 and zero.available_quantity==0 and zero.status=='OUT_OF_STOCK'
    assert multi.data_source=='demo'
    assert tools.search_products(None,'charger').items[0].product_id=='PRD-00002'
    assert tools.search_products(None,'PRD-00002').items[0].sku=='EL-PWR-65W'
    assert tools.search_products(None,'EL-PWR-65W').status=='ok'
    with twin_connection() as c:
        c.execute(text("update products set aliases=array['charger'] where id='PRD-00001'"))
    assert tools.search_products(None,'charger').status=='ambiguous'


def test_lots_aggregate_once_and_multiple_warehouses(inventory_pg):
    with twin_connection() as c:
        c.execute(text("insert into stock_locations (product_id,bin_id,lot_code,quantity) values ('PRD-00002','WH1-F2-Z01-R02-S03-B04','LOT2',3)"))
        c.execute(text("insert into warehouses(id,name) values ('WH2','Second warehouse')"))
        c.execute(text("insert into floors values ('WH2-F1','WH2',1,'Floor 1',20,20)"))
        c.execute(text("insert into zones values ('WH2-F1-Z01','WH2-F1','Zone A','storage',0,0,10,10)"))
        c.execute(text("insert into racks(id,zone_id,name,type,x,y,width_m,depth_m) values ('WH2-F1-Z01-R01','WH2-F1-Z01','Rack 1','crate_rack',1,1,5,5)"))
        c.execute(text("insert into shelves(id,rack_id,level_index) values ('WH2-F1-Z01-R01-S01','WH2-F1-Z01-R01',1)"))
        c.execute(text("insert into bins(id,shelf_id,position_index) values ('WH2-F1-Z01-R01-S01-B01','WH2-F1-Z01-R01-S01',1)"))
        c.execute(text("insert into stock_locations(product_id,bin_id,quantity) values ('PRD-00002','WH2-F1-Z01-R01-S01-B01',7)"))
    item=stock('PRD-00002')
    assert item.quantity_on_hand==60 and len(item.placements)==4
    assert len({r['warehouse_id'] for r in item.placements})==2
    assert next(r['quantity'] for r in item.placements if r['bin_id']=='WH1-F2-Z01-R02-S03-B04')==33
    snap=repo.get_inventory_snapshot()
    total=next(p for p in snap['products'] if p['product_id']==item.product_id)
    assert total['bin_count']==4 and total['total_quantity']==sum(r['quantity'] for r in item.placements)


def test_equal_groups_use_aggregated_lots_and_exclude_missing_stock(inventory_pg):
    with twin_connection() as c:
        c.execute(text("update products set is_active=false"))
        c.execute(text("update products set is_active=true, unit='units' where id in ('PRD-00002','PRD-00004','PRD-00012')"))
        c.execute(text("insert into stock_locations (product_id,bin_id,lot_code,quantity) values ('PRD-00002','WH1-F2-Z01-R02-S03-B04','EXTRA',3)"))
        c.execute(text("update stock_locations set quantity=53 where product_id='PRD-00004'"))
        c.execute(text("insert into products (product_no,sku,name) values (99,'SKU-9999','No stock record')"))
    report=tools.query_inventory(None,'products with equal units')
    assert report.status=='ok'
    assert {i.product_id for i in report.items}=={'PRD-00002','PRD-00004'}
    assert all(i.quantity_on_hand==53 for i in report.items)
    assert report.missing_product_ids==['PRD-00099']
    assert '| Warehouse / floor locations |' in report.response
    scoped=tools.query_inventory(None,'products with equal units',selected_scope='WH1-F2')
    assert scoped.items==[] # Charger floor-2 balance is 45, drill is 53.
    assert scoped.status=='missing_data' # Unlocated product has no stock record; comparison completeness is unknown.


def test_migration_import_mapping_and_allocation_preserve_totals(inventory_pg):
    legacy = Product(id=901,sku='SKU-8001',name='Imported scanner',quantity=45,reserved_quantity=3,
                     unit='units',reorder_point=50,updated_at=datetime.now(timezone.utc))
    mapping=import_products([legacy])[0]
    pid=mapping[2]
    assert pid=='PRD-00013'
    ensure_twin_schema(seed=False)
    import_products([legacy])
    item=stock('SKU-8001')
    assert item.quantity_on_hand==45 and item.available_quantity==42 and item.unplaced_quantity==45
    assert item.data_source=='imported' and not item.placements
    assert any(a['product_id']==pid and a['type']=='low_stock' for a in repo.get_open_alerts())
    update_placement(product_id=pid,bin_id='WH1-F1-Z01-R01-S04-B06',lot_code='',quantity=20,
        reserved_quantity=0,quarantined_quantity=0,expected_updated_at=None,actor='test',allocate_unplaced=True)
    item=stock(pid)
    assert item.quantity_on_hand==45 and item.unplaced_quantity==25 and item.available_quantity==42
    assert len(item.placements)==1 and item.data_source=='imported'
    update_placement(product_id=pid,bin_id='WH1-F1-Z01-R01-S04-B05',lot_code='',quantity=25,
        reserved_quantity=3,quarantined_quantity=0,expected_updated_at=None,actor='test',allocate_unplaced=True)
    item=stock(pid)
    assert item.quantity_on_hand==45 and item.unplaced_quantity==0 and item.reserved_quantity==3 and item.available_quantity==42
    with twin_connection() as c:
        assert c.execute(text('select count(*) from inventory_product_mappings')).scalar()==1
        assert c.execute(text('select legacy_snapshot->>\'quantity\' from inventory_product_mappings')).scalar()=='45'


def test_update_reservations_quarantine_audit_stale_and_capacity(inventory_pg):
    with twin_connection() as c:
        before=c.execute(text("select updated_at from stock_locations where product_id='PRD-00002' and bin_id='WH1-F2-Z01-R02-S03-B04' and lot_code='' ")).scalar()
    args=dict(product_id='PRD-00002',bin_id='WH1-F2-Z01-R02-S03-B04',lot_code='',quantity=25,
              reserved_quantity=4,quarantined_quantity=6,expected_updated_at=before,actor='test')
    saved=update_placement(**args)
    item=stock('EL-PWR-65W')
    assert (item.quantity_on_hand,item.reserved_quantity,item.quarantined_quantity,item.available_quantity)==(45,4,6,35)
    assert item.data_source=='mixed'
    with pytest.raises(InventoryConflict): update_placement(**args)
    with pytest.raises(ValueError,match='capacity'): update_placement(**{**args,'quantity':999,'expected_updated_at':saved['updated_at']})
    assert stock('EL-PWR-65W').quantity_on_hand==45
    assert repo.get_movements('PRD-00002',1)[0]['actor']=='test'
    assert tools.get_stock_movements(None,sku='EL-PWR-65W').movements[0].quantity_change==5


def test_mcp_chat_context_and_failures(inventory_pg):
    import anyio
    from mcp_servers.mcp_tool_client import inventory_tool_gateway
    from mcp_servers.inventory_mcp_server import build_inventory_server
    # The real in-memory MCP server, never an LLM selecting the workflow.
    async def conversation():
        async with inventory_tool_gateway.session('inventory_agent') as session:
            first=await handle_inventory_query_async('check EL-PWR-65W stock',tools=session,
                thread_id='thread-test',session_id='tab-test',sku='EL-PWR-65W')
            assert first['items'], first
            assert first['items'][0]['quantity_on_hand']==50
            assert first['ui_command']['product_ids']==['PRD-00002']
            assert first['ui_command']['version'] in ('1.0','1.1')
            assert first['ui_command_id'] is not None
            second=await handle_inventory_query_async('is it available?',tools=session,
                conversation=first['context_update'],thread_id='thread-test')
            assert second['items'][0]['product_id']=='PRD-00002'
            assert 'demo' in second['response']
            denied=await session.call('unknown_stock_writer',{})
            assert denied.failed
    anyio.run(conversation)
    # An unavailable authority must not return application quantities.
    from unittest.mock import patch
    from database.twin.connection import TwinUnavailable
    with patch('database.inventory_source.snapshot',side_effect=TwinUnavailable('test outage')):
        with pytest.raises(TwinUnavailable): tools.get_product_stock(None,'SKU-4521')


def test_api_snapshot_write_authorization_and_conflicts(inventory_pg, monkeypatch):
    from backend.main import app
    # The map API is Professional / Enterprise; this test is about roles and conflicts
    monkeypatch.setattr('backend.twin.routes.get_user_plan', lambda *a, **k: 'professional')
    from inventory_testkit import auth, token_for
    client=TestClient(app)
    assert client.get('/twin/inventory-snapshot').status_code==401
    response=client.get('/twin/inventory-snapshot',headers=auth('inventory-test'))
    assert response.status_code==200
    assert response.json()['products'][1]['total_quantity']==stock('EL-PWR-65W').quantity_on_hand
    row=repo.get_stock_placements('PRD-00002')[0]
    payload={'product_id':row['product_id'],'bin_id':row['bin_id'],'lot_code':row['lot_code'],
             'quantity':row['quantity'],'reserved_quantity':1,'quarantined_quantity':0,
             'expected_updated_at':row['updated_at']}
    assert client.patch('/twin/stock-placement',json=payload,headers=auth('inventory-test')).status_code==403
    manager={'Authorization':'Bearer '+token_for('inventory-test',role='manager')}
    assert client.patch('/twin/stock-placement',json=payload,headers=manager).status_code==200
    assert client.patch('/twin/stock-placement',json=payload,headers=manager).status_code==409
    assert stock('PRD-00002').reserved_quantity==1


def test_api_thread_id_reaches_inventory_and_followups(inventory_pg,monkeypatch):
    from backend.main import app
    from inventory_testkit import auth
    import agents.inventory_agent.agent as agent_module
    legacy=Product(id=902,sku='SKU-8002',name='Thread scanner',quantity=12,reserved_quantity=2,
                   unit='units',reorder_point=1,updated_at=datetime.now(timezone.utc))
    import_products([legacy])
    captured=[]
    real=agent_module.handle_inventory_query_async
    async def capture(*args,**kwargs):
        captured.append(kwargs.get('thread_id'))
        return await real(*args,**kwargs)
    monkeypatch.setattr(agent_module,'handle_inventory_query_async',capture)
    client=TestClient(app)
    first=client.post('/query',json={'query':'How many SKU-8002 are on hand?'},headers=auth('thread-owner')).json()
    assert first['status']=='success' and first['persisted']
    second=client.post('/query',json={'query':'Where is it?','thread_id':first['thread_id']},headers=auth('thread-owner')).json()
    assert captured==[first['thread_id'],first['thread_id']]
    assert second['thread_id']==first['thread_id']
    assert second['inventory_details']['items'][0]['product_id']==first['inventory_details']['items'][0]['product_id']
