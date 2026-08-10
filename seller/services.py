"""Seller earnings, commissions and payouts.

The ledger is the single source of truth for how much each seller has earned.
Earnings (``SALE`` credits) are recorded only after an order is paid *and*
delivered; any refund on a delivered order generates a matching ``REFUND``
debit so the platform never overpays. Payouts move ``available`` entries into
``payout_pending`` and, once an admin confirms the transfer, ``paid``.
"""

import logging
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.utils import timezone

from order.models import Order, OrderItem

from .models import SellerLedgerEntry, SellerPayout

logger = logging.getLogger(__name__)


def _money(value):
    return Decimal(value or 0).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def commission_rate_for(seller):
    """Per-seller override, otherwise the platform default."""
    if seller.commission_rate is not None:
        return Decimal(str(seller.commission_rate))
    return Decimal(str(getattr(settings, 'MARKETPLACE_COMMISSION_RATE', '0.10')))


def payout_min_amount():
    return Decimal(str(getattr(settings, 'MARKETPLACE_PAYOUT_MIN_AMOUNT', '100')))


def split_commission(gross, rate):
    """Return (gross, commission, net) rounded to paise."""
    gross = _money(gross)
    commission = _money(gross * Decimal(str(rate)))
    return gross, commission, gross - commission


def _eligible_items(seller=None):
    qs = OrderItem.objects.filter(
        order__paid=True,
        order__status=Order.Status.DELIVERED,
        product__seller__isnull=False,
    ).select_related('product__seller', 'order')
    if seller is not None:
        qs = qs.filter(product__seller=seller)
    return qs


def reconcile_seller_earnings(seller=None):
    """Idempotently create ledger entries for paid, delivered orders.

    Safe to run on any schedule (cron/Celery beat): ``get_or_create`` means a
    second run never double-counts. Returns a dict of created entry counts.
    """
    created = {'sale': 0, 'refund': 0}
    for item in _eligible_items(seller).iterator(chunk_size=200):
        item_seller = item.product.seller
        rate = commission_rate_for(item_seller)
        gross, commission, net = split_commission(item.get_cost(), rate)

        _, was_created = SellerLedgerEntry.objects.get_or_create(
            seller=item_seller,
            order_item=item,
            entry_type=SellerLedgerEntry.EntryType.SALE,
            defaults={
                'gross_amount': gross,
                'commission_rate': rate,
                'commission_amount': commission,
                'net_amount': net,
                'status': SellerLedgerEntry.Status.AVAILABLE,
                'reference': f'Order {item.order.order_number}',
            },
        )
        created['sale'] += int(was_created)

        # A refund on a delivered order claws back the whole net amount for the
        # item. Order-level partial refunds can be reconciled with an admin
        # ADJUSTMENT entry.
        if item.order.total_refunded() > 0:
            _, refund_created = SellerLedgerEntry.objects.get_or_create(
                seller=item_seller,
                order_item=item,
                entry_type=SellerLedgerEntry.EntryType.REFUND,
                defaults={
                    'gross_amount': -gross,
                    'commission_rate': rate,
                    'commission_amount': -commission,
                    'net_amount': -net,
                    'status': SellerLedgerEntry.Status.AVAILABLE,
                    'reference': f'Refund on order {item.order.order_number}',
                },
            )
            created['refund'] += int(refund_created)

    return created


def available_balance(seller):
    """Sum of net earnings not yet paid out or locked in a payout."""
    from django.db.models import Sum
    total = SellerLedgerEntry.objects.filter(
        seller=seller,
        status=SellerLedgerEntry.Status.AVAILABLE,
    ).aggregate(total=Sum('net_amount'))['total']
    return _money(total)


def total_earned(seller):
    """Gross lifetime earnings (sales minus refunds, before payouts)."""
    from django.db.models import Sum
    total = SellerLedgerEntry.objects.filter(
        seller=seller,
        entry_type__in=[SellerLedgerEntry.EntryType.SALE, SellerLedgerEntry.EntryType.REFUND],
    ).aggregate(total=Sum('net_amount'))['total']
    return _money(total)


def create_payout(seller, *, actor=None, amount=None):
    """Move the available balance into a processing payout.

    Returns (payout_or_None, error_or_None).
    """
    if amount is None:
        amount = available_balance(seller)
    else:
        amount = _money(amount)

    minimum = payout_min_amount()
    if amount < minimum:
        return None, f'The minimum payout amount is {minimum} and your available balance is {amount}.'
    if amount <= 0:
        return None, 'There is no available balance to pay out yet.'

    payout = SellerPayout.objects.create(
        seller=seller,
        amount=amount,
        status=SellerPayout.Status.PROCESSING,
        initiated_by=actor,
    )
    SellerLedgerEntry.objects.filter(
        seller=seller,
        status=SellerLedgerEntry.Status.AVAILABLE,
    ).update(status=SellerLedgerEntry.Status.PAYOUT_PENDING, payout=payout)
    return payout, None


def mark_payout_paid(payout, *, actor=None, reference=''):
    """Admin confirms the money was transferred; entries become PAID."""
    payout.status = SellerPayout.Status.PAID
    payout.reference = reference
    payout.paid_at = timezone.now()
    payout.save(update_fields=['status', 'reference', 'paid_at', 'updated_at'])
    payout.ledger_entries.update(status=SellerLedgerEntry.Status.PAID)


def fail_payout(payout, *, actor=None, note=''):
    """Release a failed payout back to the available balance."""
    payout.status = SellerPayout.Status.FAILED
    payout.notes = note
    payout.save(update_fields=['status', 'notes', 'updated_at'])
    payout.ledger_entries.update(
        status=SellerLedgerEntry.Status.AVAILABLE, payout=None,
    )


def cancel_payout(payout, *, actor=None, note=''):
    """Release a cancelled payout back to the available balance."""
    payout.status = SellerPayout.Status.CANCELLED
    payout.notes = note
    payout.save(update_fields=['status', 'notes', 'updated_at'])
    payout.ledger_entries.update(
        status=SellerLedgerEntry.Status.AVAILABLE, payout=None,
    )
