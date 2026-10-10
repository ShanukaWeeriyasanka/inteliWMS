"""
Inventory question autocomplete: suggestions are grounded in the seeded catalog, route to the
Inventory Agent unchanged, never state stock facts, and the endpoint is read-only and auth-gated.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func

from agents.inventory_agent import suggestions as S
from agents.inventory_agent.intents import detect_sub_intent
from agents.inventory_agent.suggestions import build_suggestions, routes_to_inventory
from backend.main import app
from database.connection import get_db
from database.models import InventoryTransaction, Product
from inventory_testkit import PRODUCTS, auth, token_for

FLOORS = [{"id": "WH1-F1", "level": 1}, {"id": "WH1-F2", "level": 2}, {"id": "WH1-F3", "level": 3}]
CATALOG = S._catalog_from_rows(
    [{"sku": sku, "name": f["name"], "category": f["category"]} for sku, f in PRODUCTS.items()], FLOORS)


def asks_rather_than_claims(text):
    """A question, or a Show/List request — never a statement such as 'SKU-1001 is low'."""
    return text.endswith("?") or text.startswith(("Show ", "List "))


def texts(query, catalog=CATALOG):
    return [s["text"] for s in build_suggestions(query, catalog)]


# ── Builder ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("query", ["sto", "stock", "STO", "stok", "quantty", "qty", "how many"])
def test_stock_words_and_synonyms_suggest_stock_questions(query):
    out = texts(query)
    assert 3 <= len(out) <= 5
    assert any("stock" in t.lower() for t in out)


def test_low_suggests_low_stock_questions():
    out = texts("low")
    assert out[0] == "Which products are low on stock?"
    assert "Which products need restocking?" in out


def test_product_name_prefix_suggests_matching_products_only():
    out = build_suggestions("therm", CATALOG)
    assert 3 <= len(out) <= 5
    assert {s["sku"] for s in out} == {"SKU-1001", "SKU-1002"}
    assert all("Thermal" in s["text"] or s["sku"] in s["text"] for s in out)


def test_sku_suggests_that_product_first():
    out = build_suggestions("SKU-1004", CATALOG)
    assert out[0]["text"] == "What is the current stock of Wireless Barcode Scanner (SKU-1004)?"
    assert {s["sku"] for s in out} == {"SKU-1004"}


def test_case_insensitive_and_partial_sku():
    assert texts("sku-1004") == texts("SKU-1004")
    assert any("SKU-1003" in t for t in texts("1003"))


def test_typed_topic_reorders_product_questions():
    assert texts("where is the scan")[0] == "Where is Wireless Barcode Scanner (SKU-1004) stored?"
    assert texts("is wireless avail")[0] == "Is Wireless Barcode Scanner (SKU-1004) available?"


def test_category_and_floor_come_from_the_catalog():
    assert texts("elec")[0] == "List products in category Electronics"
    assert texts("floor 2")[0] == "Which product has the lowest stock in WH1-F2?"
    assert not any("category Food" in t for t in texts("category"))  # not in this catalog


@pytest.mark.parametrize("query", ["apply for leave", "leave request", "track order #4521", "where is the delivery",
                                   "hi", "thanks", "what is the policy", "hello there", "x", " a "])
def test_unrelated_text_gets_no_suggestions(query):
    assert build_suggestions(query, CATALOG) == []


def test_an_order_number_does_not_pull_in_a_product_with_the_same_digits():
    catalog = S._catalog_from_rows([{"sku": "SKU-4521", "name": "Wireless Barcode Scanner", "category": "Tech"}], [])
    assert texts("track order #4521", catalog) == []
    assert texts("where is order 4521", catalog) == []
    assert texts("4521", catalog)  # on its own, the number may still be a SKU
    assert texts("is SKU-4521 delivered", catalog)  # an explicit SKU still names the product


def test_only_categories_the_agent_can_resolve_are_offered():
    catalog = S._catalog_from_rows([{"sku": "SKU-1", "name": "A", "category": "Equipment"},
                                    {"sku": "SKU-2", "name": "B", "category": "Equipment Parts"}], [])
    out = texts("equipm", catalog)
    assert "List products in category Equipment Parts" in out
    assert "List products in category Equipment" not in out


def test_results_are_unique_capped_and_never_claim_facts():
    for query in ["sto", "low", "therm", "SKU-1001", "out of", "reord", "summary", "where", "movements", "1003"]:
        out = texts(query)
        assert len(out) == len({t.casefold() for t in out}) <= 5
        assert all(asks_rather_than_claims(t) for t in out), out


def test_every_template_routes_to_the_inventory_agent_with_its_sub_intent():
    for sku, fields in PRODUCTS.items():
        label, ref = S._label({"sku": sku, "name": fields["name"]})
        for template in S.PRODUCT_TEMPLATES:
            # A name the coordinator reads as another domain ("Hazmat ...") falls back to the SKU alone
            shown = S._routed(template.text.format(label=label, ref=ref), template.sub_intent,
                              template.text.format(label=ref, ref=ref))
            assert shown and routes_to_inventory(shown, template.sub_intent), (template.id, sku)
    for template in S.GENERIC_TEMPLATES:
        assert routes_to_inventory(template.text, template.sub_intent), template.id
    for category in CATALOG["categories"]:
        assert routes_to_inventory(S.CATEGORY_TEMPLATE.text.format(category=category), "inventory_report")
    for floor in FLOORS:
        assert routes_to_inventory(S.FLOOR_TEMPLATE.text.format(floor=floor["id"]), "lowest_stock")


def test_product_names_that_would_misroute_fall_back_to_the_sku():
    catalog = S._catalog_from_rows([{"sku": "SKU-7001", "name": "Order Picker Gloves", "category": "Safety"}], [])
    out = texts("order picker", catalog)
    assert out and all(routes_to_inventory(t, detect_sub_intent(t)) for t in out)
    assert all("Order Picker" not in t for t in out)


def test_without_a_catalog_only_capability_questions_are_offered():
    assert texts("sto", None)  # generic stock questions still work
    assert texts("therm", None) == []  # no invented product
    assert all(t.count("SKU-") <= 1 and "SKU-1004" in t for t in texts("SKU-1004", None))


# ── Endpoint ────────────────────────────────────────────────────────────────

@pytest.fixture
def client(inventory_server):
    def _db():
        session = inventory_server()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _db
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)


def test_endpoint_requires_sign_in(client):
    response = client.get("/inventory/suggestions", params={"q": "sto"})
    assert response.status_code == 401
    assert response.json()["error_code"] == "AUTH_REQUIRED"


def test_endpoint_respects_inventory_permission(client, monkeypatch):
    monkeypatch.setattr("backend.routes.inventory_suggestions.rbac_manager.check_permission",
                        lambda role, action: False)
    response = client.get("/inventory/suggestions", params={"q": "sto"}, headers=auth("u1"))
    assert response.status_code == 403


def test_endpoint_rejects_too_short_text(client):
    assert client.get("/inventory/suggestions", params={"q": "s"}, headers=auth("u1")).status_code == 422


@pytest.mark.parametrize("role", ["staff", "manager", "admin"])
def test_endpoint_suggests_from_the_seeded_catalog(client, role):
    headers = {"Authorization": f"Bearer {token_for('u1', role=role)}"}
    body = client.get("/inventory/suggestions", params={"q": "SKU-1004"}, headers=headers).json()
    assert body["degraded"] is False
    assert body["suggestions"][0]["text"] == "What is the current stock of Wireless Barcode Scanner (SKU-1004)?"
    unrelated = client.get("/inventory/suggestions", params={"q": "apply for leave"}, headers=headers).json()
    assert unrelated["suggestions"] == []


def test_endpoint_falls_back_to_generic_questions_when_lookup_fails(client, monkeypatch):
    def boom(db):
        raise RuntimeError("database down")

    monkeypatch.setattr(S, "_legacy_catalog", boom)
    body = client.get("/inventory/suggestions", params={"q": "sto"}, headers=auth("u1")).json()
    assert body["degraded"] is True
    assert body["suggestions"] and all("SKU-" not in s["text"] for s in body["suggestions"])
    assert client.get("/inventory/suggestions", params={"q": "therm"}, headers=auth("u1")).json()["suggestions"] == []


def test_endpoint_never_writes(client, inventory_server):
    def counts():
        with inventory_server() as s:
            return (s.query(func.count(Product.id)).scalar(), s.query(func.sum(Product.quantity)).scalar(),
                    s.query(func.count(InventoryTransaction.id)).scalar())

    before = counts()
    for q in ["sto", "low", "therm", "SKU-1004", "reorder", "where is the scan"]:
        assert client.get("/inventory/suggestions", params={"q": q}, headers=auth("u1")).status_code == 200
    assert counts() == before
