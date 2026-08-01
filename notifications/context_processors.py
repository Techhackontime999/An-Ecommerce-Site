from .models import Notification
from .services import get_user_role


def notifications_context(request):
    context = {
        'notification_unread_count': 0,
        'recent_notifications': [],
        'user_role': None,
    }
    if request.user.is_authenticated:
        qs = Notification.objects.filter(recipient=request.user)
        context['notification_unread_count'] = qs.filter(is_read=False).count()
        context['recent_notifications'] = qs[:5]
        context['user_role'] = get_user_role(request.user)
    return context
