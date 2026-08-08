import django

from django.apps import apps
from django.contrib import admin
from django.conf import settings
from django.db.models import Avg, F, Sum

from payments.models import Payment
from shop.models import Category, Product
from reviews.models import ProductReview
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
    'shipment_count': 'logistics.Shipment',
    'notification_count': 'notifications.Notification',
}


def _model_count(label):
    return apps.get_model(label).objects.count()


def _time_ago(dt):
    from django.utils import timezone
    if not dt:
        return ''
    diff = timezone.now() - dt
    secs = int(diff.total_seconds())
    if secs < 60:
        return 'just now'
    if secs < 3600:
        return f'{int(secs // 60)} min ago'
    if secs < 86400:
        return f'{int(secs // 3600)} hr ago'
    if secs < 604800:
        return f'{int(secs // 86400)} day{"s" if secs // 86400 > 1 else ""} ago'
    return dt.strftime('%b %d')


def _build_dashboard_extras():
    from django.db.models import Avg, F, Sum
    from django.utils import timezone

    from blogs.models import Post
    from contact.models import ContactMessage
    from coupons.models import Coupon
    from deals.models import Deal
    from order.models import OrderItem
    from reviews.models import ProductReview
    from shop.models import ProductVariant

    extras = {}
    try:
        now = timezone.now()

        # --- Recent activity (orders, reviews, messages, posts) ---
        raw = []
        for order in Order.objects.order_by('-created')[:4]:
            raw.append((order.created, {
                'kind': 'order', 'url': 'admin:order_order_changelist',
                'title': f'Order #{order.id} placed',
                'desc': f'{order.first_name} {order.last_name} · {order.city}',
            }))
        for review in ProductReview.objects.select_related('product', 'reviewer').order_by('-created')[:3]:
            raw.append((review.created, {
                'kind': 'review', 'url': 'admin:reviews_productreview_changelist',
                'title': f'Review on {review.product.name[:40]}',
                'desc': f'{"★" * review.overall_rating} by {review.reviewer.username}',
            }))
        for msg in ContactMessage.objects.order_by('-created_at')[:3]:
            raw.append((msg.created_at, {
                'kind': 'message', 'url': 'admin:contact_contactmessage_changelist',
                'title': msg.subject[:44] or 'New contact message',
                'desc': f'From {msg.name}',
            }))
        for post in Post.objects.select_related('author').order_by('-created')[:3]:
            raw.append((post.created, {
                'kind': 'post', 'url': 'admin:blogs_post_changelist',
                'title': post.title[:44],
                'desc': f'by {post.author.username}',
            }))
        raw.sort(key=lambda item: item[0], reverse=True)
        extras['recent_activity'] = [
            {**data, 'time': _time_ago(dt)} for dt, data in raw[:8]
        ]

        # --- Top products by units sold ---
        rows = list(
            OrderItem.objects.values('product__name')
            .annotate(units=Sum('quantity'), revenue=Sum(F('price') * F('quantity')))
            .order_by('-units')[:5]
        )
        max_units = rows[0]['units'] if rows else 0
        extras['top_products'] = [{
            'name': row['product__name'],
            'units': row['units'],
            'revenue': row['revenue'] or 0,
            'pct': int(row['units'] / max_units * 100) if max_units else 0,
        } for row in rows]

        # --- Quick stats (real, computed ratios) ---
        order_count = Order.objects.count()
        deal_total = Deal.objects.count()
        coupon_total = Coupon.objects.count()
        product_review_total = ProductReview.objects.count()
        pending_orders = Order.objects.filter(paid=False).count()
        active_deals = Deal.objects.filter(start_time__lte=now, end_time__gte=now).count()
        active_coupons = Coupon.objects.filter(
            active=True, valid_from__lte=now, valid_to__gte=now).count()
        avg_rating = ProductReview.objects.filter(status='approved').aggregate(a=Avg('overall_rating'))['a'] or 0
        pending_reviews = ProductReview.objects.filter(status='pending').count()
        low_stock = ProductVariant.objects.filter(stock__lte=5).count()

        def _pct(part, total):
            return min(100, int(part / total * 100)) if total else 0

        extras['quick_stats'] = [
            {'label': 'Pending Orders', 'value': str(pending_orders), 'pct': _pct(pending_orders, order_count),
             'tone': 'orange', 'hint': 'awaiting payment'},
            {'label': 'Active Deals', 'value': str(active_deals), 'pct': _pct(active_deals, deal_total),
             'tone': 'green', 'hint': 'live right now'},
            {'label': 'Active Coupons', 'value': str(active_coupons), 'pct': _pct(active_coupons, coupon_total),
             'tone': 'blue', 'hint': 'valid today'},
            {'label': 'Average Rating', 'value': f'{avg_rating:.1f}', 'pct': _pct(int(avg_rating), 5),
             'tone': 'amber', 'hint': 'across all reviews'},
            {'label': 'Pending Reviews', 'value': str(pending_reviews), 'pct': _pct(pending_reviews, product_review_total),
             'tone': 'red', 'hint': 'awaiting moderation'},
            {'label': 'Low Stock', 'value': str(low_stock), 'pct': _pct(low_stock, low_stock + 5),
             'tone': 'slate', 'hint': 'variants with ≤ 5 units'},
        ]
    except Exception:
        extras.setdefault('recent_activity', [])
        extras.setdefault('top_products', [])
        extras.setdefault('quick_stats', [])
    return extras


def patched_index(request, extra_context=None):
    extra_context = extra_context or {}
    extra_context['product_count'] = Product.objects.count()
    extra_context['category_count'] = Category.objects.count()
    extra_context['order_count'] = Order.objects.count()
    extra_context['review_count'] = ProductReview.objects.count()
    extra_context['user_count'] = User.objects.count()
    extra_context['django_version'] = '.'.join(str(v) for v in django.VERSION[:3])
    extra_context['debug'] = settings.DEBUG
    total = Payment.objects.filter(status='captured').aggregate(Sum('amount'))
    extra_context['total_revenue'] = total['amount__sum'] or 0
    for key, label in STAT_MODELS.items():
        extra_context[key] = _model_count(label)
    extra_context.update(_build_dashboard_extras())
    return _orig_index(request, extra_context=extra_context)


admin.site.index = patched_index
admin.site.index_template = "admin/dashboard_index.html"
admin.site.site_header = "Shop-Seed Administration Panel"
admin.site.site_title = "Shop-Seed Dashboard"
admin.site.index_title = "Welcome to Shop-Seed Admin Panel"
