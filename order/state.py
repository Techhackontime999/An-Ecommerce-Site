"""Order status state machine.

Every status change must go through ``set_order_status`` so transitions are
validated and audited. Callers that need side effects (refunds, stock release,
notifications) wrap the call; this module owns *only* the transition + audit
record.

Allowed transitions:

    pending    → processing, cancelled
    processing → shipped,     cancelled
    shipped    → delivered,   cancelled
    delivered  → refunded
    cancelled  → refunded
    refunded   → (terminal)

``force=True`` is reserved for staff/admin corrections and still writes the
audit row so no change is ever silent.
"""

from .models import Order, OrderAuditLog

ALLOWED_TRANSITIONS = {
    Order.Status.PENDING: {Order.Status.PROCESSING, Order.Status.CANCELLED},
    Order.Status.PROCESSING: {Order.Status.SHIPPED, Order.Status.DELIVERED, Order.Status.CANCELLED},
    Order.Status.SHIPPED: {Order.Status.DELIVERED, Order.Status.CANCELLED},
    Order.Status.DELIVERED: {Order.Status.REFUNDED},
    Order.Status.CANCELLED: {Order.Status.REFUNDED},
    Order.Status.REFUNDED: set(),
}


def set_order_status(order, to_status, *, actor=None, note='', force=False):
    """Validate and apply a status transition, writing an audit log entry.

    Returns ``(ok, reason)``. On success the order is saved (status + updated).
    """
    from_status = order.status
    if to_status == from_status:
        return True, 'no_change'

    allowed = ALLOWED_TRANSITIONS.get(from_status, set())
    if to_status not in allowed:
        if not force:
            return False, (
                f'Cannot move order {order.order_number} from '
                f'"{from_status}" to "{to_status}".'
            )

    order.status = to_status
    order.save(update_fields=['status', 'updated'])
    OrderAuditLog.objects.create(
        order=order,
        from_status=from_status,
        to_status=to_status,
        action='status_change' + ('_forced' if force else ''),
        note=note,
        actor=actor,
    )
    return True, 'ok'
