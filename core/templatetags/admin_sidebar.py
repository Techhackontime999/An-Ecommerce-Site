from django import template

register = template.Library()


@register.simple_tag(name="admin_sidebar_counts")
def admin_sidebar_counts():
    from django.contrib.auth.models import User

    from order.models import Order

    return {
        "pending_orders": Order.objects.filter(paid=False).count(),
        "users": User.objects.count(),
    }
