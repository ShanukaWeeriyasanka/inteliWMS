import pytest
from agents.fulfillment.extractor import extract_order_id

def test_extract_order_id_uppercase():
    assert extract_order_id("Status of ORD-1001") == "ORD-1001"

def test_extract_order_id_lowercase():
    assert extract_order_id("check order ord-25 please") == "ORD-25"

def test_extract_order_id_in_sentence():
    assert extract_order_id("Why is ORD-1001 delayed?") == "ORD-1001"

def test_extract_order_id_no_order_id():
    assert extract_order_id("Where is my order?") is None

def test_extract_order_id_invalid_ord_dash():
    assert extract_order_id("Here is ORD-") is None

def test_extract_order_id_invalid_ord_abc():
    assert extract_order_id("What about ORD-ABC?") is None

def test_extract_order_id_random_numbers():
    assert extract_order_id("Order 12345") is None

def test_extract_order_id_empty():
    assert extract_order_id("") is None
    assert extract_order_id(None) is None
