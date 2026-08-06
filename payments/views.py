import logging
import razorpay
import hmac
import hashlib

from django.conf import settings
from django.shortcuts import render, get_object_or_404, redirect, reverse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponseBadRequest
from order.models import Order
from .models import Payment
from notifications.models import Notification
from notifications.services import notify

logger = logging.getLogger(__name__)


def trigger_fulfilment(order):
    """Run the LMS fulfilment pipeline for a freshly paid order.

    Best effort — a courier failure must never roll back a successful payment.
    """
    try:
        from logistics.services.fulfillment import FulfillmentService
        shipments = FulfillmentService.create_shipments_for_order(order)
        if shipments:
            names = ', '.join(s.shipment_number for s in shipments)
            notify(
                order.user,
                Notification.Category.SHIPPING,
                f'Shipment created for order #{order.id}',
                f'Your order is being packed. AWB(s): {names}. Track it anytime.',
                link=f'/logistics/track/?q={shipments[0].shipment_number}',
                icon='truck-fast',
            )
        return shipments
    except Exception as exc:
        logger.error('Fulfilment failed for order %s: %s', order.id, exc, exc_info=True)
        return []


def get_razorpay_client():
    return razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )


@login_required
def checkout(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)

    if order.paid:
        return redirect('payments:success', order_id=order.id)

    if hasattr(order, 'payment'):
        payment = order.payment
    else:
        client = get_razorpay_client()
        amount_paise = int(order.get_total_cost() * 100)
        razorpay_order = client.order.create({
            'amount': amount_paise,
            'currency': 'INR',
            'payment_capture': '1',
        })
        payment = Payment.objects.create(
            order=order,
            razorpay_order_id=razorpay_order['id'],
            amount=order.get_total_cost(),
            currency='INR',
        )

    context = {
        'order': order,
        'subtotal': sum(item.get_cost() for item in order.items.all()),
        'payment': payment,
        'razorpay_key_id': settings.RAZORPAY_KEY_ID,
        'razorpay_order_id': payment.razorpay_order_id,
        'amount': int(payment.amount * 100),
        'currency': payment.currency,
        'callback_url': request.build_absolute_uri(reverse('payments:callback')),
    }
    return render(request, 'payments/checkout.html', context)


@csrf_exempt
def payment_callback(request):
    if request.method != 'POST':
        return HttpResponseBadRequest('Invalid request method')

    razorpay_payment_id = request.POST.get('razorpay_payment_id', '')
    razorpay_order_id = request.POST.get('razorpay_order_id', '')
    razorpay_signature = request.POST.get('razorpay_signature', '')

    try:
        payment = Payment.objects.get(razorpay_order_id=razorpay_order_id)
    except Payment.DoesNotExist:
        return HttpResponseBadRequest('Invalid payment')

    expected_signature = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        f"{razorpay_order_id}|{razorpay_payment_id}".encode(),
        hashlib.sha256
    ).hexdigest()

    if expected_signature != razorpay_signature:
        payment.status = 'failed'
        payment.save()
        notify(
            payment.order.user,
            Notification.Category.PAYMENT,
            f'Payment failed for order #{payment.order.id}',
            'Your payment could not be processed. Please try again or use a different payment method.',
            link=reverse('payments:checkout', args=[payment.order.id]),
            icon='credit-card',
        )
        return redirect('payments:error', order_id=payment.order.id)

    payment.razorpay_payment_id = razorpay_payment_id
    payment.razorpay_signature = razorpay_signature
    payment.status = 'captured'
    payment.save()

    order = payment.order
    order.paid = True
    if order.status == Order.Status.PENDING:
        order.status = Order.Status.PROCESSING
    order.save()

    trigger_fulfilment(order)

    notify(
        order.user,
        Notification.Category.PAYMENT,
        f'Payment received for order #{order.id}',
        f'Your payment of {payment.amount} {payment.currency} was successful. Thank you for shopping with Shop-Seed!',
        link=reverse('order:my_orders'),
        icon='credit-card',
    )

    return redirect('payments:success', order_id=order.id)


@login_required
def payment_success(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'payments/success.html', {'order': order})


@login_required
def payment_error(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'payments/error.html', {'order': order})
