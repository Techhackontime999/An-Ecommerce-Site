from django.core.cache import cache

BLOG_UNREAD_TTL = 60  # seconds


def blog_unread_key(user_id):
    return f'blog:unread:{user_id}'


def blog_nav(request):
    if request.user.is_authenticated:
        key = blog_unread_key(request.user.pk)
        unread = cache.get(key)
        if unread is None:
            unread = request.user.blog_notifications.filter(is_read=False).count()
            cache.set(key, unread, BLOG_UNREAD_TTL)
    else:
        unread = 0
    return {
        'blog_unread_notifications': unread,
    }
