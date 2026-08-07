from django.contrib import admin

from core.admin_actions import export_as_csv_action
from .models import Coupon, CouponRedemption


class CouponRedemptionInline(admin.TabularInline):
    model = CouponRedemption
    extra = 0
    readonly_fields = ['redeemed_at']
    raw_id_fields = ['user', 'order']
    can_delete = False


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = [
        'code', 'discount', 'seller', 'max_uses', 'used_count', 'per_user_limit',
        'min_amount', 'valid_from', 'valid_to', 'active', 'is_expired',
    ]
    list_filter = ['active', 'valid_from', 'valid_to', 'seller']
    search_fields = ['code', 'seller__shop_name']
    list_editable = ['active']
    date_hierarchy = 'valid_from'
    filter_horizontal = ['allowed_users']
    inlines = [CouponRedemptionInline]

    def is_expired(self, obj):
        return obj.is_expired()
    is_expired.boolean = True
    is_expired.short_description = 'Expired'

    def used_count(self, obj):
        return obj.used_count()
    used_count.short_description = 'Uses'


@admin.register(CouponRedemption)
class CouponRedemptionAdmin(admin.ModelAdmin):
    list_display = ['coupon', 'user', 'order', 'redeemed_at']
    list_filter = ['redeemed_at', 'coupon']
    search_fields = ['coupon__code', 'user__username', 'order__order_number']
    list_select_related = ['coupon', 'user', 'order']
    raw_id_fields = ['user', 'order']
    date_hierarchy = 'redeemed_at'
    actions = [export_as_csv_action(
        description='Export selected redemptions as CSV',
        fields=['coupon', 'user', 'order', 'redeemed_at'],
    )]
