from sqlalchemy.orm import Session
from database.models import Order
from typing import Optional

def get_order_by_id(db: Session, order_id: str) -> Optional[Order]:
    """
    Retrieve an Order from the database by its exact order_id (e.g., 'ORD-1001').
    Returns None if the order does not exist.
    """
    if not order_id:
        return None
    
    return db.query(Order).filter(Order.order_id == order_id).first()

def get_order_status(db: Session, order_id: str) -> Optional[str]:
    """
    Retrieve the status of an order by its order_id.
    Returns None if the order does not exist.
    """
    order = get_order_by_id(db, order_id)
    if order:
        return order.status
    return None
