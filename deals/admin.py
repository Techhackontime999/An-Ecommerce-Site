from django.contrib import admin
from .models import Deal

@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):
    list_display = ('product', 'deal_price', 'start_time', 'end_time', 'is_active')
    list_filter = ('start_time', 'end_time')
