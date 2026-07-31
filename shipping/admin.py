from django.contrib import admin
from .models import ShippingAddress, ShippingMethod, Shipment


@admin.register(ShippingAddress)
class ShippingAddressAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'user', 'city', 'state', 'is_default']
    list_filter = ['is_default', 'city', 'state']
    search_fields = ['full_name', 'address_line1', 'city']


@admin.register(ShippingMethod)
class ShippingMethodAdmin(admin.ModelAdmin):
    list_display = ['name', 'price', 'estimated_delivery_days', 'is_active']
    list_editable = ['is_active']


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = ['order', 'shipping_method', 'tracking_number', 'status', 'created_at']
    list_filter = ['status', 'shipping_method']
    search_fields = ['order__id', 'tracking_number']
