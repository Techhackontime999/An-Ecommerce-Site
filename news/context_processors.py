from django.db.models import Q
from django.utils import timezone

from .models import NewsItem


def active_news_items():
    now = timezone.now()
    return NewsItem.objects.filter(
        is_published=True,
        publish_at__lte=now,
    ).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=now)
    )


def news_ticker(request):
    items = list(active_news_items()[:12])
    return {
        'news_ticker_items': items,
        'news_ticker_label': 'Announcements',
    }
