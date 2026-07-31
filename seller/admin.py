from django.contrib import admin
from .models import SellerProduct


@admin.register(SellerProduct)
class SellerProductAdmin(admin.ModelAdmin):
    list_display = ['seller', 'product', 'price', 'quantity', 'deals', 'is_active_seller', 'created_at']
    list_filter = ['is_active_seller', 'deals']
    search_fields = ['seller__shop_name', 'product__name']
    list_select_related = ['seller', 'product']
    list_editable = ['price', 'quantity', 'is_active_seller']
