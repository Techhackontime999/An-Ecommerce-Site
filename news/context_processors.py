from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone

from .models import NewsItem

TICKER_CACHE_KEY = 'news:ticker:items'
TICKER_CACHE_TTL = 300  # seconds


def active_news_items():
    now = timezone.now()
    return NewsItem.objects.filter(
        is_published=True,
        publish_at__lte=now,
    ).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=now)
    )


def news_ticker(request):
    try:
        from platform_studio.utils import get_setting
        enabled = get_setting('show_news_ticker', '1')
        if str(enabled).strip().lower() not in ('1', 'true', 'yes', 'on'):
            return {
                'news_ticker_items': [],
                'news_ticker_label': 'Announcements',
            }
    except Exception:
        pass
    items = cache.get(TICKER_CACHE_KEY)
    if items is None:
        items = list(active_news_items()[:12])
        cache.set(TICKER_CACHE_KEY, items, TICKER_CACHE_TTL)
    return {
        'news_ticker_items': items,
        'news_ticker_label': 'Announcements',
    }
