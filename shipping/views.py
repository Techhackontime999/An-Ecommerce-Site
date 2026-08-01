from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from decimal import Decimal
from .models import ShippingAddress, ShippingMethod, Shipment
from .forms import ShippingAddressForm
from cart.cart import Cart
from order.models import Order
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
            next_url = request.POST.get('next') or request.GET.get('next')
            if next_url and next_url.startswith('/') and not next_url.startswith('//'):
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


@login_required
def shipping_select(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    cart = Cart(request)
    addresses = ShippingAddress.objects.filter(user=request.user)
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
            shipping_address, _ = ShippingAddress.objects.get_or_create(
                user=request.user,
                full_name=f"{order.first_name} {order.last_name}",
                address_line1=order.address,
                city=order.city,
                postal_code=order.postal_code,
                defaults={'state': '', 'phone': ''}
            )
        else:
            shipping_address = get_object_or_404(ShippingAddress, id=address_id, user=request.user)

        order.shipping_cost = shipping_method.price
        order.shipping_method_name = shipping_method.name
        order.save()

        Shipment.objects.update_or_create(
            order=order,
            defaults={
                'shipping_method': shipping_method,
                'shipping_address': shipping_address,
                'status': 'pending',
            }
        )
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


@login_required
def order_tracking(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    shipment = getattr(order, 'shipment', None)
    return render(request, 'shipping/tracking.html', {
        'order': order,
        'shipment': shipment,
    })
