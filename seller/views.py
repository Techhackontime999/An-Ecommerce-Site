from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from shop.models import Product, ProductImage, ProductVariant, VariantImage
from order.models import OrderItem, Order
from accounts.models import SellerProfile
from django.contrib import messages
from .forms import ProductForm, VariantsFormSet
from accounts.forms import SellerProfileForm
from django.db.models import Q
from django.db.models import Count, F, FloatField, ExpressionWrapper
from django.db.models.functions import Log
from notifications.models import Notification
from notifications.services import notify
from django.core.files import File
import os
import math

@login_required
def seller_dashboard(request):
    try:
        profile = request.user.sellerprofile
    except SellerProfile.DoesNotExist:
        return redirect('accounts:seller_register')

    if not profile.is_verified:
        return render(request, 'seller/not_verified.html')

    products = Product.objects.filter(seller=profile)
    order_items = OrderItem.objects.filter(product__in=products)

    context = {
        'profile': profile,
        'total_products': products.count(),
        'total_orders': order_items.count(),
        'pending_orders': order_items.filter(order__paid=False).count(),
        'products': products,
    }
    return render(request, 'seller/dashboard.html', context)

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
        return redirect('accounts:seller_register')

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
    order_items = OrderItem.objects.filter(product__seller=profile).select_related('order')
    context = {
        'order_items': order_items,
        'total_orders': order_items.count(),
        'pending_orders': order_items.filter(order__paid=False).count(),
        'completed_orders': order_items.filter(order__paid=True).count(),
    }
    return render(request, 'seller/orders.html', context)

@login_required
def update_order_status(request, order_id):
    order = get_object_or_404(Order, id=order_id, items__product__seller=request.user.sellerprofile)
    order.paid = True
    order.status = Order.Status.SHIPPED
    order.save()
    notify(
        order.user,
        Notification.Category.ORDER,
        f'Order #{order.id} marked as shipped',
        f'{request.user.sellerprofile.shop_name} has shipped the item(s) in your order.',
        link=reverse('order:my_orders'),
        icon='box',
    )
    messages.success(request, 'Order marked as shipped/paid.')
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

    profile = SellerProfile.objects.all()
   

    if query:
        profile = profile.filter(Q(shop_name__icontains=query) | Q(description__icontains=query) | Q(address__icontains=query))

    return render(request, "seller/profile_search.html", {
        "profile": profile,
        "query": query,
        "search_action": "seller:sellers_profile_search",  # optional, for your navbar
    })


# seller/views.py



# def seller_detail(request, slug):
#     seller = get_object_or_404(SellerProfile, slug=slug)
#     return render(request, "seller/detail.html", {
#         "seller": seller
#     })

