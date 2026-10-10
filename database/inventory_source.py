"""Inventory's authoritative read model; configured PostgreSQL never falls back on failure.

The application database remains available to other agents. Inventory reads the twin
when configured, including explicitly unplaced imported stock. No balances are merged
with application quantities at query time.
"""
from types import SimpleNamespace

from database.twin import connection, repository
from utils.logger import StructuredLogger
from utils.tracing import span

logger = StructuredLogger(__name__)


def uses_twin():
    return connection.is_enabled()


def inventory_session():
    """Inventory history sessions use the supplied PostgreSQL database when configured."""
    if uses_twin():
        from sqlalchemy.orm import Session
        return Session(bind=connection.get_engine())
    from database.connection import SessionLocal
    return SessionLocal()


def products():
    with span('inventory.retrieve', source='postgresql_twin'):
        rows = repository.get_product_totals()
        logger.log_event('INVENTORY_DATA_RETRIEVED', {'source': 'postgresql_twin', 'products': len(rows)})
        return rows


def snapshot():
    with span('inventory.retrieve', source='postgresql_twin'):
        result = repository.get_inventory_snapshot()
        logger.log_event('INVENTORY_DATA_RETRIEVED', {'source':'postgresql_twin',
            'products':len(result['products']), 'placements':len(result['locations']), 'as_of':result['as_of']})
        return result


def find(reference, rows=None):
    key = reference.strip().upper()
    row = next((p for p in (products() if rows is None else rows) if p['sku'].upper() == key or p['product_id'] == key), None)
    logger.log_event('INVENTORY_PRODUCT_RESOLVED', {
        'reference': reference, 'product_id': row['product_id'] if row else None,
        'source': 'postgresql_twin', 'found': row is not None,
    })
    return row


def legacy_shape(row):
    """Compatibility shape for existing specialist calculations, not another balance source."""
    return SimpleNamespace(**{**row, 'id': row['product_id'], 'quantity': row['total_quantity'],
                              'location': 'Location unassigned', 'aisle': None, 'shelf': None,
                              'tier': None, 'bay': None, 'occupancy_pct': None, 'temperature': None})
