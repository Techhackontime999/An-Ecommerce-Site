from django.core.cache import cache

from .models import Notification
from .services import UNREAD_CACHE_TTL, get_user_role, unread_cache_key


def notifications_context(request):
    context = {
        'notification_unread_count': 0,
        'recent_notifications': [],
        'user_role': None,
    }
    if request.user.is_authenticated:
        key = unread_cache_key(request.user.pk)
        payload = cache.get(key)
        if payload is None:
            qs = Notification.objects.filter(recipient=request.user)
            payload = {
                'unread': qs.filter(is_read=False).count(),
                'recent': list(qs[:5]),
                'role': get_user_role(request.user),
            }
            cache.set(key, payload, UNREAD_CACHE_TTL)
        context['notification_unread_count'] = payload['unread']
        context['recent_notifications'] = payload['recent']
        context['user_role'] = payload['role']
    return context
