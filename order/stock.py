"""Stock accounting for orders.

Stock is committed only after a payment is captured (never at order creation,
so abandoned checkouts don't eat inventory) and released again on cancellation
or refund.

All updates use atomic ``F()`` expressions guarded by a ``stock >= quantity``
predicate so concurrent orders can never oversell: the database serialises the
``UPDATE ... WHERE stock >= n`` on each row and only one transaction wins.
"""

import logging

from django.db import transaction
from django.db.models import F

from shop.models import Product, ProductVariant

logger = logging.getLogger(__name__)


class InsufficientStock(Exception):
    """Raised when an order cannot be fulfilled from current inventory."""


@transaction.atomic
def commit_stock(order):
    """Atomically decrement stock for every item on the order.

    Raises ``InsufficientStock`` if any line cannot be fulfilled — the
    caller's transaction is then rolled back so a payment is never marked
    captured against an order that cannot be shipped.
    """
    for item in order.items.select_related('product', 'variant'):
        if item.variant_id is not None:
            updated = ProductVariant.objects.filter(
                pk=item.variant_id, stock__gte=item.quantity,
            ).update(stock=F('stock') - item.quantity)
        else:
            updated = Product.objects.filter(
                pk=item.product_id, stock__gte=item.quantity,
            ).update(stock=F('stock') - item.quantity)
        if not updated:
            name = item.variant.name if item.variant_id else item.product.name
            logger.warning(
                'Insufficient stock for "%s" (need %s) on order %s',
                name, item.quantity, order.id,
            )
            raise InsufficientStock(
                f'Not enough stock for "{name}" (requested {item.quantity}).'
            )


@transaction.atomic
def release_stock(order):
    """Atomically restore stock for every item on the order."""
    for item in order.items.select_related('product', 'variant'):
        if item.variant_id is not None:
            ProductVariant.objects.filter(pk=item.variant_id).update(
                stock=F('stock') + item.quantity
            )
        else:
            Product.objects.filter(pk=item.product_id).update(
                stock=F('stock') + item.quantity
            )
