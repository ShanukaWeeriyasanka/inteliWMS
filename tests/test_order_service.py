import pytest
from sqlalchemy.orm import Session
from agents.fulfillment.order_service import get_order_by_id, get_order_status
from database.connection import SessionLocal

@pytest.fixture(scope="module")
def db_session():
    """Provides a database session for tests. Read-only usage only."""
    db = SessionLocal()
    yield db
    db.close()

def test_get_order_by_id_exists(db_session: Session):
    # Test 1 & 2: Retrieve a known existing Order ID and verify
    order = get_order_by_id(db_session, "ORD-1001")
    assert order is not None, "Expected ORD-1001 to exist in the database"
    assert order.order_id == "ORD-1001"
    
def test_get_order_by_id_non_existent(db_session: Session):
    # Test 3: Query a non-existing Order ID and verify None is returned
    order = get_order_by_id(db_session, "ORD-99999999")
    assert order is None

def test_get_order_by_id_consistency(db_session: Session):
    # Test 4: Perform the same lookup multiple times and verify consistent data
    order_1 = get_order_by_id(db_session, "ORD-1002")
    order_2 = get_order_by_id(db_session, "ORD-1002")
    
    assert order_1 is not None
    assert order_2 is not None
    assert order_1.id == order_2.id
    assert order_1.order_id == order_2.order_id
    assert order_1.status == order_2.status

def test_get_order_status_exists(db_session: Session):
    status = get_order_status(db_session, "ORD-1001")
    assert status is not None
    assert isinstance(status, str)

def test_get_order_status_non_existent(db_session: Session):
    status = get_order_status(db_session, "ORD-99999999")
    assert status is None
