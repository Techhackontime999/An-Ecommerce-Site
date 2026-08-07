from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from shop.models import Product

from .models import WishlistItem


def _next_url(request):
    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url and next_url.startswith('/') and not next_url.startswith('//'):
        return next_url
    referer = request.META.get('HTTP_REFERER', '')
    if referer and referer.startswith('/') and not referer.startswith('//'):
        return referer
    return None


@login_required
def wishlist_detail(request):
    items = (
        WishlistItem.objects.filter(user=request.user)
        .select_related('product__category', 'product__seller')
        .prefetch_related('product__images')
    )
    wished = {item.product_id for item in items}
    return render(request, 'wishlist/wishlist.html', {
        'items': items,
        'wished': wished,
    })


@login_required
@require_POST
def toggle_wishlist(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    item = WishlistItem.objects.filter(user=request.user, product=product).first()
    if item:
        item.delete()
        added = False
        messages.success(request, f'Removed "{product.name}" from your wishlist.')
    else:
        WishlistItem.objects.create(user=request.user, product=product)
        added = True
        messages.success(request, f'Added "{product.name}" to your wishlist.')

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'added': added, 'product_id': product_id})

    return redirect(_next_url(request) or 'wishlist:wishlist_detail')


@login_required
@require_POST
def remove_wishlist(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    WishlistItem.objects.filter(user=request.user, product=product).delete()
    messages.success(request, f'Removed "{product.name}" from your wishlist.')
    return redirect('wishlist:wishlist_detail')
