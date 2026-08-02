import django

from django.apps import apps
from django.contrib import admin
from django.conf import settings
from django.db.models import Sum

from payments.models import Payment
from shop.models import Category, Product
from reviews.models import Review
from order.models import Order
from django.contrib.auth.models import User


_orig_index = admin.site.index

STAT_MODELS = {
    'seller_product_count': 'seller.SellerProduct',
    'blog_post_count': 'blogs.Post',
    'coupon_count': 'coupons.Coupon',
    'deal_count': 'deals.Deal',
    'subscriber_count': 'newsletter.Subscriber',
    'message_count': 'contact.ContactMessage',
    'faq_count': 'faq.FAQ',
    'story_count': 'faq.Story',
    'news_count': 'news.NewsItem',
    'service_count': 'services.Service',
    'documentation_count': 'documentation.DocumentationSection',
    'about_count': 'about.AboutSection',
    'team_count': 'about.TeamMember',
    'shipment_count': 'shipping.Shipment',
    'notification_count': 'notifications.Notification',
}


def _model_count(label):
    return apps.get_model(label).objects.count()


def patched_index(request, extra_context=None):
    extra_context = extra_context or {}
    extra_context['product_count'] = Product.objects.count()
    extra_context['category_count'] = Category.objects.count()
    extra_context['order_count'] = Order.objects.count()
    extra_context['review_count'] = Review.objects.count()
    extra_context['user_count'] = User.objects.count()
    extra_context['django_version'] = '.'.join(str(v) for v in django.VERSION[:3])
    extra_context['debug'] = settings.DEBUG
    total = Payment.objects.filter(status='captured').aggregate(Sum('amount'))
    extra_context['total_revenue'] = total['amount__sum'] or 0
    for key, label in STAT_MODELS.items():
        extra_context[key] = _model_count(label)
    return _orig_index(request, extra_context=extra_context)


admin.site.index = patched_index
admin.site.site_header = "Shop-Seed Administration Panel"
admin.site.site_title = "Shop-Seed Dashboard"
admin.site.index_title = "Welcome to Shop-Seed Admin Panel"
