from io import StringIO

from django.conf import settings
from django.contrib import admin
from django.core.management import call_command
from django.http import Http404
from django.shortcuts import redirect, render
from django.contrib import messages


ADMIN_MODELS_CLEAR_ORDER = [
    'reviews.ReviewReport', 'reviews.ProductReviewImage', 'reviews.ProductReview',
    'shipping.ShippingAddress', 'shipping.ShippingMethod',
    'blogs.PostReport', 'blogs.PostView', 'blogs.ActivityFeedItem', 'blogs.UserReaction',
    'blogs.Notification', 'blogs.Follow', 'blogs.Like', 'blogs.Bookmark',
    'blogs.Comment', 'blogs.PostImage', 'blogs.PostProduct', 'blogs.Post',
    'blogs.Badge', 'blogs.UserProfile', 'blogs.Tag',
    'news.NewsItem',
    'notifications.Notification', 'notifications.NotificationPreference',
    'preferences.UserPreference',
    'newsletter.Subscriber',
    'seller.SellerProduct', 'documentation.DocumentationSection',
    'contact.ContactMessage', 'about.TeamMember', 'about.AboutSection',
    'faq.Story', 'faq.FAQ', 'services.Service',
    'payments.Payment', 'order.Refund', 'order.ReturnRequest', 'order.OrderItem', 'order.Order',
    'reviews.SellerReview', 'deals.Deal',
    'coupons.Coupon', 'shop.Product', 'accounts.SellerProfile',
    'accounts.CustomerProfile', 'shop.Category',
]


def _debug_only(request):
    if not settings.DEBUG:
        raise Http404


def seed_data_view(request):
    _debug_only(request)
    buf = StringIO()
    preset = request.GET.get('preset', 'medium')
    if preset not in ('tiny', 'small', 'medium', 'large', 'full'):
        preset = 'medium'
    try:
        call_command('seed_all', preset=preset, stdout=buf)
        output = buf.getvalue()
        messages.success(request, f'Database seeded! [{preset} preset]\n{output}')
    except Exception as e:
        messages.error(request, f'Seeding failed: {e}')
    return redirect('admin:index')


def clear_data_view(request):
    _debug_only(request)
    from django.apps import apps
    cleared = []
    for model_label in ADMIN_MODELS_CLEAR_ORDER:
        try:
            model = apps.get_model(model_label)
            count = model.objects.count()
            model.objects.all().delete()
            if count:
                cleared.append(f'{model.__name__} ({count})')
        except LookupError:
            pass
    if cleared:
        messages.success(request, f'Cleared: {", ".join(cleared)}')
    else:
        messages.warning(request, 'No data to clear.')
    return redirect('admin:index')


def research_insights_view(request):
    from django.db.models import Sum

    from blogs.models import Post, PostView
    from faq.models import FAQ
    from news.models import NewsItem
    from reviews.models import ProductReview, ReviewReport

    ctx = admin.site.each_context(request)
    ctx['page'] = 'research'
    try:
        ctx['total_posts'] = Post.objects.count()
        ctx['published_posts'] = Post.objects.filter(status=Post.Status.PUBLISHED).count()
        ctx['total_views'] = Post.objects.aggregate(total=Sum('view_count'))['total'] or 0
        ctx['post_views'] = PostView.objects.count()
        ctx['total_reviews'] = ProductReview.objects.count()
        ctx['pending_reports'] = ReviewReport.objects.filter(status='pending').count()
        ctx['faq_count'] = FAQ.objects.count()
        ctx['news_count'] = NewsItem.objects.count()
        ctx['recent_posts'] = Post.objects.select_related('author').order_by('-created')[:6]
        ctx['recent_reviews'] = (
            ProductReview.objects.select_related('reviewer', 'product')
            .order_by('-created')[:6])
        ctx['recent_faqs'] = FAQ.objects.order_by('-created_at')[:5]
    except Exception:
        ctx.setdefault('total_posts', 0)
        ctx.setdefault('published_posts', 0)
        ctx.setdefault('total_views', 0)
        ctx.setdefault('post_views', 0)
        ctx.setdefault('total_reviews', 0)
        ctx.setdefault('pending_reports', 0)
        ctx.setdefault('faq_count', 0)
        ctx.setdefault('news_count', 0)
        ctx.setdefault('recent_posts', [])
        ctx.setdefault('recent_reviews', [])
        ctx.setdefault('recent_faqs', [])
    return render(request, 'admin/pages/research_insights.html', ctx)


def analytics_view(request):
    from django.db.models import Avg, F, Sum
    from django.utils import timezone

    from blogs.models import Post, PostView
    from deals.models import Deal
    from order.models import Order, OrderItem
    from payments.models import Payment
    from reviews.models import ProductReview
    from shop.models import ProductVariant

    ctx = admin.site.each_context(request)
    ctx['page'] = 'analytics'
    try:
        revenue = Payment.objects.filter(status='captured').aggregate(total=Sum('amount'))
        ctx['revenue'] = revenue['total'] or 0
        ctx['order_count'] = Order.objects.count()
        ctx['pending_orders'] = Order.objects.filter(paid=False).count()
        ctx['avg_rating'] = ProductReview.objects.aggregate(avg=Avg('overall_rating'))['avg'] or 0
        ctx['total_views'] = Post.objects.aggregate(total=Sum('view_count'))['total'] or 0
        ctx['post_views'] = PostView.objects.count()
        ctx['active_deals'] = Deal.objects.filter(
            start_time__lte=timezone.now(), end_time__gte=timezone.now()).count()
        ctx['low_stock'] = ProductVariant.objects.filter(stock__lte=5).count()

        rows = list(
            OrderItem.objects.values('product__name')
            .annotate(units=Sum('quantity'), revenue=Sum(F('price') * F('quantity')))
            .order_by('-units')[:6]
        )
        max_units = rows[0]['units'] if rows else 0
        ctx['top_products'] = [{
            'name': row['product__name'],
            'units': row['units'],
            'revenue': row['revenue'] or 0,
            'pct': int(row['units'] / max_units * 100) if max_units else 0,
        } for row in rows]

        ctx['recent_orders'] = (
            Order.objects.select_related('user').order_by('-created')[:8])
    except Exception:
        ctx.setdefault('revenue', 0)
        ctx.setdefault('order_count', 0)
        ctx.setdefault('pending_orders', 0)
        ctx.setdefault('avg_rating', 0)
        ctx.setdefault('total_views', 0)
        ctx.setdefault('post_views', 0)
        ctx.setdefault('active_deals', 0)
        ctx.setdefault('low_stock', 0)
        ctx.setdefault('top_products', [])
        ctx.setdefault('recent_orders', [])
    return render(request, 'admin/pages/analytics.html', ctx)


def marketing_view(request):
    from django.utils import timezone

    from blogs.models import Post
    from contact.models import ContactMessage
    from coupons.models import Coupon
    from deals.models import Deal
    from news.models import NewsItem
    from newsletter.models import Subscriber
    from shop.models import Product

    ctx = admin.site.each_context(request)
    ctx['page'] = 'marketing'
    try:
        now = timezone.now()
        ctx['coupon_count'] = Coupon.objects.count()
        ctx['active_coupons'] = Coupon.objects.filter(
            active=True, valid_from__lte=now, valid_to__gte=now).count()
        ctx['deal_count'] = Deal.objects.count()
        ctx['active_deals'] = Deal.objects.filter(start_time__lte=now, end_time__gte=now).count()
        ctx['subscriber_count'] = Subscriber.objects.count()
        ctx['active_subscribers'] = Subscriber.objects.filter(is_active=True).count()
        ctx['unconfirmed_subscribers'] = Subscriber.objects.filter(is_confirmed=False).count()
        ctx['news_count'] = NewsItem.objects.filter(is_published=True).count()
        ctx['post_count'] = Post.objects.filter(status=Post.Status.PUBLISHED).count()
        ctx['product_count'] = Product.objects.count()
        ctx['message_count'] = ContactMessage.objects.count()
        ctx['recent_coupons'] = Coupon.objects.order_by('-valid_from')[:6]
        ctx['recent_deals'] = Deal.objects.select_related('product').order_by('-start_time')[:6]
        ctx['recent_subscribers'] = Subscriber.objects.order_by('-created_at')[:6]
        ctx['recent_news'] = NewsItem.objects.order_by('-publish_at')[:6]
    except Exception:
        ctx.setdefault('coupon_count', 0)
        ctx.setdefault('active_coupons', 0)
        ctx.setdefault('deal_count', 0)
        ctx.setdefault('active_deals', 0)
        ctx.setdefault('subscriber_count', 0)
        ctx.setdefault('active_subscribers', 0)
        ctx.setdefault('unconfirmed_subscribers', 0)
        ctx.setdefault('news_count', 0)
        ctx.setdefault('post_count', 0)
        ctx.setdefault('product_count', 0)
        ctx.setdefault('message_count', 0)
        ctx.setdefault('recent_coupons', [])
        ctx.setdefault('recent_deals', [])
        ctx.setdefault('recent_subscribers', [])
        ctx.setdefault('recent_news', [])
    return render(request, 'admin/pages/marketing.html', ctx)
