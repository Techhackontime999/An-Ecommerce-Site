from django.contrib.syndication.views import Feed
from django.utils.feedgenerator import Atom1Feed
from django.utils import timezone

from .models import Post


class LatestPostsFeed(Feed):
    title = 'Shop-Seed Market Blog'
    link = '/blog/'
    description = 'Guides, product reviews, and buying tips from the Shop-Seed Market Blog.'

    def items(self):
        return Post.objects.filter(
            status=Post.Status.PUBLISHED,
            publish_at__lte=timezone.now(),
        ).order_by('-publish_at')[:25]

    def item_title(self, item):
        return item.title

    def item_description(self, item):
        return item.excerpt or item.meta_description or item.plain_body[:500]

    def item_link(self, item):
        return item.get_absolute_url()

    def item_pubdate(self, item):
        return item.publish_at


class AtomLatestPostsFeed(LatestPostsFeed):
    feed_type = Atom1Feed
    subtitle = LatestPostsFeed.description
