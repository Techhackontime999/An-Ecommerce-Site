from django.contrib import admin
from django.utils import timezone
from .models import ShippingAddress, ShippingMethod, Shipment
from notifications.models import Notification
from notifications.services import notify


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

    STATUS_MESSAGES = {
        'shipped': ('Your order is on its way!', 'Your shipment for order #{order_id} has been dispatched. Track it anytime.'),
        'in_transit': ('Your order is in transit', 'Shipment for order #{order_id} is on the move and heading to you.'),
        'delivered': ('Order delivered!', 'Your order #{order_id} has been delivered. Enjoy!'),
        'failed': ('Delivery issue with your order', 'There was a delivery issue with order #{order_id}. Contact support for help.'),
    }

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change:
            return
        old = Shipment.objects.get(pk=obj.pk)
        if old.status == obj.status:
            return
        new_status = obj.status
        if new_status == 'shipped' and not obj.shipped_at:
            obj.shipped_at = timezone.now()
            obj.save(update_fields=['shipped_at'])
        if new_status == 'delivered' and not obj.delivered_at:
            obj.delivered_at = timezone.now()
            obj.save(update_fields=['delivered_at'])
        if new_status in self.STATUS_MESSAGES:
            title, message = self.STATUS_MESSAGES[new_status]
            notify(
                obj.order.user,
                Notification.Category.SHIPPING,
                title,
                message.format(order_id=obj.order.id),
                link='/order/my-orders/',
                icon='truck-fast',
            )
