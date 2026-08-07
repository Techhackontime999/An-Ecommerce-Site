import json
import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render, reverse
from django.views.decorators.csrf import csrf_exempt

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

    if not verify_callback_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature):
        mark_payment_failed(payment)
        return redirect('payments:error', order_id=payment.order.id)

    finalize_payment(payment, razorpay_payment_id, razorpay_signature)
    return redirect('payments:success', order_id=payment.order.id)


@csrf_exempt
def payment_webhook(request):
    """Razorpay webhook. Idempotent — safe even if delivered more than once."""
    if request.method != 'POST':
        return HttpResponseBadRequest('Invalid request method')

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

    if event_name in ('payment.captured', 'order.paid'):
        finalize_payment(payment, razorpay_payment_id)
    elif event_name == 'payment.failed':
        mark_payment_failed(payment, 'Payment was declined by your bank / card issuer.')

    return HttpResponse('OK', status=200)


@login_required
def payment_success(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    payment = getattr(order, 'payment', None)

    if not order.paid and payment:
        # The user landed here without a verified capture (page refresh after the
        # redirect, or the callback never returned). Confirm with the gateway
        # before trusting the screen.
        try:
            razorpay_payment_id = payment.razorpay_payment_id
            client = get_razorpay_client()
            detail = client.payment.fetch(razorpay_payment_id) if razorpay_payment_id else None
            if detail and detail.get('status') == 'captured':
                finalize_payment(payment, detail['id'])
            else:
                return redirect('payments:checkout', order_id=order.id)
        except Exception as exc:
            logger.error('Success-page verification failed for order %s: %s', order.id, exc, exc_info=True)
            return redirect('payments:checkout', order_id=order.id)

    return render(request, 'payments/success.html', {'order': order, 'payment': payment})


@login_required
def payment_error(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'payments/error.html', {'order': order})
