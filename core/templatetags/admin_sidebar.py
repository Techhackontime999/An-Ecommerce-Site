from django import template

register = template.Library()


@register.simple_tag(name="admin_sidebar_counts")
def admin_sidebar_counts():
    from django.contrib.auth.models import User

    from order.models import Order, ReturnRequest

    from logistics.constants import ShipmentStatus
    from logistics.models import Shipment

    return {
        "pending_orders": Order.objects.filter(paid=False).count(),
        "open_returns": ReturnRequest.objects.filter(status="pending").count(),
        "in_transit": Shipment.objects.filter(
            status__in=ShipmentStatus.TIMELINE,
        ).count(),
        "users": User.objects.count(),
    }
