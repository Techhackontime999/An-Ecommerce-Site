"""Shared payment logic: idempotent capture, webhook verification, gateway refunds.

Both the browser callback and the Razorpay webhook funnel through
``finalize_payment`` so a double-delivery can never double-charge, double-fulfil,
or double-notify the customer.

``finalize_payment`` is the *only* place an order is marked paid, and it
serialises on the payment + order rows with ``select_for_update`` so a payment
can never be captured against an order that was cancelled concurrently.
"""

import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.db import transaction
from django.urls import reverse

from order.models import Order
from order.state import set_order_status
from order.stock import InsufficientStock
from notifications.emails import send_payment_confirmation
from notifications.models import Notification
from notifications.services import notify

from .models import Payment, PaymentAuditLog

logger = logging.getLogger(__name__)

VALID_SOURCES = {'callback', 'webhook', 'verify', 'admin', 'system'}


def get_razorpay_client():
    import razorpay
    return razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )


def verify_callback_signature(razorpay_order_id, razorpay_payment_id, signature):
    expected = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        f'{razorpay_order_id}|{razorpay_payment_id}'.encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def verify_webhook_signature(raw_body, signature):
    """Verify the X-Razorpay-Signature header over the raw request body.

    A dedicated ``RAZORPAY_WEBHOOK_SECRET`` is required in production; when the
    app is running with DEBUG=True (local dev) it falls back to the regular key
    secret so the feature works without extra env vars.
    """
    secret = getattr(settings, 'RAZORPAY_WEBHOOK_SECRET', '') or ''
    if not secret and settings.DEBUG:
        secret = getattr(settings, 'RAZORPAY_KEY_SECRET', '') or ''
    if not secret or not signature:
        logger.warning('Payment webhook received without a configured signature secret — rejecting.')
        return False
    expected = hmac.new(secret.encode(), raw_body.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def record_audit(payment, old_status, new_status, source='system', message='', actor=None):
    """Append a row to the payment audit log."""
    if source not in VALID_SOURCES:
        source = 'system'
    try:
        PaymentAuditLog.objects.create(
            payment=payment,
            old_status=old_status,
            new_status=new_status,
            source=source,
            actor=actor,
            message=message,
        )
    except Exception as exc:  # an audit failure must never break the payment flow
        logger.error('Failed to record payment audit for payment %s: %s', payment.id, exc, exc_info=True)


def trigger_fulfilment(order):
    """Run the LMS fulfilment pipeline for a freshly paid order.

    Best effort — a courier failure must never roll back a successful payment.
    """
    try:
        from logistics.services.fulfillment import FulfillmentService
        shipments = FulfillmentService.create_shipments_for_order(order)
        if shipments:
            from notifications.emails import send_shipping_confirmation
            for shipment in shipments[:1]:
                send_shipping_confirmation(order, shipment)
            names = ', '.join(s.shipment_number for s in shipments)
            notify(
                order.user,
                Notification.Category.SHIPPING,
                f'Shipment created for order {order.order_number}',
                f'Your order is being packed. AWB(s): {names}. Track it anytime.',
                link=f'/logistics/track/?q={shipments[0].shipment_number}',
                icon='truck-fast',
            )
        return shipments
    except Exception as exc:
        logger.error('Fulfilment failed for order %s: %s', order.id, exc, exc_info=True)
        return []


def _post_capture_side_effects(order, payment):
    """Notifications/emails for a captured payment (after the DB transaction)."""
    trigger_fulfilment(order)
    notify(
        order.user,
        Notification.Category.PAYMENT,
        f'Payment received for order {order.order_number}',
        f'Your payment of {payment.amount} {payment.currency} was successful. Thank you for shopping with Shop-Seed!',
        link=reverse('order:my_orders'),
        icon='credit-card',
    )
    send_payment_confirmation(order, payment)


def _fail_and_refund_captured(payment, razorpay_payment_id, reason, source='system', actor=None):
    """Persist a failed payment for an order that cannot be fulfilled, then refund it.

    The gateway has *already captured* the money by the time stock runs short, so
    the payment must not be left in ``created``/``attempted`` — that would orphan
    the customer's funds. We record a failed state in a fresh transaction (the
    capture transaction already rolled back) and immediately attempt a full
    gateway refund. If the refund fails, the audit trail and error log flag it
    for manual reconciliation.
    """
    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(pk=payment.pk)
        order = Order.objects.select_for_update().get(pk=payment.order_id)
        old_status = payment.status
        if razorpay_payment_id and not payment.razorpay_payment_id:
            payment.razorpay_payment_id = razorpay_payment_id
        payment.status = 'failed'
        payment.save(update_fields=['razorpay_payment_id', 'status', 'updated_at'])
        record_audit(
            payment, old_status, 'failed', source=source, actor=actor,
            message=f'Payment captured but order could not be fulfilled: {reason}',
        )

    try:
        ok, detail = refund_payment(
            payment,
            note=f'Auto-refund — order could not be fulfilled: {reason}',
            actor=actor,
            source=source,
        )
    except Exception as exc:
        logger.error(
            'Auto-refund raised after failed capture for payment %s: %s',
            payment.pk, exc, exc_info=True,
        )
        ok, detail = False, str(exc)

    if ok:
        notify(
            payment.order.user,
            Notification.Category.PAYMENT,
            f'Payment refunded for order {payment.order.order_number}',
            f'We could not fulfil your order, so your payment of {payment.amount} '
            f'{payment.currency} has been refunded. It will appear in 3–7 business days.',
            link=reverse('order:my_orders'),
            icon='credit-card',
        )
    else:
        logger.error(
            'AUTO-REFUND FAILED for payment %s (order %s): %s — manual reconciliation required.',
            payment.pk, payment.order_id, detail,
        )


def finalize_payment(payment, razorpay_payment_id, razorpay_signature='', source='callback', actor=None):
    """Mark a payment captured and its order paid — idempotently and atomically.

    Returns True if this call actually processed the payment, False if it was
    already captured (double callback / webhook delivery), rejected because the
    order was cancelled/refunded before the money arrived, or rolled back because
    the order could not be fulfilled from stock (in which case a gateway refund
    is issued automatically — see ``_fail_and_refund_captured``).

    Only call this from endpoints whose authenticity has already been verified
    (HMAC signature or gateway status check) — a GET request must never reach it.
    """
    if source not in VALID_SOURCES:
        raise ValueError(f'Invalid payment source: {source!r}')

    try:
        with transaction.atomic():
            # Lock in the same order as cancel_order (Order -> Payment) so a
            # concurrent capture and cancellation can never deadlock.
            order = Order.objects.select_for_update().get(pk=payment.order_id)
            payment = Payment.objects.select_for_update().get(pk=payment.pk)
            if payment.status == 'captured':
                return False

            # Race guard: a customer may have cancelled between the gateway capture
            # and our processing. Never "resurrect" a cancelled order into a paid one.
            if order.status in (Order.Status.CANCELLED, Order.Status.REFUNDED):
                logger.warning(
                    'Capture rejected for order %s: order status is %s',
                    order.id, order.status,
                )
                record_audit(
                    payment, payment.status, 'failed', source=source, actor=actor,
                    message=f'Capture rejected — order is {order.status}.',
                )
                if razorpay_payment_id:
                    payment.razorpay_payment_id = razorpay_payment_id
                    try:
                        refund_payment(
                            payment,
                            note=f'Refunded — payment captured after order {order.order_number} was cancelled.',
                        )
                    except Exception as exc:
                        logger.error('Refund after cancellation failed for payment %s: %s', payment.id, exc, exc_info=True)
                if payment.status != 'refunded':
                    payment.status = 'failed'
                    payment.save(update_fields=['status', 'updated_at'])
                return False

            old_status = payment.status
            payment.razorpay_payment_id = razorpay_payment_id
            payment.razorpay_signature = razorpay_signature or payment.razorpay_signature
            payment.status = 'captured'
            payment.save(update_fields=['razorpay_payment_id', 'razorpay_signature', 'status', 'updated_at'])

            order.paid = True
            if order.status == Order.Status.PENDING:
                set_order_status(
                    order, Order.Status.PROCESSING, actor=actor,
                    note='Payment captured.',
                )
            order.save(update_fields=['paid', 'updated'])

            # Stock is decremented inside the same transaction. If any line is short,
            # commit_stock raises and the whole capture rolls back — the customer is
            # never charged for an order that cannot be shipped.
            from order.stock import commit_stock
            commit_stock(order)

            record_audit(
                payment, old_status, 'captured', source=source, actor=actor,
                message='Payment captured and order marked paid.',
            )
    except InsufficientStock as exc:
        # The gateway has already captured the money, so we must refund it rather
        # than leave the customer charged with a "failed" order. This handles the
        # failure in a fresh transaction (the capture above was rolled back).
        logger.error(
            'Capture rolled back for payment %s (order %s): %s',
            payment.pk, payment.order_id, exc, exc_info=True,
        )
        _fail_and_refund_captured(payment, razorpay_payment_id, str(exc), source=source, actor=actor)
        return False

    transaction.on_commit(lambda: _post_capture_side_effects(order, payment))
    return True


def collect_cod_cash(shipment, *, source='system', actor=None):
    """Record the cash collected when a COD shipment is delivered.

    A delivered COD shipment means the courier has collected cash from the
    customer, so the order is marked paid — always backed by a captured
    ``Payment`` row, the same source of truth ``total_paid()`` and refund
    validation rely on. Idempotent: only runs once per order, and is a no-op
    for prepaid shipments or already-paid orders.

    Returns True when cash collection was recorded, False otherwise.
    """
    if not getattr(shipment, 'is_cod', False):
        return False
    order = shipment.order
    if order is None or order.paid:
        return False

    try:
        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=order.pk)
            if order.paid:
                return False
            amount = shipment.cod_amount or order.get_total_cost()
            currency = getattr(shipment, 'currency', '') or 'INR'
            ref = f'cod-{shipment.shipment_number or shipment.id}'

            payment = Payment.objects.select_for_update().filter(order=order).first()
            if payment is None:
                old_status = ''
                payment = Payment.objects.create(
                    order=order, razorpay_order_id=ref, amount=amount,
                    currency=currency, status='captured',
                )
            else:
                old_status = payment.status
                payment.status = 'captured'
                payment.amount = amount
                if not payment.razorpay_payment_id:
                    payment.razorpay_payment_id = ref
                payment.save(update_fields=['status', 'amount', 'razorpay_payment_id', 'updated_at'])

            record_audit(
                payment, old_status, 'captured', source=source, actor=actor,
                message=f'Cash collected on delivery of shipment {shipment.shipment_number}.',
            )

            order.paid = True
            order.save(update_fields=['paid', 'updated'])

            # Same invariant as finalize_payment: a paid order has committed
            # stock. If stock is short the whole collection rolls back and the
            # order stays unpaid, flagged for reconciliation.
            from order.stock import commit_stock
            commit_stock(order)

        def _notify_cod_collected():
            notify(
                order.user,
                Notification.Category.PAYMENT,
                f'Payment collected for order {order.order_number}',
                f'Cash of {payment.amount} {payment.currency} was collected on delivery. Thank you for shopping with Shop-Seed!',
                link=reverse('order:my_orders'),
                icon='hand-coin',
            )
        transaction.on_commit(_notify_cod_collected)
        return True
    except InsufficientStock:
        logger.warning(
            'COD cash collection rolled back for order %s — insufficient stock.',
            order.id,
        )
        return False


def mark_payment_failed(payment, message='', source='gateway', actor=None):
    """Mark a payment failed, with audit + customer notification."""
    if payment.status == 'failed':
        return
    old_status = payment.status
    payment.status = 'failed'
    payment.save(update_fields=['status', 'updated_at'])
    record_audit(payment, old_status, 'failed', source=source, actor=actor, message=message)
    notify(
        payment.order.user,
        Notification.Category.PAYMENT,
        f'Payment failed for order {payment.order.order_number}',
        message or 'Your payment could not be processed. Please try again or use a different payment method.',
        link=reverse('payments:checkout', args=[payment.order.id]),
        icon='credit-card',
    )


def refund_payment(payment, amount=None, note='Refund requested via Shop-Seed admin', actor=None, source='admin'):
    """Issue a gateway refund for a captured payment.

    Falls back to marking the payment refunded locally when the gateway is not
    configured or the payment has no captured transaction id.
    Returns (ok, detail).
    """
    amount = amount if amount is not None else payment.amount
    if payment.status == 'refunded':
        return True, 'already_refunded'

    old_status = payment.status
    client = get_razorpay_client()
    payment_id = payment.razorpay_payment_id
    if not payment_id:
        payment.status = 'refunded'
        payment.save(update_fields=['status', 'updated_at'])
        record_audit(payment, old_status, 'refunded', source=source, actor=actor,
                     message='Marked refunded — no gateway transaction id to refund.')
        return True, 'marked_refunded_no_gateway_id'

    try:
        response = client.payment.refund(
            payment_id,
            {
                'amount': int(amount * 100),
                'notes': {'order': str(payment.order.id), 'note': note},
            },
        )
    except Exception as exc:
        logger.error('Gateway refund failed for payment %s: %s', payment.id, exc, exc_info=True)
        return False, str(exc)

    payment.status = 'refunded'
    payment.save(update_fields=['status', 'updated_at'])
    record_audit(payment, old_status, 'refunded', source=source, actor=actor, message=note)
    return True, response.get('id', 'refunded')
