import anyio
import pytest
from sqlalchemy import update

from agents.coordinator.intent_classifier import IntentClassifier
from agents.inventory_agent.agent import handle_inventory_query_async
from agents.inventory_agent.intents import detect_sub_intent
from agents.inventory_agent.tools import list_low_stock
from database.models import Product


@pytest.mark.parametrize('query', [
    'which product have the lowest stocks',
    'which product has the lowest stock?',
    'which products have the least quantity?',
])
def test_lowest_stock_routes_without_llm(query):
    result = IntentClassifier(llm=None).match_rules(query)
    assert result['domain'] == 'INVENTORY'
    assert detect_sub_intent(query) == 'lowest_stock'


def test_lowest_answer_includes_real_zero(inventory_server):
    response = anyio.run(lambda: handle_inventory_query_async('which product have the lowest stocks'))
    assert response['outcome'] == 'answered'
    assert response['sub_intent'] == 'lowest_stock'
    assert [i['sku'] for i in response['items']] == ['SKU-1003']
    assert response['items'][0]['quantity_on_hand'] == 0


def test_minimum_is_not_reorder_filter_and_preserves_ties(inventory_server):
    with inventory_server() as db:
        db.execute(update(Product).values(quantity=30, reorder_point=1))
        db.execute(update(Product).where(Product.sku.in_(['SKU-1001','SKU-1002'])).values(quantity=25))
        db.commit()
        assert list_low_stock(db).status == 'empty'
        result = list_low_stock(db, selection='lowest_on_hand')
        assert {i.sku for i in result.items} == {'SKU-1001','SKU-1002'}
        assert result.total_checked == 5
        db.query(Product).delete()
        db.commit()
        assert list_low_stock(db, selection='lowest_on_hand').status == 'empty'
