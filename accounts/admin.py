from django.contrib import admin

# Register your models here.
from django.contrib.auth.models import Group

from .models import SellerProfile, CustomerProfile

@admin.register(SellerProfile)
class SellerProfileAdmin(admin.ModelAdmin):
    list_display = ['shop_name', 'user', 'phone','address','is_verified', 'created_at']
    search_fields = ['shop_name', 'username', 'phone']
    list_filter = ['is_verified', 'created_at']

@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'phone']
    search_fields = ['username', 'phone' ,'address']

# admin.site.register(SellerProfile)
# admin.site.register(CustomerProfile)


