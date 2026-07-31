from django.contrib import admin
from .models import SellerProfile, CustomerProfile


@admin.register(SellerProfile)
class SellerProfileAdmin(admin.ModelAdmin):
    list_display = ['shop_name', 'user', 'phone', 'address', 'is_verified', 'created_at']
    search_fields = ['shop_name', 'user__username', 'phone']
    list_filter = ['is_verified', 'created_at']
    list_select_related = ['user']
    date_hierarchy = 'created_at'
    actions = ['verify_sellers']

    def verify_sellers(self, request, queryset):
        queryset.update(is_verified=True)
    verify_sellers.short_description = 'Mark selected sellers as verified'


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'phone', 'address']
    search_fields = ['user__username', 'phone', 'address']
    list_select_related = ['user']
