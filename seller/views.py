from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from accounts.models import SellerProfile
from shop.models import Product
from order.models import Order  # if you have an Order model

# @login_required
# def seller_dashboard(request):
#     try:
#         seller_profile = SellerProfile.objects.get(user=request.user)
#     except SellerProfile.DoesNotExist:
#         return redirect('accounts:seller_register')  # Redirect if not a seller

#     products = Product.objects.filter(seller=seller_profile)
#     orders = Order.objects.filter(items__product__seller=seller_profile).distinct() if hasattr(Product, 'seller') else []
#     if not seller_profile.is_verified:
#         return render(request, 'seller/not_verified.html')
#     else:
#         return render(request, 'seller/dashboard.html', {
#         'seller': seller_profile,
#         'products': products,
#         'orders': orders,
#       })



@login_required
def seller_dashboard(request):
    seller_profile = request.user.sellerprofile
    orders = Order.objects.filter(items__product__seller=seller_profile).distinct()

    return render(request, 'seller/dashboard.html', {
        'seller_profile': seller_profile,
        'orders': orders,
    })