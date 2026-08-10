"""Job handlers for the async worker.

Handlers must be idempotent: delivery is at-least-once, so a crash between
claim and completion (or an expired lease on a still-running job) can re-run
a handler. Raise ``RetryableJobError`` to mark a job for a later attempt; any
other exception is treated the same way and only becomes permanent once
``max_attempts`` is exhausted.
"""

HANDLERS = {}


class RetryableJobError(Exception):
    """A job failed in a way that may succeed on a later attempt."""


def register(kind):
    def decorator(fn):
        HANDLERS[kind] = fn
        return fn
    return decorator


def get_handler(kind):
    return HANDLERS.get(kind)


@register('send_email')
def handle_send_email(payload):
    from notifications.emails import (
        send_order_confirmation,
        send_payment_confirmation,
        send_shipping_confirmation,
    )
    from order.models import Order
    from payments.models import Payment
    from logistics.models import Shipment

    kind = payload.get('kind')
    order = Order.objects.select_related('user').get(pk=payload['order_id'])

    sent = False
    if kind == 'order_confirmation':
        sent = send_order_confirmation(order)
    elif kind == 'payment_confirmation':
        payment = Payment.objects.get(pk=payload['payment_id'])
        sent = send_payment_confirmation(order, payment)
    elif kind == 'shipping_confirmation':
        shipment = Shipment.objects.get(pk=payload['shipment_id'])
        sent = send_shipping_confirmation(order, shipment)
    else:
        raise RetryableJobError(f'Unknown email kind: {kind!r}')

    if not sent:
        raise RetryableJobError(f'{kind} email failed for order {order.pk}')
    return f'{kind} email sent for order {order.pk}'


@register('fulfil_order')
def handle_fulfil_order(payload):
    from order.models import Order
    from payments.services import trigger_fulfilment

    order = Order.objects.get(pk=payload['order_id'])
    trigger_fulfilment(order)
    if not order.logistics_shipments.exists():
        raise RetryableJobError(
            f'Fulfilment produced no shipments for order {order.pk}'
        )
    return f'fulfilled order {order.pk}'


@register('refund_payment')
def handle_refund_payment(payload):
    from payments.models import Payment
    from payments.services import refund_payment

    payment = Payment.objects.select_for_update().get(pk=payload['payment_id'])
    ok, detail = refund_payment(
        payment,
        note=payload.get('note') or 'Auto-refund — retried by async worker',
        source='system',
    )
    if not ok:
        raise RetryableJobError(detail or 'Gateway refund failed')
    return detail
