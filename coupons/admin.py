from django.contrib import admin
from .models import Coupon


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ['code', 'discount', 'valid_from', 'valid_to', 'active', 'is_expired']
    list_filter = ['active', 'valid_from', 'valid_to']
    search_fields = ['code']
    list_editable = ['active']
    date_hierarchy = 'valid_from'

    def is_expired(self, obj):
        from django.utils.timezone import now
        return obj.valid_to < now()
    is_expired.boolean = True
    is_expired.short_description = 'Expired'
