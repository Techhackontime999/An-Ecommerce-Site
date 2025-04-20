from django.contrib import admin
from .models import SellerProduct

# @admin.register(SellerProduct)
# class SellerProductAdmin(admin.ModelAdmin):
#     list_display = ('seller', 'product', 'price', 'quantity', 'deals')
#     list_filter = ('seller', 'product', 'deals')
#     search_fields = ('seller__user__username', 'product__name')


@admin.register(SellerProduct)
class SellerProductAdmin(admin.ModelAdmin):
    list_display = ("seller", "product", "price", "quantity", "deals", "is_active_seller", "created_at")
    list_filter = ("is_active_seller", "deals")  # fixed: use 'deal', not 'deals'
    search_fields = ("seller__shop_name", "product__name")
