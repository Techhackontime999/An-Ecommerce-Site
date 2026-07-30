from django.contrib import admin
from .models import SellerProfile, CustomerProfile


@admin.register(SellerProfile)
class SellerProfileAdmin(admin.ModelAdmin):
    list_display = ['shop_name', 'user', 'phone', 'address', 'is_verified', 'created_at']
    search_fields = ['shop_name', 'user__username', 'phone']
    list_filter = ['is_verified', 'created_at']


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'phone']
    search_fields = ['user__username', 'phone', 'address']
