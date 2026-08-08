import json
import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render, reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from order.models import Order

from .models import Payment
from .services import (
    get_razorpay_client,
    finalize_payment,
    mark_payment_failed,
    verify_callback_signature,
    verify_webhook_signature,
)

logger = logging.getLogger(__name__)


@login_required
def checkout(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)

    if order.paid:
        return redirect('payments:success', order_id=order.id)

    client = get_razorpay_client()
    amount = order.get_total_cost()

    payment = getattr(order, 'payment', None)

    # A stale 'created' order (user left mid-checkout) or a failed attempt must
    # get a *fresh* Razorpay order so retries never reuse a dead token.
    needs_new = (
        payment is None
        or payment.status == 'failed'
        or payment.status == 'created'
    )
    if needs_new:
        razorpay_order = client.order.create({
            'amount': int(amount * 100),
            'currency': 'INR',
            'payment_capture': '1',
        })
        if payment is None:
            payment = Payment.objects.create(
                order=order,
                razorpay_order_id=razorpay_order['id'],
                amount=amount,
                currency='INR',
            )
        else:
            payment.razorpay_order_id = razorpay_order['id']
            payment.razorpay_payment_id = ''
            payment.razorpay_signature = ''
            payment.amount = amount
            payment.status = 'created'
            payment.save()

    context = {
        'order': order,
        'subtotal': sum(item.get_cost() for item in order.items.all()),
        'payment': payment,
        'razorpay_key_id': settings.RAZORPAY_KEY_ID,
        'razorpay_order_id': payment.razorpay_order_id,
        'amount': int(payment.amount * 100),
        'currency': payment.currency,
        'callback_url': request.build_absolute_uri(reverse('payments:callback')),
        'show_verify': bool(payment.razorpay_payment_id and payment.status != 'captured'),
    }
    return render(request, 'payments/checkout.html', context)


@csrf_exempt
@require_POST
def payment_callback(request):
    """Razorpay browser redirect callback. Signature-verified, POST-only."""
    razorpay_payment_id = request.POST.get('razorpay_payment_id', '')
    razorpay_order_id = request.POST.get('razorpay_order_id', '')
    razorpay_signature = request.POST.get('razorpay_signature', '')

    try:
        payment = Payment.objects.get(razorpay_order_id=razorpay_order_id)
    except Payment.DoesNotExist:
        return HttpResponseBadRequest('Invalid payment')

    if not verify_callback_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature):
        mark_payment_failed(payment, source='callback')
        return redirect('payments:error', order_id=payment.order.id)

    try:
        finalize_payment(
            payment, razorpay_payment_id, razorpay_signature, source='callback',
        )
    except Exception as exc:
        # finalize_payment already records failed/refunded state + audit; this is
        # a defensive net so a rendering/notify bug can never 500 the callback.
        logger.error('Callback capture failed for order %s: %s', payment.order_id, exc, exc_info=True)

    order = Order.objects.get(pk=payment.order_id)
    if order.paid:
        return redirect('payments:success', order_id=order.id)
    return redirect('payments:error', order_id=order.id)


@csrf_exempt
@require_POST
def payment_webhook(request):
    """Razorpay webhook. Signature-verified, idempotent and POST-only."""
    signature = request.META.get('HTTP_X_RAZORPAY_SIGNATURE', '')
    raw_body = request.body.decode('utf-8')
    if not verify_webhook_signature(raw_body, signature):
        return HttpResponse('Invalid signature', status=400)

    try:
        event = json.loads(raw_body)
        entity = event.get('payload', {}).get('payment', {}).get('entity', {})
        razorpay_order_id = entity.get('order_id')
        razorpay_payment_id = entity.get('id')
    except (ValueError, AttributeError):
        return HttpResponseBadRequest('Invalid payload')

    if not razorpay_order_id or not razorpay_payment_id:
        return HttpResponse('No order/payment id', status=200)

    event_name = event.get('event')
    try:
        payment = Payment.objects.get(razorpay_order_id=razorpay_order_id)
    except Payment.DoesNotExist:
        logger.warning('Webhook for unknown order %s', razorpay_order_id)
        return HttpResponse('Unknown order', status=200)

    try:
        if event_name in ('payment.captured', 'order.paid'):
            finalize_payment(payment, razorpay_payment_id, source='webhook')
        elif event_name == 'payment.failed':
            mark_payment_failed(payment, 'Payment was declined by your bank / card issuer.', source='webhook')
    except Exception as exc:
        logger.error('Webhook processing failed for order %s: %s', payment.order_id, exc, exc_info=True)

    return HttpResponse('OK', status=200)


@login_required
@require_POST
def payment_verify(request, order_id):
    """POST-only server-side re-check against the gateway.

    Used when a capture succeeded at the gateway but the browser callback was
    lost. Never reached via GET, so a plain page load can never change a
    payment status.
    """
    order = get_object_or_404(Order, id=order_id, user=request.user)
    payment = getattr(order, 'payment', None)

    if order.paid:
        return redirect('payments:success', order_id=order.id)

    if payment and payment.razorpay_payment_id:
        try:
            client = get_razorpay_client()
            detail = client.payment.fetch(payment.razorpay_payment_id)
            if detail and detail.get('status') == 'captured':
                finalize_payment(payment, detail['id'], source='verify')
        except Exception as exc:
            logger.error('Gateway verification failed for order %s: %s', order.id, exc, exc_info=True)

    if order.paid:
        return redirect('payments:success', order_id=order.id)
    return redirect('payments:checkout', order_id=order.id)


@login_required
def payment_success(request, order_id):
    """Render-only success page.

    A GET can never change a payment status — if the order isn't already paid,
    the user is sent back to checkout to verify/retry instead.
    """
    order = get_object_or_404(Order, id=order_id, user=request.user)
    if not order.paid:
        return redirect('payments:checkout', order_id=order.id)
    payment = getattr(order, 'payment', None)
    return render(request, 'payments/success.html', {'order': order, 'payment': payment})


@login_required
def payment_error(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'payments/error.html', {'order': order})
