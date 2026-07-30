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
        return redirect('payments:error', order_id=payment.order.id)

    payment.razorpay_payment_id = razorpay_payment_id
    payment.razorpay_signature = razorpay_signature
    payment.status = 'captured'
    payment.save()

    order = payment.order
    order.paid = True
    order.save()

    return redirect('payments:success', order_id=order.id)


@login_required
def payment_success(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'payments/success.html', {'order': order})


@login_required
def payment_error(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'payments/error.html', {'order': order})
