
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
import requests
from cart.cart import Cart
from .models import Order, OrderItem
from .forms import OrderCreateForm
from notifications.models import Notification
from notifications.services import notify

@login_required
def order_create(request):
    cart = Cart(request)
    if not cart:
        return redirect('cart:cart_detail')
    if request.method == 'POST':
        form = OrderCreateForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)   # ✅ Create order instance without saving
            order.user = request.user         # ✅ Now assign the user
            order.save()                      # ✅ Then save the order
            for item in cart:
                is_deal = item['product'].price != item['price']
                OrderItem.objects.create(
                    order=order,
                    product=item['product'],
                    price=item['price'],
                    quantity=item['quantity'],
                    deal_applied=is_deal
                )
            cart.clear()
            notify(
                request.user,
                Notification.Category.ORDER,
                f'Order #{order.id} placed',
                'We received your order and are preparing it. Choose a shipping method to continue.',
                link=reverse('shipping:shipping_select', args=[order.id]),
                icon='box',
            )
            seller_users = set()
            for item in order.items.all():
                seller = item.product.seller
                if seller and seller.user_id:
                    seller_users.add(seller.user)
            for seller_user in seller_users:
                notify(
                    seller_user,
                    Notification.Category.ORDER,
                    f'New order #{order.id} for your shop',
                    f'{seller_user.sellerprofile.shop_name if hasattr(seller_user, "sellerprofile") else "Your shop"} received a new order. Review it in your dashboard.',
                    link=reverse('seller:orders'),
                    icon='store',
                )
            return redirect('shipping:shipping_select', order_id=order.id)
    else:
        initial = {
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'email': request.user.email,
        }
        form = OrderCreateForm(initial=initial)
    return render(request, 'order/create.html', {'cart': cart, 'form': form})


@login_required
def my_orders(request):
    orders = Order.objects.filter(user=request.user).prefetch_related('items__product', 'shipment')
    statuses = []
    for o in orders:
        shipment = getattr(o, 'shipment', None)
        statuses.append(shipment.status if shipment else None)
    stats = {
        'total': orders.count(),
        'spent': sum(o.get_total_cost() for o in orders),
        'active': sum(1 for s in statuses if s not in ('delivered', 'failed', None)),
        'delivered': sum(1 for s in statuses if s == 'delivered'),
    }
    return render(request, 'order/my_orders.html', {'orders': orders, 'stats': stats})


NOMINATIM_URL = 'https://nominatim.openstreetmap.org/reverse'
NOMINATIM_HEADERS = {'User-Agent': 'Shop-Seed checkout autofill (contact@shopseed.com)'}


def _join_parts(parts):
    cleaned = [str(p).strip() for p in parts if p and str(p).strip()]
    return ' '.join(cleaned)


@require_POST
@login_required
def autofill_address(request):
    """Reverse-geocode the browser's coordinates into a postal address."""
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
        'display_name': data.get('display_name', ''),
    })
