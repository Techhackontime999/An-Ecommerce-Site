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
    gateway_charge,
    create_payment_link,
    create_razorpay_order,
    mark_payment_failed,
    verify_callback_signature,
    verify_payment_link_signature,
    verify_webhook_signature,
)

logger = logging.getLogger(__name__)


@login_required
def checkout(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)

    if order.paid:
        return redirect('payments:success', order_id=order.id)

    charge_amount, charge_currency, minor_units = gateway_charge(order.get_total_cost())

    payment = getattr(order, 'payment', None)

    # A stale 'created' payment (user left mid-checkout) or a failed attempt
    # must get *fresh* gateway objects so retries never reuse a dead token.
    needs_new = (
        payment is None
        or payment.status == 'failed'
        or payment.status == 'created'
    )
    if needs_new:
        # 1) Embedded checkout (default): an in-page Razorpay Order.
        try:
            rzp_order_id = create_razorpay_order(order, minor_units, charge_currency)
        except Exception as exc:
            logger.error('Razorpay order creation failed for order %s: %s', order.id, exc, exc_info=True)
            rzp_order_id = None

        # 2) Hosted Payment Link (fallback when the in-page checkout can't run,
        # e.g. browsers that block the checkout iframe / third-party cookies).
        try:
            plink_id, short_url = create_payment_link(
                order,
                amount=minor_units,
                currency=charge_currency,
                callback_url=request.build_absolute_uri(reverse('payments:link_callback')),
                name=f'{order.first_name} {order.last_name}',
                email=order.email,
                contact=order.phone or '',
            )
        except Exception as exc:
            logger.error('Payment link creation failed for order %s: %s', order.id, exc, exc_info=True)
            plink_id = None
            short_url = ''

        if payment is None:
            payment = Payment.objects.create(
                order=order,
                razorpay_order_id=rzp_order_id,
                razorpay_payment_link_id=plink_id,
                razorpay_payment_link_url=short_url,
                amount=charge_amount,
                currency=charge_currency,
            )
        else:
            payment.razorpay_order_id = rzp_order_id
            payment.razorpay_payment_link_id = plink_id
            payment.razorpay_payment_link_url = short_url
            payment.razorpay_payment_id = ''
            payment.razorpay_signature = ''
            payment.amount = charge_amount
            payment.currency = charge_currency
            payment.status = 'created'
            payment.save()

        if not rzp_order_id and not plink_id:
            return render(request, 'payments/error.html', {
                'order': order,
                'gateway_error': True,
            })

    context = {
        'order': order,
        'subtotal': sum(item.get_cost() for item in order.items.all()),
        'payment': payment,
        'razorpay_key_id': settings.RAZORPAY_KEY_ID,
        'razorpay_order_id': payment.razorpay_order_id or '',
        'amount': int(payment.amount * 100),
        'currency': payment.currency,
        'callback_url': request.build_absolute_uri(reverse('payments:callback')),
        'payment_link_url': payment.razorpay_payment_link_url,
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
def payment_link_callback(request):
    """Razorpay hosted Payment Page redirect callback (GET).

    The hosted page runs top-level on Razorpay's domain, so it works even when
    browsers block third-party cookies. After payment Razorpay redirects here
    with signature-bearing query params.
    """
    payment_link_id = request.GET.get('razorpay_payment_link_id', '')
    reference_id = request.GET.get('razorpay_payment_link_reference_id', '')
    status = request.GET.get('razorpay_payment_link_status', '')
    razorpay_payment_id = request.GET.get('razorpay_payment_id', '')
    signature = request.GET.get('razorpay_signature', '')

    try:
        payment = Payment.objects.get(razorpay_payment_link_id=payment_link_id)
    except Payment.DoesNotExist:
        return HttpResponseBadRequest('Invalid payment link')

    if status == 'failed' or not razorpay_payment_id:
        mark_payment_failed(payment, source='callback')
        return redirect('payments:error', order_id=payment.order.id)

    if not verify_payment_link_signature(
        payment_link_id, reference_id, status, razorpay_payment_id, signature
    ):
        mark_payment_failed(payment, source='callback')
        return redirect('payments:error', order_id=payment.order.id)

    try:
        finalize_payment(payment, razorpay_payment_id, source='callback')
    except Exception as exc:
        # finalize_payment already records failed/refunded state + audit; this is
        # a defensive net so a rendering/notify bug can never 500 the callback.
        logger.error('Link callback capture failed for order %s: %s', payment.order_id, exc, exc_info=True)

    order = Order.objects.get(pk=payment.order_id)
    if order.paid:
        return redirect('payments:success', order_id=order.id)
    return redirect('payments:error', order_id=order.id)


@csrf_exempt
@require_POST
def payment_webhook(request):
    """Razorpay webhook. Signature-verified, idempotent and POST-only.

    Handles both the classic order checkout (``payment.captured`` /
    ``order.paid``) and the hosted Payment Link flow (``payment_link.paid``).
    """
    signature = request.META.get('HTTP_X_RAZORPAY_SIGNATURE', '')
    raw_body = request.body.decode('utf-8')
    if not verify_webhook_signature(raw_body, signature):
        return HttpResponse('Invalid signature', status=400)

    try:
        event = json.loads(raw_body)
        event_name = event.get('event')
    except (ValueError, AttributeError):
        return HttpResponseBadRequest('Invalid payload')

    payload = event.get('payload', {}) or {}

    razorpay_payment_id = None
    razorpay_order_id = None
    razorpay_payment_link_id = None
    if event_name == 'payment_link.paid':
        link_entity = payload.get('payment_link', {}).get('entity', {}) or {}
        payment_entity = payload.get('payment', {}).get('entity', {}) or {}
        razorpay_payment_link_id = link_entity.get('id')
        razorpay_payment_id = payment_entity.get('id')
        razorpay_order_id = link_entity.get('order_id')
    else:
        payment_entity = payload.get('payment', {}).get('entity', {}) or {}
        razorpay_order_id = payment_entity.get('order_id')
        razorpay_payment_id = payment_entity.get('id')

    if not razorpay_payment_id:
        return HttpResponse('No payment id', status=400)

    try:
        if razorpay_payment_link_id:
            payment = Payment.objects.filter(
                razorpay_payment_link_id=razorpay_payment_link_id
            ).first()
        else:
            payment = Payment.objects.get(razorpay_order_id=razorpay_order_id)
    except Payment.DoesNotExist:
        payment = None

    if payment is None:
        # The Payment row can legitimately not exist yet when the webhook beats
        # the checkout's own creation (a race). Return 5xx so Razorpay retries
        # instead of silently dropping a real capture.
        logger.warning('Webhook for unknown gateway ref %s',
                       razorpay_payment_link_id or razorpay_order_id)
        return HttpResponse('Unknown order', status=500)

    try:
        if event_name in ('payment_link.paid', 'payment.captured', 'order.paid'):
            # Payment Links wrap an internal Razorpay Order; remember its id so
            # any later order.* event finds this Payment row too.
            if razorpay_order_id and not payment.razorpay_order_id:
                payment.razorpay_order_id = razorpay_order_id
                payment.save(update_fields=['razorpay_order_id', 'updated_at'])
            finalize_payment(payment, razorpay_payment_id, source='webhook')
        elif event_name == 'payment.failed':
            mark_payment_failed(payment, 'Payment was declined by your bank / card issuer.', source='webhook')
    except Exception as exc:
        logger.error('Webhook processing failed for payment %s: %s', payment.id, exc, exc_info=True)
        return HttpResponse('Processing failed', status=500)

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
