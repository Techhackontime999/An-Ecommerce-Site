
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
import requests
import secrets
import logging
from cart.cart import Cart
from coupons.models import Coupon, CouponRedemption
from coupons.services import discount_for, validate_coupon
from .models import Order, OrderItem, ReturnRequest
from .forms import OrderCreateForm
from .access import grant_guest_access, get_order_for_request
from .services import cancel_order, invoice_number, invoice_totals
from notifications.models import Notification
from notifications.services import notify
from notifications.emails import send_order_confirmation

logger = logging.getLogger(__name__)


def _user(request):
    """The owning user for an order, or None for guest checkout."""
    return request.user if request.user.is_authenticated else None


def order_create(request):
    cart = Cart(request)
    if not cart:
        return redirect('cart:cart_detail')

    user = _user(request)

    if request.method == 'POST':
        # Idempotency: the same form carries the same token, so a double submit
        # (double-click, retry, back-button) can never create two orders.
        token = request.POST.get('checkout_token', '').strip() or secrets.token_urlsafe(32)
        existing = (
            Order.objects
            .filter(user=user, checkout_token=token)
            .exclude(status=Order.Status.CANCELLED)
            .exclude(status=Order.Status.REFUNDED)
            .first()
        )
        if existing is not None:
            grant_guest_access(request, existing)
            return redirect('shipping:shipping_select', order_id=existing.id)

        form = OrderCreateForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    order = form.save(commit=False)   # Create order instance without saving
                    order.user = user
                    order.checkout_token = token
                    # Re-validate the coupon at the *final* moment of order
                    # creation — it may have expired, been exhausted, or be out
                    # of scope since it was applied. The coupon row is locked so
                    # concurrent checkouts can never exceed the usage limits.
                    coupon = cart.coupon
                    if coupon is not None:
                        coupon = Coupon.objects.select_for_update().get(pk=coupon.pk)
                        ok, _reason = validate_coupon(
                            coupon,
                            user=user,
                            cart_total=cart.get_total_price(),
                            seller_ids=cart._seller_ids(),
                        )
                        if ok:
                            order.coupon = coupon
                            order.discount = discount_for(coupon, cart.get_total_price())
                        else:
                            order.discount = 0
                    else:
                        order.discount = 0
                    order.save()                      # Then save the order
                    for item in cart:
                        is_deal = item['product'].price != item['price']
                        variant = item.get('variant')
                        OrderItem.objects.create(
                            order=order,
                            product=item['product'],
                            variant=variant,
                            variant_name=variant.name if variant else '',
                            price=item['price'],
                            quantity=item['quantity'],
                            deal_applied=is_deal
                        )
                    if order.coupon_id and user is not None:
                        CouponRedemption.objects.create(
                            coupon=order.coupon,
                            user=user,
                            order=order,
                        )
            except IntegrityError:
                # Two concurrent POSTs raced: the other one already created the
                # order with this token. Reuse it instead of failing.
                existing = Order.objects.filter(user=user, checkout_token=token).first()
                if existing is not None:
                    grant_guest_access(request, existing)
                    return redirect('shipping:shipping_select', order_id=existing.id)
                raise

            # Order + items are durable; now clean up the cart (session + DB)
            # so purchased products never reappear, then notify.
            grant_guest_access(request, order)
            cart.clear()
            request.session['coupon_id'] = None
            send_order_confirmation(order)
            if user is not None:
                notify(
                    user,
                    Notification.Category.ORDER,
                    f'Order #{order.order_number} placed',
                    'We received your order and are preparing it. Choose a shipping method to continue.',
                    link=reverse('shipping:shipping_select', args=[order.id]),
                    icon='box',
                )
            seller_users = set()
            for item in order.items.select_related('product__seller'):
                seller = item.product.seller
                if seller and seller.user_id:
                    seller_users.add(seller.user)
            for seller_user in seller_users:
                notify(
                    seller_user,
                    Notification.Category.ORDER,
                    f'New order #{order.order_number} for your shop',
                    f'{seller_user.sellerprofile.shop_name if hasattr(seller_user, "sellerprofile") else "Your shop"} received a new order. Review it in your dashboard.',
                    link=reverse('seller:orders'),
                    icon='store',
                )
            return redirect('shipping:shipping_select', order_id=order.id)
    else:
        token = secrets.token_urlsafe(32)
        initial = {}
        if user is not None:
            initial = {
                'first_name': user.first_name,
                'last_name': user.last_name,
                'email': user.email,
            }
        form = OrderCreateForm(initial=initial)
    return render(request, 'order/create.html', {'cart': cart, 'form': form, 'checkout_token': token})


# Condensed tracking milestones shown on My Orders (LMS shipments have a
# 9-step canonical timeline; the card renders a friendlier 5-step summary).
MYO_STEPS = ['Confirmed', 'Picked Up', 'In Transit', 'Out for Delivery', 'Delivered']
MYO_STATUS_IDX = {
    'order_confirmed': 1,
    'packed': 1,
    'ready_for_pickup': 1,
    'picked_up': 2,
    'at_origin_hub': 2,
    'in_transit': 3,
    'at_destination_hub': 3,
    'out_for_delivery': 4,
    'delivered': 5,
}


@login_required
def my_orders(request):
    orders = Order.objects.filter(user=request.user).prefetch_related(
        'items__product__seller', 'logistics_shipments',
    )
    statuses = []
    for o in orders:
        logistics = o.logistics_shipments.first()
        shipment = logistics
        statuses.append(shipment.status if shipment else None)
        if logistics:
            o.tl = MYO_STEPS
            o.tl_idx = MYO_STATUS_IDX.get(logistics.status, 1)
            o.tl_shipment = logistics
        elif shipment:
            o.tl = shipment.timeline
            o.tl_idx = shipment.progress
            o.tl_shipment = None
        else:
            o.tl = []
            o.tl_idx = 0
            o.tl_shipment = None
    stats = {
        'total': orders.count(),
        'spent': sum(o.get_total_cost() for o in orders),
        'active': sum(1 for s in statuses if s not in ('delivered', 'failed', 'delivery_failed', None)),
        'delivered': sum(1 for s in statuses if s == 'delivered'),
    }
    return render(request, 'order/my_orders.html', {'orders': orders, 'stats': stats})


NOMINATIM_URL = 'https://nominatim.openstreetmap.org/reverse'
NOMINATIM_HEADERS = {'User-Agent': 'Shop-Seed checkout autofill (contact@shopseed.com)'}


def _join_parts(parts):
    cleaned = [str(p).strip() for p in parts if p and str(p).strip()]
    return ' '.join(cleaned)


@require_POST
def autofill_address(request):
    """Reverse-geocode the browser's coordinates into a postal address.

    Works for guests too — it is a public geocoding service, not account data.
    """
    try:
        lat = float(request.POST.get('lat'))
        lon = float(request.POST.get('lon'))
    except (TypeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'invalid_coordinates'}, status=400)

    if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
        return JsonResponse({'ok': False, 'error': 'invalid_coordinates'}, status=400)

    try:
        resp = requests.get(
            NOMINATIM_URL,
            params={'format': 'jsonv2', 'lat': lat, 'lon': lon, 'addressdetails': 1, 'zoom': 18},
            headers=NOMINATIM_HEADERS,
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        return JsonResponse({'ok': False, 'error': 'geocoder_unavailable'}, status=502)

    address = (data or {}).get('address') or {}
    street = _join_parts([address.get('house_number'), address.get('road'), address.get('pedestrian'), address.get('footway')])
    city = address.get('city') or address.get('town') or address.get('village') or address.get('county') or ''
    area_parts = [address.get('suburb'), address.get('neighbourhood'), address.get('city_district')]
    area = _join_parts([p for p in area_parts if p and str(p).strip() != city])

    return JsonResponse({
        'ok': True,
        'address': _join_parts([street, area]),
        'city': city,
        'postal_code': address.get('postcode', ''),
        'state': address.get('state', ''),
        'country': address.get('country', ''),
        'display_name': data.get('display_name', ''),
    })


def order_detail(request, order_id):
    order = get_order_for_request(request, order_id, queryset=(
        Order.objects.prefetch_related(
            'items__product', 'items__variant', 'logistics_shipments__courier',
            'refunds', 'return_requests', 'audit_logs',
        )
    ), token=request.GET.get('token'))
    shipment = order.logistics_shipments.select_related('courier').first()
    payment = getattr(order, 'payment', None)
    has_open_return = order.return_requests.exclude(
        status__in=[ReturnRequest.Status.REJECTED, ReturnRequest.Status.CLOSED],
    ).exists()
    return render(request, 'order/detail.html', {
        'order': order,
        'shipment': shipment,
        'payment': payment,
        'totals': invoice_totals(order),
        'invoice_number': invoice_number(order),
        'return_reasons': ReturnRequest.Reason.choices,
        'has_open_return': has_open_return,
    })


@require_POST
def request_return(request, order_id):
    """Customer asks for a return on a delivered order.

    Creates a ``ReturnRequest`` and kicks off reverse logistics through the LMS
    when a shipment exists. Never auto-refunds — an admin approves and issues
    the refund (with over-refund protection on the Refund model).
    """
    order = get_order_for_request(request, order_id)

    if order.user is None:
        messages.error(request, 'Create an account to request a return for a guest order.')
        return redirect('order:order_detail', order_id=order.id)

    if order.status != Order.Status.DELIVERED:
        messages.error(request, 'Returns are only available for delivered orders.')
        return redirect('order:order_detail', order_id=order.id)

    if order.return_requests.exclude(
        status__in=[ReturnRequest.Status.REJECTED, ReturnRequest.Status.CLOSED],
    ).exists():
        messages.error(request, 'A return request is already open for this order.')
        return redirect('order:order_detail', order_id=order.id)

    reason = request.POST.get('reason', '')
    details = request.POST.get('details', '').strip()
    if reason not in dict(ReturnRequest.Reason.choices):
        messages.error(request, 'Please choose a valid return reason.')
        return redirect('order:order_detail', order_id=order.id)

    ret = ReturnRequest.objects.create(
        order=order, user=order.user, reason=reason, details=details,
    )

    try:
        from logistics.services.fulfillment import FulfillmentService
        original = order.logistics_shipments.select_related('courier').first()
        if original is not None:
            FulfillmentService.create_return(
                original,
                return_request=ret,
                reason=reason,
                notes=details,
                actor=order.user,
            )
    except Exception as exc:
        logger.warning('Reverse logistics not started for return %s: %s', ret.id, exc)

    notify(
        order.user,
        Notification.Category.ORDER,
        f'Return requested for order {order.order_number}',
        'Your return request was received. An admin will review it and arrange a pickup.',
        link=reverse('order:order_detail', args=[order.id]),
        icon='rotate-left',
    )
    messages.success(request, 'Return request submitted.')
    return redirect('order:order_detail', order_id=order.id)


@require_POST
def order_cancel(request, order_id):
    order = get_order_for_request(request, order_id)
    actor = _user(request)
    ok, detail = cancel_order(order, actor=actor, reason=request.POST.get('reason', ''))
    if ok:
        if detail == 'cancelled_and_refunded':
            messages.success(request, 'Order cancelled and your payment has been refunded.')
        else:
            messages.success(request, 'Order cancelled.')
    else:
        messages.error(request, detail)
    return redirect('order:order_detail', order_id=order.id)


def order_invoice_pdf(request, order_id):
    order = get_order_for_request(request, order_id, token=request.GET.get('token'))
    from .services import generate_invoice_pdf
    pdf = generate_invoice_pdf(order)
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{invoice_number(order)}.pdf"'
    return response
