from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from shop.models import Product

from .models import WishlistItem


def _next_url(request):
    url = request.POST.get('next') or request.GET.get('next')
    if url and url_has_allowed_host_and_scheme(url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return url
    referer = request.META.get('HTTP_REFERER', '')
    if referer and url_has_allowed_host_and_scheme(referer, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return referer
    return None


@login_required
def wishlist_detail(request):
    items = (
        WishlistItem.objects.filter(user=request.user)
        .select_related('product__category', 'product__seller')
        .prefetch_related('product__images')
    )
    total = items.count()
    query = request.GET.get('q', '').strip()
    if query:
        items = items.filter(product__name__icontains=query)
    wished = {item.product_id for item in items}
    return render(request, 'wishlist/wishlist.html', {
        'items': items,
        'wished': wished,
        'query': query,
        'total_items': total,
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


@login_required
@require_POST
def bulk_remove_wishlist(request):
    ids = request.POST.getlist('selected')
    removed, _ = WishlistItem.objects.filter(
        user=request.user, product_id__in=ids).delete()
    if removed:
        messages.success(request, f'{removed} item{"s" if removed != 1 else ""} removed from your wishlist.')
    else:
        messages.warning(request, 'No items selected.')
    return redirect('wishlist:wishlist_detail')
