"""Transactional inventory writes; the LLM has no stock-write tool."""
from datetime import datetime

from sqlalchemy import text
from database.twin.connection import twin_connection
from database.twin.repository import _rows
from utils.logger import StructuredLogger

logger = StructuredLogger(__name__)


class InventoryConflict(ValueError):
    pass


def update_placement(*, product_id, bin_id, lot_code, quantity, reserved_quantity,
                     quarantined_quantity, expected_updated_at, actor, allocate_unplaced=False):
    with twin_connection() as conn:
        product = conn.execute(text('select id from products where id=:pid and is_active for update'),
                               {'pid':product_id}).scalar()
        if not product:
            raise ValueError('Unknown active product')
        bin_row = conn.execute(text('select id,status,capacity_units from bins where id=:bin for update'),
                               {'bin':bin_id}).mappings().first()
        if not bin_row:
            raise ValueError('Unknown bin')
        params = {'pid':product_id,'bin':bin_id,'lot':lot_code}
        old = conn.execute(text('''select * from stock_locations where product_id=:pid and bin_id=:bin
                                  and lot_code=:lot for update'''),params).mappings().first()
        if old:
            expected = datetime.fromisoformat(expected_updated_at.replace('Z','+00:00')) if isinstance(expected_updated_at,str) else expected_updated_at
            if expected != old['updated_at']:
                raise InventoryConflict('Stock changed since it was read; reload before saving')
        elif expected_updated_at is not None:
            raise InventoryConflict('Placement no longer exists; reload before saving')
        previous = old['quantity'] if old else 0
        old_reserved = old['reserved_quantity'] if old else 0
        old_quarantined = old['quarantined_quantity'] if old else 0
        reserved_quantity = old_reserved if reserved_quantity is None else reserved_quantity
        quarantined_quantity = old_quarantined if quarantined_quantity is None else quarantined_quantity
        if reserved_quantity + quarantined_quantity > quantity:
            raise ValueError('Reserved and quarantined quantities exceed physical stock')
        delta = quantity - previous
        if delta > 0:
            if str(bin_row['status']) != 'active':
                raise ValueError('Bin is blocked or unavailable')
            used = conn.execute(text('select coalesce(sum(quantity),0) from stock_locations where bin_id=:bin'),params).scalar()
            if used + delta > bin_row['capacity_units']:
                raise ValueError('Bin capacity exceeded')
        source = 'operational'
        if allocate_unplaced:
            if delta <= 0:
                raise ValueError('Allocation must increase placed stock')
            unplaced = conn.execute(text('select * from unplaced_stock where product_id=:pid for update'),params).mappings().first()
            moved_reserved = reserved_quantity-old_reserved
            moved_quarantined = quarantined_quantity-old_quarantined
            moved_available = delta-moved_reserved-moved_quarantined
            if (not unplaced or moved_reserved < 0 or moved_quarantined < 0 or moved_available < 0
                or delta > unplaced['quantity'] or moved_reserved > unplaced['reserved_quantity']
                or moved_quarantined > unplaced['quarantined_quantity']
                or moved_available > unplaced['quantity']-unplaced['reserved_quantity']-unplaced['quarantined_quantity']):
                raise ValueError('Allocation exceeds the unassigned quantity or commitment breakdown')
            source = unplaced['data_source']
            conn.execute(text('''update unplaced_stock set quantity=quantity-:delta,
                reserved_quantity=reserved_quantity-:reserved,quarantined_quantity=quarantined_quantity-:quarantined
                where product_id=:pid'''),{**params,'delta':delta,'reserved':moved_reserved,'quarantined':moved_quarantined})
        result = conn.execute(text('''insert into stock_locations
            (product_id,bin_id,lot_code,quantity,reserved_quantity,quarantined_quantity,data_source)
            values (:pid,:bin,:lot,:qty,:reserved,:quarantined,:source)
            on conflict (product_id,bin_id,lot_code) do update set quantity=excluded.quantity,
              reserved_quantity=excluded.reserved_quantity,quarantined_quantity=excluded.quarantined_quantity,
              data_source=excluded.data_source, updated_at=now()
            returning *'''), {**params,'qty':quantity,'reserved':reserved_quantity,
                              'quarantined':quarantined_quantity,'source':source})
        saved = _rows(result)[0]
        if delta:
            conn.execute(text('''insert into stock_movements
                (product_id,from_bin_id,to_bin_id,quantity,type,actor,note)
                values (:pid,:from_bin,:to_bin,:delta,'adjust',:actor,:note)'''),
                {'pid':product_id,'from_bin':bin_id if delta<0 else None,'to_bin':bin_id if delta>0 else None,
                 'delta':abs(delta),'actor':actor,'note':'Allocation of imported unassigned balance' if allocate_unplaced else 'Inventory placement update'})
        if not allocate_unplaced:
            conn.execute(text('update products set updated_at=now() where id=:pid'),params)
    logger.log_event('INVENTORY_PLACEMENT_UPDATED', {'product_id':product_id,'bin_id':bin_id,
                     'quantity':quantity,'allocated_unplaced':allocate_unplaced,'actor':actor})
    return saved
