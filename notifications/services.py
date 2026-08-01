from django.contrib.auth.models import User

from .models import Notification, NotificationPreference

CATEGORY_FIELD = {
    Notification.Category.ORDER: 'order_enabled',
    Notification.Category.PAYMENT: 'payment_enabled',
    Notification.Category.SHIPPING: 'shipping_enabled',
    Notification.Category.DEAL: 'deal_enabled',
    Notification.Category.REVIEW: 'review_enabled',
    Notification.Category.ACCOUNT: 'account_enabled',
    Notification.Category.SYSTEM: 'system_enabled',
    Notification.Category.PROMO: 'promo_enabled',
}

ROLE_ICONS = {
    Notification.Role.CUSTOMER: 'user',
    Notification.Role.SELLER: 'store',
    Notification.Role.ADMIN: 'shield-halved',
}


def get_user_role(user):
    """Return the role used for notifications: admin > seller > customer."""
    if user is None:
        return Notification.Role.CUSTOMER
    if user.is_superuser or user.is_staff:
        return Notification.Role.ADMIN
    if hasattr(user, 'sellerprofile'):
        return Notification.Role.SELLER
    return Notification.Role.CUSTOMER


def category_enabled(user, category):
    """Check a single user's preference for a notification category."""
    try:
        prefs = user.notification_preference
    except NotificationPreference.DoesNotExist:
        return True
    field = CATEGORY_FIELD.get(category)
    if field is None:
        return True
    return getattr(prefs, field)


def notify(recipient, category, title, message='', link='', icon=''):
    """Create a notification for a single user, honouring their preferences.

    Returns the created Notification, or None when preferences disable it.
    """
    if recipient is None:
        return None
    if not category_enabled(recipient, category):
        return None
    if not icon:
        icon = ROLE_ICONS.get(get_user_role(recipient), 'bell')
    return Notification.objects.create(
        recipient=recipient,
        role=get_user_role(recipient),
        category=category,
        title=title,
        message=message,
        link=link,
        icon=icon,
    )


def notify_role(role, category, title, message='', link='', icon=''):
    """Broadcast a notification to every user belonging to a role.

    Respects each recipient's category preferences.
    Returns the list of created Notification objects.
    """
    queryset = User.objects.filter(is_active=True)
    if role == Notification.Role.ADMIN:
        queryset = queryset.filter(is_staff=True)
    elif role == Notification.Role.SELLER:
        queryset = queryset.filter(sellerprofile__isnull=False)
    else:
        queryset = queryset.filter(is_staff=False).exclude(sellerprofile__isnull=False)

    created = []
    for user in queryset.iterator(chunk_size=500):
        item = notify(user, category, title, message, link, icon)
        if item is not None:
            created.append(item)
    return created


def unread_count(user):
    if user is None or not user.is_authenticated:
        return 0
    return Notification.objects.filter(recipient=user, is_read=False).count()
