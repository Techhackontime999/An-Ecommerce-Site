"""Stock accounting for orders.

Stock is committed only after a payment is captured (never at order creation,
so abandoned checkouts don't eat inventory) and released again on cancellation
or refund.
"""

import logging

logger = logging.getLogger(__name__)


def commit_stock(order):
    """Decrement product/variant stock for every item on the order."""
    for item in order.items.all():
        variant = item.variant
        if variant is not None:
            variant.stock = max(0, variant.stock - item.quantity)
            variant.save(update_fields=['stock'])
        else:
            product = item.product
            product.stock = max(0, product.stock - item.quantity)
            product.save(update_fields=['stock'])


def release_stock(order):
    """Restore product/variant stock for every item on the order."""
    for item in order.items.all():
        variant = item.variant
        if variant is not None:
            variant.stock += item.quantity
            variant.save(update_fields=['stock'])
        else:
            product = item.product
            product.stock += item.quantity
            product.save(update_fields=['stock'])
