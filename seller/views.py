from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from shop.models import Product, ProductImage, ProductVariant, VariantImage
from order.models import OrderItem, Order
from accounts.models import SellerProfile
from django.contrib import messages
from django.views.decorators.http import require_POST
from .forms import ProductForm, VariantsFormSet, SellerDocumentForm
from accounts.forms import SellerProfileForm
from accounts.verification import submit_for_verification
from django.db.models import Q
from django.db.models import Count, F, FloatField, ExpressionWrapper
from django.db.models.functions import Log
from notifications.models import Notification
from notifications.services import notify
from django.core.files import File
from .services import available_balance, create_payout, payout_min_amount, total_earned
import os
import math

@login_required
def seller_dashboard(request):
    try:
        profile = request.user.sellerprofile
    except SellerProfile.DoesNotExist:
        return redirect('accounts:become_seller')

    if not profile.is_verified:
        return render(request, 'seller/not_verified.html', {'profile': profile})

    products = Product.objects.filter(seller=profile)
    order_items = OrderItem.objects.filter(product__in=products)

    context = {
        'profile': profile,
        'total_products': products.count(),
        'total_orders': order_items.count(),
        'pending_orders': order_items.filter(order__paid=False).count(),
        'products': products,
        'payout_balance': available_balance(profile),
    }
    return render(request, 'seller/dashboard.html', context)


@login_required
def seller_verification(request):
    """Seller-facing page: upload KYC / business documents and submit for
    admin review. Never auto-verifies."""
    try:
        profile = request.user.sellerprofile
    except SellerProfile.DoesNotExist:
        return redirect('accounts:become_seller')

    if profile.is_verified:
        return render(request, 'seller/verification.html', {'profile': profile, 'approved': True})

    form = SellerDocumentForm()
    if request.method == 'POST':
        if request.POST.get('action') == 'submit':
            ok, detail = submit_for_verification(profile, actor=request.user)
            if ok:
                messages.success(request, 'Verification submitted for admin review.')
            else:
                messages.error(request, 'Please verify your email and phone before submitting for review.')
            return redirect('seller:verification')
        form = SellerDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.seller_profile = profile
            doc.save()
            messages.success(request, 'Document uploaded.')
            return redirect('seller:verification')

    return render(request, 'seller/verification.html', {
        'profile': profile,
        'form': form,
        'approved': False,
    })

def _save_gallery(product, files):
    for f in files:
        ProductImage.objects.create(product=product, image=f)


def _save_variant_galleries(request, variant_formset):
    """Attach uploaded per-variant gallery files to their saved variant rows."""
    for vf in variant_formset:
        if not vf.is_valid() or vf.cleaned_data.get('DELETE'):
            continue
        if not vf.instance.pk:
            continue
        files = request.FILES.getlist(vf.add_prefix('gallery_images'))
        for f in files:
            VariantImage.objects.create(variant=vf.instance, image=f)


def _make_cover(product, image):
    ProductImage.objects.filter(product=product).update(is_main=False)
    image.is_main = True
    image.save(update_fields=['is_main'])
    ext = os.path.splitext(image.image.name)[1]
    with image.image.open('rb') as f:
        product.image.save(f'{product.slug}-main{ext}', File(f), save=True)


def _ensure_default_variant(product):
    """Every product keeps at least one (default) variant so it can always be
    added to the cart. Called after the variant formset is saved."""
    if product.variants.exists():
        return None
    return ProductVariant.objects.create(
        product=product,
        name='Default',
        price=None,
        stock=0,
        active=True,
    )


@login_required
def add_product(request):
    try:
        profile = request.user.sellerprofile
    except SellerProfile.DoesNotExist:
        return redirect('accounts:become_seller')

    if not profile.is_verified:
        return render(request, 'seller/not_verified.html')

    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        variant_formset = VariantsFormSet(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.seller = profile
            product.save()
            _save_gallery(product, request.FILES.getlist('gallery_images'))
            variant_formset.instance = product
            if variant_formset.is_valid():
                variant_formset.save()
                _save_variant_galleries(request, variant_formset)
            _ensure_default_variant(product)
            messages.success(request, 'Product added successfully!')
            return redirect('seller:seller_dashboard')
    else:
        form = ProductForm()
        variant_formset = VariantsFormSet(initial=[{'name': 'Default'}])

    return render(request, 'seller/add_product.html', {'form': form, 'variant_formset': variant_formset})

@login_required
def edit_product(request, pk):
    product = get_object_or_404(Product, pk=pk, seller=request.user.sellerprofile)
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        variant_formset = VariantsFormSet(request.POST, request.FILES, instance=product)
        if form.is_valid() and variant_formset.is_valid():
            form.save()
            _save_gallery(product, request.FILES.getlist('gallery_images'))
            variant_formset.save()
            _save_variant_galleries(request, variant_formset)
            _ensure_default_variant(product)
            messages.success(request, 'Product updated successfully!')
            return redirect('seller:seller_dashboard')
    else:
        form = ProductForm(instance=product)
        initial = [{'name': 'Default'}] if not product.variants.exists() else None
        variant_formset = VariantsFormSet(instance=product, initial=initial)
    return render(request, 'seller/edit_product.html', {'form': form, 'variant_formset': variant_formset, 'product': product})


@login_required
def delete_product_image(request, pk, image_id):
    product = get_object_or_404(Product, pk=pk, seller=request.user.sellerprofile)
    image = get_object_or_404(ProductImage, pk=image_id, product=product)
    was_cover = image.is_main
    image.delete()
    if was_cover:
        next_image = product.images.first()
        if next_image:
            _make_cover(product, next_image)
        else:
            product.image.delete(save=True)
    messages.success(request, 'Photo deleted.')
    return redirect('seller:edit_product', pk=product.pk)


@login_required
def set_product_main_image(request, pk, image_id):
    product = get_object_or_404(Product, pk=pk, seller=request.user.sellerprofile)
    image = get_object_or_404(ProductImage, pk=image_id, product=product)
    _make_cover(product, image)
    messages.success(request, 'Main photo updated.')
    return redirect('seller:edit_product', pk=product.pk)


@login_required
def delete_variant_image(request, pk, image_id):
    product = get_object_or_404(Product, pk=pk, seller=request.user.sellerprofile)
    image = get_object_or_404(VariantImage, pk=image_id, variant__product=product)
    image.delete()
    messages.success(request, 'Variant photo deleted.')
    return redirect('seller:edit_product', pk=product.pk)

@login_required
def delete_product(request, pk):
    product = get_object_or_404(Product, pk=pk, seller=request.user.sellerprofile)
    product.delete()
    messages.success(request, 'Product deleted successfully!')
    return redirect('seller:seller_dashboard')

@login_required
def seller_orders(request):
    profile = request.user.sellerprofile
    order_items = (
        OrderItem.objects.filter(product__seller=profile)
        .select_related('order')
        .prefetch_related('order__logistics_shipments__courier')
    )
    context = {
        'order_items': order_items,
        'total_orders': order_items.count(),
        'pending_orders': order_items.filter(order__paid=False).count(),
        'completed_orders': order_items.filter(order__paid=True).count(),
    }
    return render(request, 'seller/orders.html', context)

@login_required
@require_POST
def update_order_status(request, order_id):
    order = get_object_or_404(
        Order.objects.filter(items__product__seller=request.user.sellerprofile).distinct(),
        id=order_id,
    )
    from order.state import set_order_status
    ok, reason = set_order_status(
        order, Order.Status.PROCESSING, actor=request.user,
        note=f'Confirmed by {request.user.sellerprofile.shop_name}',
    )
    if not ok:
        messages.error(request, reason)
        return redirect('seller:orders')

    created = 0
    # A seller dashboard click must never mark an order paid: only a verified
    # gateway capture (or the admin refund flow) may set paid=True. Fulfilment
    # is therefore gated on actual payment, never on a manual confirmation.
    if order.paid:
        try:
            from logistics.services.fulfillment import FulfillmentService
            created = len(FulfillmentService.create_shipments_for_order(order, actor=request.user))
        except Exception as exc:
            messages.error(request, f'Fulfilment could not be started: {exc}')

    notify(
        order.user,
        Notification.Category.ORDER,
        f'Order #{order.id} confirmed',
        (
            f'{request.user.sellerprofile.shop_name} confirmed your order. '
            f'Your item(s) are being prepared for dispatch.'
            if order.paid else
            f'{request.user.sellerprofile.shop_name} confirmed your order. '
            f'We will start preparing it once payment is received.'
        ),
        link=reverse('order:my_orders'),
        icon='box',
    )
    if order.paid:
        messages.success(request, 'Order confirmed and fulfilment started.' if created else 'Order confirmed.')
    else:
        messages.success(request, 'Order confirmed — awaiting payment.')
    return redirect('seller:orders')



# from django.shortcuts import render, redirect
# from django.contrib.auth.decorators import login_required
# from shop.models import Product
# from order.models import OrderItem
# from accounts.models import SellerProfile
# from django.contrib import messages

# @login_required
# def seller_dashboard(request):
#     try:
#         profile = request.user.sellerprofile
#     except SellerProfile.DoesNotExist:
#         return redirect('accounts:seller_register')

#     if not profile.is_verified:
#         return render(request, 'seller/not_verified.html')

#     products = Product.objects.filter(seller=profile)
#     order_items = OrderItem.objects.filter(product__in=products)

#     context = {
#         'profile': profile,
#         'total_products': products.count(),
#         'total_orders': order_items.count(),
#         'pending_orders': order_items.filter(order__paid=False).count(),
#         'products': products,
#     }
#     return render(request, 'seller/dashboard.html', context)



@login_required
def private_profile(request):
  

    profile = get_object_or_404(SellerProfile, user=request.user)
    products = Product.objects.filter(seller=profile)
    order_items = OrderItem.objects.filter(product__in=products)

    context={
        'profile': profile,
          'total_products': products.count(),
        'total_orders': order_items.count(),
        'pending_orders': order_items.filter(order__paid=False).count(),

    }
    return render(request, 'seller/seller_private_profile.html',context)

@login_required
def edit_profile(request):
    profile = get_object_or_404(SellerProfile, user=request.user)
    
    if request.method == 'POST':
        form = SellerProfileForm(request.POST, request.FILES, instance=profile)

        
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('seller:private_profile')
    else:
        form = SellerProfileForm(instance=profile)

    return render(request, 'seller/seller_edit_profile.html', {'form': form, 'profile': profile})

def profile_details(request, slug):
    profile = get_object_or_404(SellerProfile, slug=slug, is_verified=True)
    return render(request, 'seller/profile_details.html', {'profile': profile})


# def best_sellers(request):
#     query = request.GET.get("q", "").strip()
#     # profile = SellerProfile.objects.filter(is_verified=True).order_by('-rating')[:10]#its shows top-10 sellers
#     profile = SellerProfile.objects.filter(is_verified=True).order_by('-rating')

#     if query:
#         profile = profile.filter(
#             Q(shop_name__icontains=query) |
#             Q(address__icontains=query) |
#             Q(description__icontains=query)
#         )

#     return render(request, "seller/best_sellers.html", {
#         'profile': profile,
#         "query": query,  # 🔍 for input box value
#         "search_action": "seller:best_sellers",
        
#           # for navbar search action (optional)
#     })

def best_sellers(request):
    query = request.GET.get("q", "").strip()

    # Annotate review_count first, then use it in composite_score
    profile = SellerProfile.objects.annotate(
        review_count=Count('seller_reviews'),
    ).annotate(
        composite_score=ExpressionWrapper(
            F('rating') * Log(F('review_count') + 1, math.e),
            output_field=FloatField()
        )
    ).filter(is_verified=True).order_by('-composite_score')

    if query:
        profile = profile.filter(
            Q(shop_name__icontains=query) |
            Q(address__icontains=query) |
            Q(description__icontains=query)
        )

    return render(request, "seller/best_sellers.html", {
        'profile': profile,
        "query": query,
        "search_action": "seller:best_sellers",
    })




def sellers_profile_search(request):
    query = request.GET.get('q', '').strip()

    profile = SellerProfile.objects.filter(is_verified=True)
   

    if query:
        profile = profile.filter(Q(shop_name__icontains=query) | Q(description__icontains=query) | Q(address__icontains=query))

    return render(request, "seller/profile_search.html", {
        "profile": profile,
        "query": query,
        "search_action": "seller:sellers_profile_search",  # optional, for your navbar
    })


@login_required
def seller_payouts(request):
    try:
        profile = request.user.sellerprofile
    except SellerProfile.DoesNotExist:
        return redirect('accounts:become_seller')

    if not profile.is_verified:
        return render(request, 'seller/not_verified.html', {'profile': profile})

    ledger = (
        profile.ledger_entries
        .select_related('order_item__product', 'payout')
        .order_by('-created_at')[:50]
    )
    payouts = profile.payouts.order_by('-created_at')

    context = {
        'profile': profile,
        'available': available_balance(profile),
        'total_earned': total_earned(profile),
        'ledger': ledger,
        'payouts': payouts,
        'payout_min': payout_min_amount(),
    }
    return render(request, 'seller/payouts.html', context)


@login_required
@require_POST
def request_payout(request):
    try:
        profile = request.user.sellerprofile
    except SellerProfile.DoesNotExist:
        return redirect('accounts:become_seller')

    if not profile.is_verified:
        return render(request, 'seller/not_verified.html', {'profile': profile})

    payout, error = create_payout(profile, actor=request.user)
    if error:
        messages.error(request, error)
    else:
        messages.success(
            request,
            f'Payout of {payout.amount} is now processing. '
            'It will be transferred to your bank account once confirmed.',
        )
    return redirect('seller:payouts')


# seller/views.py



# def seller_detail(request, slug):
#     seller = get_object_or_404(SellerProfile, slug=slug)
#     return render(request, "seller/detail.html", {
#         "seller": seller
#     })

