"""Shared payment logic: idempotent capture, webhook verification, gateway refunds.

Both the browser callback and the Razorpay webhook funnel through
``finalize_payment`` so a double-delivery can never double-charge, double-fulfil,
or double-notify the customer.
"""

import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.urls import reverse

from order.models import Order
from notifications.emails import send_payment_confirmation
from notifications.models import Notification
from notifications.services import notify

logger = logging.getLogger(__name__)


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

    Uses a dedicated webhook secret when configured, falling back to the
    regular key secret so the feature works without extra env vars.
    """
    secret = getattr(settings, 'RAZORPAY_WEBHOOK_SECRET', None) or settings.RAZORPAY_KEY_SECRET
    if not signature:
        return False
    expected = hmac.new(secret.encode(), raw_body.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


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


def finalize_payment(payment, razorpay_payment_id, razorpay_signature=''):
    """Mark a payment captured and its order paid — idempotently.

    Returns True if this call actually processed the payment, False if it was
    already captured (double callback / webhook delivery).
    """
    if payment.status == 'captured':
        return False

    payment.razorpay_payment_id = razorpay_payment_id
    payment.razorpay_signature = razorpay_signature or payment.razorpay_signature
    payment.status = 'captured'
    payment.save(update_fields=['razorpay_payment_id', 'razorpay_signature', 'status', 'updated_at'])

    order = payment.order
    order.paid = True
    if order.status == Order.Status.PENDING:
        order.status = Order.Status.PROCESSING
    order.save()

    from order.stock import commit_stock
    commit_stock(order)

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
    return True


def mark_payment_failed(payment, message=''):
    payment.status = 'failed'
    payment.save(update_fields=['status', 'updated_at'])
    notify(
        payment.order.user,
        Notification.Category.PAYMENT,
        f'Payment failed for order {payment.order.order_number}',
        message or 'Your payment could not be processed. Please try again or use a different payment method.',
        link=reverse('payments:checkout', args=[payment.order.id]),
        icon='credit-card',
    )


def refund_payment(payment, amount=None, note='Refund requested via Shop-Seed admin'):
    """Issue a gateway refund for a captured payment.

    Falls back to marking the payment refunded locally when the gateway is not
    configured or the payment has no captured transaction id.
    Returns (ok, detail).
    """
    amount = amount if amount is not None else payment.amount
    if payment.status == 'refunded':
        return True, 'already_refunded'

    client = get_razorpay_client()
    payment_id = payment.razorpay_payment_id
    if not payment_id:
        payment.status = 'refunded'
        payment.save(update_fields=['status', 'updated_at'])
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
    return True, response.get('id', 'refunded')
