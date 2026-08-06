"""Unified in-app notification helper for logistics events.

Thin wrapper around the ``notifications`` app so the fulfilment service can
notify customers and sellers without caring about storage details. Fails
silently so a notification problem never blocks a logistics operation.
"""

from django.contrib.auth.models import User

from logistics.models import Shipment


def notify_user(user, title, message, *, category='shipping', icon='', link='', role='customer'):
    """Create an in-app notification for a user (best effort)."""
    if user is None:
        return None
    try:
        from notifications.models import Notification
        return Notification.objects.create(
            recipient=user,
            role=role,
            category=category,
            title=title,
            message=message,
            icon=icon,
            link=link,
        )
    except Exception:
        return None


def notify_shipment_update(shipment, description='', category='shipping'):
    """Notify the order's customer about a shipment status change."""
    order = shipment.order
    if order is None or order.user_id is None:
        return None
    title = _title_for_status(shipment.status)
    message = description or title
    link = f'/logistics/track/?q={shipment.shipment_number}'
    return notify_user(
        order.user,
        title,
        f'{message} — AWB {shipment.tracking_number or "pending"}',
        category=category,
        icon='truck-fast',
        link=link,
    )


def notify_seller(shipment, title, message):
    seller = shipment.seller
    if seller is None or seller.user_id is None:
        return None
    return notify_user(
        seller.user,
        title,
        message,
        category='shipping',
        icon='box-open',
        role='seller',
        link=f'/logistics/track/?q={shipment.shipment_number}',
    )


def _title_for_status(status):
    from logistics.constants import ShipmentStatus
    return ShipmentStatus.LABELS.get(status, 'Shipment Update')
