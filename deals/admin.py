from django.contrib import admin
from .models import Deal


@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):
    list_display = ['product', 'deal_price', 'discount_percent', 'start_time', 'end_time', 'is_active']
    list_filter = ['start_time', 'end_time']
    search_fields = ['product__name']
    list_select_related = ['product']
    date_hierarchy = 'start_time'
    readonly_fields = ['discount_percent']

    def discount_percent(self, obj):
        if obj.product and obj.product.price:
            pct = round((1 - obj.deal_price / obj.product.price) * 100)
            return f'{pct}% off'
        return '-'
    discount_percent.short_description = 'Discount'
