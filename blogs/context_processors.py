from django.contrib.auth.models import User


def blog_nav(request):
    if request.user.is_authenticated:
        unread = request.user.blog_notifications.filter(is_read=False).count()
    else:
        unread = 0
    return {
        'blog_unread_notifications': unread,
    }
