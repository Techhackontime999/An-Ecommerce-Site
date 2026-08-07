from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.contrib import messages
from shop.models import Product, ProductVariant
from core.security import safe_next_url
from .cart import Cart
from .forms import CartAddProductForm
from coupons.forms import CouponApplyForm


@require_POST
def cart_add(request, product_id):
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)
    form = CartAddProductForm(request.POST)
    if form.is_valid():
        cd = form.cleaned_data
        variant_id = request.POST.get('variant_id') or None
        variant = None
        if variant_id:
            try:
                variant = ProductVariant.objects.get(id=int(variant_id), product=product, active=True)
            except (ProductVariant.DoesNotExist, ValueError):
                variant = None

        quantity = cd['quantity']
        stock = variant.stock if variant else None
        if stock is not None:
            in_cart = cart.cart.get(cart._key(product.id, variant.id), {}).get('quantity', 0)
            wanted = quantity if cd['update'] else in_cart + quantity
            if wanted > stock:
                messages.error(
                    request,
                    f'Sorry, only {stock} in stock for "{variant.name}". '
                    f'You already have {in_cart} in your cart.'
                )
                return redirect('shop:product_detail', id=product.id, slug=product.slug)

        cart.add(
            product=product,
            quantity=quantity,
            update_quantity=cd['update'],
            variant_id=variant.id if variant else None,
            price=variant.effective_price if variant else None,
        )
        next_url = safe_next_url(request)
        if next_url:
            return redirect(next_url)
    return redirect('cart:cart_detail')


@require_POST
def cart_remove(request, product_id, variant_id=None):
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)
    cart.remove(product, variant_id)
    return redirect('cart:cart_detail')


def cart_detail(request):
    cart = Cart(request)
    for item in cart:
        item['update_quantity_form'] = CartAddProductForm(initial={'quantity': item['quantity'], 'update': True})
    coupon_apply_form = CouponApplyForm()
    coupon = None
    try:
        coupon = cart.coupon
    except Exception:
        coupon = None
    return render(request, 'cart/detail.html', {'cart': cart, 'coupon_apply_form': coupon_apply_form, 'coupon': coupon})
