from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import ShippingAddress, ShippingMethod, Shipment
from .forms import ShippingAddressForm
from cart.cart import Cart
from order.models import Order


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

    if request.method == 'POST':
        method_id = request.POST.get('shipping_method')
        address_id = request.POST.get('shipping_address')
        if not method_id or not address_id:
            messages.error(request, 'Please select a shipping method and address.')
            return render(request, 'shipping/select.html', {
                'order': order, 'cart': cart,
                'addresses': addresses, 'methods': methods,
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
        return redirect('payments:checkout', order_id=order.id)

    return render(request, 'shipping/select.html', {
        'order': order, 'cart': cart,
        'addresses': addresses, 'methods': methods,
    })


@login_required
def order_tracking(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    shipment = getattr(order, 'shipment', None)
    return render(request, 'shipping/tracking.html', {
        'order': order,
        'shipment': shipment,
    })
