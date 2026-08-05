from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from core.admin_actions import export_as_csv_action
from .models import SellerProfile, CustomerProfile


admin.site.unregister(User)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    actions = BaseUserAdmin.actions + (export_as_csv_action(
        description='Export selected users as CSV',
        fields=['id', 'username', 'first_name', 'last_name', 'email',
                'is_staff', 'is_superuser', 'is_active', 'date_joined', 'last_login'],
    ),)


@admin.register(SellerProfile)
class SellerProfileAdmin(admin.ModelAdmin):
    list_display = ['shop_name', 'user', 'phone', 'is_verified', 'created_at']
    search_fields = ['shop_name', 'user__username', 'phone', 'account_holder_name', 'ifsc_code']
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
