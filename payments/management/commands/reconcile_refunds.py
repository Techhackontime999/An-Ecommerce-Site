"""Reconcile failed auto-refunds.

Finds payments where the gateway has taken the customer's money but the money
has not been returned, and enqueues a durable ``refund_payment`` job for each:

- a **captured** payment whose order was cancelled or refunded, or
- a payment marked **failed** after capture (e.g. insufficient stock at
  fulfilment time).

Real gateway refunds are only issued for transactions with a Razorpay payment
id (``pay_...``); COD / manual references have no gateway refund and are left
alone. Orders that already have an admin-issued ``Refund`` row are skipped so
a store-credit or bank-transfer refund is never double-refunded through the
gateway. ``refund_payment`` is idempotent, so re-running this command is safe.

Run from cron every few minutes::

    python manage.py reconcile_refunds --dry-run
"""

import logging

from django.core.management.base import BaseCommand
from django.db.models import Q

from jobs.services import enqueue
from order.models import Order, Refund
from payments.models import Payment

logger = logging.getLogger(__name__)


def find_unrefunded_payments():
    """Payments that still owe the customer a refund (see module docstring)."""
    in_flight_refund_statuses = (
        Refund.Status.PENDING,
        Refund.Status.PROCESSING,
        Refund.Status.COMPLETED,
    )
    return (
        Payment.objects.select_related('order')
        .exclude(status='refunded')
        .exclude(order__refunds__status__in=in_flight_refund_statuses)
        .filter(
            Q(
                status='captured',
                order__status__in=(Order.Status.CANCELLED, Order.Status.REFUNDED),
            )
            | Q(status='failed', razorpay_payment_id__isnull=False)
        )
        .exclude(
            Q(razorpay_payment_id__startswith='cod-')
            | Q(razorpay_payment_id__startswith='manual-')
        )
        .order_by('updated_at')
    )


class Command(BaseCommand):
    help = 'Enqueue durable refund jobs for payments that still owe the customer money.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Report what would be refunded without enqueueing anything.',
        )
        parser.add_argument(
            '--limit', type=int, default=100,
            help='Max payments to reconcile per run (default 100).',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        limit = max(1, int(options['limit']))

        payments = find_unrefunded_payments()[:limit]
        enqueued = 0
        for payment in payments:
            if dry_run:
                self.stdout.write(
                    f'  would refund payment {payment.pk} '
                    f'({payment.status}, order {payment.order_id})'
                )
                continue
            enqueue('refund_payment', {
                'payment_id': payment.pk,
                'note': f'Reconciled refund — payment {payment.status} but money captured.',
            }, dedupe_key=f'refund-payment:{payment.pk}')
            enqueued += 1

        verb = 'would enqueue' if dry_run else 'enqueued'
        self.stdout.write(self.style.SUCCESS(
            f'Reconcile finished: {verb} refund job(s) for '
            f'{enqueued}/{payments.count()} payment(s).'
        ))
