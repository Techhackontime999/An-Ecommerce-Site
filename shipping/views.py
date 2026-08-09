from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from decimal import Decimal
from .models import ShippingAddress, ShippingMethod
from .forms import ShippingAddressForm
from cart.cart import Cart
from core.security import safe_next_url
from order.models import Order
from order.access import get_order_for_request
from notifications.models import Notification
from notifications.services import notify


@login_required
def address_list(request):
    addresses = ShippingAddress.objects.filter(user=request.user)
    return render(request, 'shipping/address_list.html', {'addresses': addresses})


@login_required
def address_create(request):
    if request.method == 'POST':
        form = ShippingAddressForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.user = request.user
            if address.is_default:
                ShippingAddress.objects.filter(user=request.user, is_default=True).update(is_default=False)
            address.save()
            messages.success(request, 'Address added successfully.')
            next_url = safe_next_url(request)
            if next_url:
                return redirect(next_url)
            return redirect('shipping:address_list')
    else:
        form = ShippingAddressForm()
    return render(request, 'shipping/address_form.html', {'form': form, 'title': 'Add Address'})


@login_required
def address_update(request, address_id):
    address = get_object_or_404(ShippingAddress, id=address_id, user=request.user)
    if request.method == 'POST':
        form = ShippingAddressForm(request.POST, instance=address)
        if form.is_valid():
            addr = form.save(commit=False)
            if addr.is_default:
                ShippingAddress.objects.filter(user=request.user, is_default=True).exclude(id=address_id).update(is_default=False)
            addr.save()
            messages.success(request, 'Address updated successfully.')
            return redirect('shipping:address_list')
    else:
        form = ShippingAddressForm(instance=address)
    return render(request, 'shipping/address_form.html', {'form': form, 'title': 'Edit Address'})


@login_required
def address_delete(request, address_id):
    address = get_object_or_404(ShippingAddress, id=address_id, user=request.user)
    if request.method == 'POST':
        address.delete()
        messages.success(request, 'Address deleted.')
    return redirect('shipping:address_list')


def shipping_select(request, order_id):
    order = get_order_for_request(request, order_id)
    cart = Cart(request)
    addresses = ShippingAddress.objects.filter(user=order.user)
    methods = ShippingMethod.objects.filter(is_active=True)

    subtotal_usd = order.get_total_cost()
    first_method = methods.first()
    total_usd = subtotal_usd + (first_method.price if first_method else Decimal('0.00'))

    if request.method == 'POST':
        method_id = request.POST.get('shipping_method')
        address_id = request.POST.get('shipping_address')
        if not method_id or not address_id:
            messages.error(request, 'Please select a shipping method and address.')
            return render(request, 'shipping/select.html', {
                'order': order, 'cart': cart,
                'addresses': addresses, 'methods': methods,
                'subtotal_usd': subtotal_usd, 'total_usd': total_usd,
            })
        shipping_method = get_object_or_404(ShippingMethod, id=method_id, is_active=True)

        if address_id == 'order_address':
            if order.user is not None:
                shipping_address, _ = ShippingAddress.objects.get_or_create(
                    user=order.user,
                    full_name=f"{order.first_name} {order.last_name}",
                    address_line1=order.address,
                    city=order.city,
                    postal_code=order.postal_code,
                    defaults={'state': order.state, 'phone': order.phone, 'country': order.country or 'India'}
                )
            else:
                # Guests have no saved addresses; the order already carries the
                # delivery address entered at checkout.
                shipping_address = None
        else:
            shipping_address = get_object_or_404(ShippingAddress, id=address_id, user=order.user)

        order.shipping_cost = shipping_method.price
        order.shipping_method_name = shipping_method.name
        order.payment_method = request.POST.get('payment_method', Order.PaymentMethod.ONLINE)
        if shipping_address is not None:
            order.phone = shipping_address.phone or order.phone
            order.state = shipping_address.state or order.state
            order.country = shipping_address.country or order.country or 'India'
        order.save()

        if order.user is not None:
            notify(
                order.user,
                Notification.Category.SHIPPING,
                f'Shipping arranged for order #{order.id}',
                f'{shipping_method.name} selected ({shipping_method.estimated_delivery_days}). Complete payment to dispatch your items.',
                link=reverse('payments:checkout', args=[order.id]),
                icon='truck-fast',
            )
        return redirect('payments:checkout', order_id=order.id)

    return render(request, 'shipping/select.html', {
        'order': order, 'cart': cart,
        'addresses': addresses, 'methods': methods,
        'subtotal_usd': subtotal_usd, 'total_usd': total_usd,
    })


def order_tracking(request, order_id):
    order = get_order_for_request(request, order_id)
    logistics = (
        order.logistics_shipments.select_related('courier', 'service', 'warehouse')
        .prefetch_related('tracking_events', 'items__product')
        .order_by('created_at')
        .first()
    )
    if logistics is not None:
        shipment = logistics
        is_logistics = True
    else:
        shipment = None
        is_logistics = False
    return render(request, 'shipping/tracking.html', {
        'order': order,
        'shipment': shipment,
        'is_logistics': is_logistics,
    })
