import anyio
import pytest
from agents.coordinator.intent_classifier import IntentClassifier
from agents.inventory_agent.agent import handle_inventory_query_async
from agents.inventory_agent.report_queries import report_spec, evaluate_report


@pytest.mark.parametrize('query', [
    'lowest stock', 'highest stock', 'top 3 products by stock', 'inventory summary',
    'how many products do we have?', 'list all products', 'list low stock products',
    'show reserved stock', 'which products are quarantined?', 'show unassigned inventory',
    'total stock by category', 'list Electronics products', 'lowest available stock in warehouse 1',
    'heights stock', 'which product have highest number of units', 'which product has the most units?',
    'product with the greatest quantity', 'fewest units', 'bottom 2 products by stock',
    'which products have equal number of units', 'products with the same quantity',
    'which products have identical stock', 'products with more than 100 units',
    'show products with at least 10 available units',
    'products that have eqal number of units', 'items with the same stock quantity',
    'products with identical amounts', 'products whose quantities are identical',
    'products with eqal available quantities',
])
def test_catalog_questions_route_to_inventory(query):
    assert report_spec(query) is not None
    assert IntentClassifier(llm=None).match_rules(query)['domain']=='INVENTORY'


@pytest.mark.parametrize('query,expected', [
    ('lowest stock',['SKU-1003']), ('highest stock',['SKU-1004']),
    ('show reserved stock',['SKU-1001','SKU-1002','SKU-1004']),
    ('list products in category Electronics',['SKU-1001','SKU-1004']),
])
def test_reports_over_real_mcp(inventory_server,query,expected):
    r=anyio.run(lambda:handle_inventory_query_async(query))
    assert r['outcome']=='answered'
    assert sorted(i['sku'] for i in r['items'])==sorted(expected)
    assert 'Snapshot checked:' in r['response']


@pytest.mark.parametrize('query', ['heights stock', 'which product have highest number of units'])
def test_screenshot_rankings_ignore_old_product_context(inventory_server, query):
    r=anyio.run(lambda:handle_inventory_query_async(query, conversation={
        'skus':['HW-SCR-4X40'], 'product_ids':['PRD-00012'], 'last_sub_intent':'stock_check'}))
    assert r['outcome']=='answered'
    assert [i['sku'] for i in r['items']]==['SKU-1004']
    assert r['items'][0]['quantity_on_hand']==340
    assert 'HW-SCR-4X40' not in r['response']


def test_unrecognized_short_question_does_not_borrow_old_sku(inventory_server):
    r=anyio.run(lambda:handle_inventory_query_async('mysterious gadget', conversation={
        'skus':['HW-SCR-4X40'], 'product_ids':['PRD-00012']}))
    assert r['outcome']=='needs_product'
    assert r['items']==[]
    assert 'HW-SCR-4X40' not in r['response']


def test_summary_keeps_units_separate(inventory_server):
    r=anyio.run(lambda:handle_inventory_query_async('inventory summary'))
    assert r['outcome']=='answered'
    assert '355 on hand' in r['response'] # 15 printer units + 340 scanner units
    assert '120 on hand' in r['response'] # rolls, not mixed into units
    assert '8 on hand' in r['response'] # kits


def test_rank_reserved_includes_zero_commitments(inventory_server):
    r=anyio.run(lambda:handle_inventory_query_async('lowest reserved stock'))
    assert r['outcome']=='answered'
    assert {i['sku'] for i in r['items']}=={'SKU-1003','SKU-1005'}


def test_unavailable_location_does_not_return_global(inventory_server):
    r=anyio.run(lambda:handle_inventory_query_async('lowest stock in warehouse 999'))
    assert r['outcome']=='empty' and r['items']==[]
    assert 'WH999' in r['response']


def test_unsupported_category_does_not_return_all_products(inventory_server):
    r=anyio.run(lambda:handle_inventory_query_async('list products in category Unknown'))
    assert r['outcome']=='invalid_request' and r['items']==[]


def test_ambiguous_floor_requires_warehouse():
    result=evaluate_report('lowest stock on floor 1',[],[],{
        'floors':[{'id':'WH1-F1','warehouse_id':'WH1'},{'id':'WH2-F1','warehouse_id':'WH2'}]})
    assert result['status']=='ambiguous'


def test_equal_quantity_groups_over_mcp(inventory_server):
    from database.models import Product
    with inventory_server() as db:
        for sku in ('SKU-1001','SKU-1004'):
            db.query(Product).filter(Product.sku==sku).update({'quantity':15})
        # Same number of rolls must not be presented as equal physical units.
        db.query(Product).filter(Product.sku=='SKU-1002').update({'quantity':15})
        db.commit()
    r=anyio.run(lambda:handle_inventory_query_async('which products have equal number of units',
        conversation={'skus':['HW-SCR-4X40']}))
    assert r['outcome']=='answered'
    assert {i['sku'] for i in r['items']}=={'SKU-1001','SKU-1004'}
    assert '15 units on-hand each' in r['response']
    assert 'Snapshot checked:' in r['response']


def test_equal_quantity_no_matches(inventory_server):
    r=anyio.run(lambda:handle_inventory_query_async('products with the same quantity'))
    assert r['outcome']=='empty' and r['items']==[]
    assert 'No products share' in r['response']


def test_equal_reserved_includes_zero(inventory_server):
    r=anyio.run(lambda:handle_inventory_query_async('which products have equal reserved units'))
    # Both zero-reserved products have different units (rolls and kits).
    assert r['outcome']=='empty'


@pytest.mark.parametrize('query,expected', [
    ('products with more than 100 units', {'SKU-1002','SKU-1004'}),
    ('show products with at least 100 available units', {'SKU-1002','SKU-1004'}),
    ('products with exactly 0 units', {'SKU-1003'}),
    ('products with fewer than 8 units', {'SKU-1003'}),
    ('products with at most 8 units', {'SKU-1003','SKU-1005'}),
])
def test_numeric_stock_filters(inventory_server, query, expected):
    r=anyio.run(lambda:handle_inventory_query_async(query))
    assert r['outcome']=='answered'
    assert {i['sku'] for i in r['items']}==expected


def test_scoped_equality_uses_bin_balances_once():
    products=[dict(product_id=id,sku=id,name=id,unit='units',total_quantity=50,
                   available_quantity=50,reserved_quantity=0,quarantined_quantity=0,
                   unplaced_quantity=0,reorder_point=5) for id in ('A','B','C')]
    locations=[dict(product_id=id,bin_id='WH1-F1-Z01-R01-S01-B'+str(n),quantity=qty,
                    available_quantity=qty,reserved_quantity=0,quarantined_quantity=0,
                    updated_at='2026-10-09') for n,(id,qty) in enumerate([('A',2),('A',3),('B',5),('C',7)])]
    r=evaluate_report('which products have the same stock in warehouse 1', products, locations,
                      {'warehouses':[{'id':'WH1','name':'Main warehouse'}]})
    assert {p['product_id'] for p in r['products']}=={'A','B'}
    assert all(p['total_quantity']==5 for p in r['products'])


def test_equal_zero_commitments_are_real_matches():
    products=[dict(product_id=id,sku=id,name=id,unit='units',total_quantity=qty,
                   available_quantity=qty,reserved_quantity=0,quarantined_quantity=0,
                   unplaced_quantity=0,reorder_point=5) for id,qty in [('A',3),('B',9)]]
    r=evaluate_report('products with equal reserved quantities', products, [])
    assert r['status']=='ok'
    assert {p['product_id'] for p in r['products']}=={'A','B'}


def _row(pid, quantity, **extra):
    return dict(product_id=pid,sku=pid,name=pid,unit='units',total_quantity=quantity,
                available_quantity=quantity,reserved_quantity=0,quarantined_quantity=0,
                unplaced_quantity=0,reorder_point=5,updated_at='2026-10-09T00:00:00+00:00',
                stock_updated_at='2026-10-08T00:00:00+00:00',data_source='imported',**extra)


def test_missing_records_are_not_zero_groups():
    r=evaluate_report('products with equal units',[_row('A',0,stock_recorded=False),
                      _row('B',None)],[])
    assert r['status']=='missing_data' and r['products']==[]
    assert set(r['missing_product_ids'])=={'A','B'}


def test_zero_groups_are_separate_and_duplicate_products_not_counted_twice():
    p=_row('A',0)
    r=evaluate_report('products with equal units',[p,p,_row('B',0),_row('C',9)],[])
    assert [p['product_id'] for p in r['products']]==['A','B']
    assert r['unit_totals']['units']['total_quantity']==0


def test_exact_numeric_comparison():
    from decimal import Decimal
    r=evaluate_report('products with equal units',[_row('A',Decimal('1.000000000000001')),
                      _row('B',Decimal('1.000000000000002'))],[])
    assert r['status']=='empty'


def test_scope_selection_and_explicit_override():
    layout={'warehouses':[{'id':'WH1','name':'First'},{'id':'WH2','name':'Second'}]}
    for query, expected in [('products with equal units','WH2'),('products with equal units in warehouse 1','WH1')]:
        r=evaluate_report(query,[],[],layout,selected_scope='WH2')
        assert r['location_scope']==expected


def test_mcp_missing_data_and_freshness_are_distinct(inventory_server, monkeypatch):
    from agents.inventory_agent import tools
    from database.twin import repository
    monkeypatch.setattr(tools.authority,'uses_twin',lambda:True)
    snapshot={'products':[_row('PRD-00001',0,stock_recorded=False),_row('PRD-00002',0,stock_recorded=False)],
              'locations':[], 'as_of':'2026-10-09T12:00:00+00:00'}
    monkeypatch.setattr(tools.authority,'snapshot',lambda:snapshot)
    monkeypatch.setattr(repository,'get_layout',lambda:{})
    r=anyio.run(lambda:handle_inventory_query_async('products with equal units'))
    assert r['outcome']=='missing_data'
    assert 'missing data is not zero stock' in r['response']
    assert 'No products share' not in r['response']


def test_table_and_source_freshness(inventory_server, monkeypatch):
    from agents.inventory_agent import tools
    from database.twin import repository
    from types import SimpleNamespace
    monkeypatch.setattr(tools.authority,'uses_twin',lambda:True)
    snapshot={'products':[_row('PRD-00001',0,stock_recorded=True),_row('PRD-00002',0,stock_recorded=True)],
              'locations':[], 'as_of':'2026-10-09T12:00:00+00:00'}
    monkeypatch.setattr(tools.authority,'snapshot',lambda:snapshot)
    monkeypatch.setattr(repository,'get_layout',lambda:{})
    with inventory_server() as db:
        r=tools.query_inventory(db,'products with equal units')
        assert '| Product ID | Product name | Quantity | Unit | Warehouse / floor locations |' in r.response
        assert 'Confirmed zero-stock group' in r.response
        assert r.source_updated_at=='2026-10-08T00:00:00+00:00'
        assert r.freshness=='recorded'
        monkeypatch.setattr(tools,'inventory_config',SimpleNamespace(STOCK_MAX_AGE_SECONDS=1,DEFAULT_SAFETY_STOCK=15,DEFAULT_REORDER_QUANTITY=100))
        stale=tools.query_inventory(db,'products with equal units')
        assert stale.freshness=='stale'


@pytest.mark.parametrize('status', ['timeout','unavailable','tool_error'])
def test_equal_query_tool_failures_never_ask_for_sku(status):
    from mcp_servers.mcp_tool_client import ToolResult,ToolStatus
    from agents.inventory_agent.tool_contracts import QUERY_INVENTORY
    class FailedTools:
        async def call(self,tool,args):
            assert tool==QUERY_INVENTORY
            assert args['intent']['operation']=='equal'
            return ToolResult(tool=tool,status=ToolStatus(status),error_code='TEST_FAILURE')
    r=anyio.run(lambda:handle_inventory_query_async('products with equal units',tools=FailedTools(),thread_id='test-thread'))
    assert r['outcome']=='error' and r['items']==[]
    assert 'Which product' not in r['response']


def test_structured_interpretation_is_validated_and_cannot_select_tools():
    from agents.inventory_agent.report_queries import interpret_collection_language
    valid='{"kind":"collection","confidence":0.95,"operation":"equal"}'
    plan=interpret_collection_language('products with equivalent holdings',lambda prompt:valid)
    assert plan['operation']=='equal' and plan['metric']=='total_quantity'
    for invalid in ['{"kind":"collection","confidence":0.2,"operation":"equal"}',
                    '{"kind":"collection","confidence":0.95,"operation":"delete"}',
                    '{"kind":"collection","confidence":0.95,"operation":"equal","tool":"delete"}', 'not json']:
        assert interpret_collection_language('products with equivalent holdings',lambda prompt:invalid) is None


def test_unfamiliar_paraphrase_executes_validated_collection_flow(inventory_server, monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr('config.llm_config.llm_config',SimpleNamespace(gemini_key='test',groq_key=None,
        hybrid_complete=lambda **kw:'{"kind":"collection","confidence":0.95,"operation":"equal"}'))
    r=anyio.run(lambda:handle_inventory_query_async('products with equivalent holdings'))
    assert r['sub_intent']=='inventory_report' and r['outcome']=='empty'
    assert 'Which product' not in r['response']


def test_available_comparison_does_not_use_on_hand():
    a,b=_row('A',10),_row('B',20)
    a['available_quantity']=b['available_quantity']=5
    assert evaluate_report('products with equal units',[a,b],[])['status']=='empty'
    result=evaluate_report('products with equal available units',[a,b],[])
    assert result['status']=='ok' and len(result['products'])==2


def test_equality_limit_keeps_complete_groups():
    rows=[_row(str(n),4) for n in range(25)]
    result=evaluate_report('products with equal units',rows,[])
    assert result['returned_count']==25 # A group cannot be cut at the default limit of 20.
