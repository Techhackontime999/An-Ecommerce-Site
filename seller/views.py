from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from shop.models import Product
from order.models import OrderItem, Order
from accounts.models import SellerProfile
from django.contrib import messages
from .forms import ProductForm
from accounts.forms import SellerProfileForm

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
        if form.is_valid():
            product = form.save(commit=False)
            product.seller = profile
            product.save()
            messages.success(request, 'Product added successfully!')
            return redirect('seller:seller_dashboard')
    else:
        form = ProductForm()

    return render(request, 'seller/add_product.html', {'form': form})

@login_required
def edit_product(request, pk):
    product = get_object_or_404(Product, pk=pk, seller=request.user.sellerprofile)
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, 'Product updated successfully!')
            return redirect('seller:seller_dashboard')
    else:
        form = ProductForm(instance=product)
    return render(request, 'seller/edit_product.html', {'form': form})

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
    return render(request, 'seller/orders.html', {'order_items': order_items})

@login_required
def update_order_status(request, order_id):
    order = get_object_or_404(Order, id=order_id, items__product__seller=request.user.sellerprofile)
    order.paid = True
    order.save()
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

    return render(request, 'seller/seller_edit_profile.html', {'form': form})

def public_profile(request, slug):
    profile = get_object_or_404(SellerProfile, slug=slug, is_verified=True)
    return render(request, 'seller/seller_public_profile.html', {'profile': profile})
