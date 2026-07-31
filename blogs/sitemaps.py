from django.contrib.sitemaps import Sitemap
from django.utils import timezone

from .models import Post, Tag


class PostSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.7

    def items(self):
        return Post.objects.filter(
            status=Post.Status.PUBLISHED,
            publish_at__lte=timezone.now(),
        ).order_by('-publish_at')

    def lastmod(self, obj):
        return obj.updated


class TagSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.4

    def items(self):
        return Tag.objects.all()
