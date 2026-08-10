import re

from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from django.http import HttpResponseForbidden
from django.urls import include, path, re_path
from django.views.generic import TemplateView
from django.views.static import serve as static_serve

from blogs.urls import sitemaps as blog_sitemaps
from shop.sitemaps import CategorySitemap, ProductSitemap

sitemaps = {
    **blog_sitemaps,
    'products': ProductSitemap,
    'categories': CategorySitemap,
}

# KYC / business documents are never served from the public media URL. Direct
# hits on these prefixes get a 403; the only way to read them is the
# authenticated ``accounts:seller_document`` view. In production the web
# server / S3 policy must enforce the same rule (see README).
PROTECTED_MEDIA_PREFIXES = ('protected/', 'seller_documents/')


def protected_media_serve(request, path, document_root=None, show_indexes=False):
    if any(path.startswith(prefix) for prefix in PROTECTED_MEDIA_PREFIXES):
        return HttpResponseForbidden('Forbidden', content_type='text/plain')
    return static_serve(request, path, document_root=document_root, show_indexes=show_indexes)

urlpatterns = [
    path('', include('core.urls')),
    path('robots.txt', TemplateView.as_view(template_name='robots.txt', content_type='text/plain'), name='robots'),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='sitemap'),
    path('', include('reviews.urls', namespace='reviews')),
    path('accounts/', include('accounts.urls', namespace='accounts')),
    path(settings.ADMIN_URL, include('core.admin_urls')),
    path('todays-deals/', include('deals.urls', namespace='deals')),
    path('cart/', include('cart.urls', namespace='cart')),
    path('wishlist/', include('wishlist.urls', namespace='wishlist')),
    path('order/', include('order.urls', namespace='order')),
    path('services/', include('services.urls', namespace='services')),
    path('documentation/', include('documentation.urls', namespace='doc')),
    path('faq/', include('faq.urls', namespace='faq')),
    path('about/', include('about.urls', namespace='about')),
    path('blog/', include('blogs.urls', namespace='blogs')),
    path('contact/', include('contact.urls', namespace='contact')),
    path('coupons/', include('coupons.urls', namespace='coupons')),
    path('seller/', include('seller.urls', namespace='seller')),
    path('payments/', include('payments.urls', namespace='payments')),
    path('shipping/', include('shipping.urls', namespace='shipping')),
    path('logistics/', include('logistics.urls', namespace='logistics')),
    path('i18n/', include('django.conf.urls.i18n')),
    path('preferences/', include('preferences.urls', namespace='preferences')),
    path('notifications/', include('notifications.urls', namespace='notifications')),
    path('newsletter/', include('newsletter.urls', namespace='newsletter')),
    path('news/', include('news.urls', namespace='news')),
    path('legal/', include('legal.urls', namespace='legal')),
    path('', include('shop.urls', namespace='shop')),
]

# ``django.conf.urls.static.static`` only registers patterns while DEBUG is on,
# so build the media pattern explicitly — it must also exist for the non-debug
# fallback so the 403 guard below keeps protecting KYC folders there too.
MEDIA_PATTERN = re_path(
    r'^%s(?P<path>.*)$' % re.escape(settings.MEDIA_URL.lstrip('/')),
    protected_media_serve,
    kwargs={'document_root': settings.MEDIA_ROOT},
)

if settings.DEBUG:
    urlpatterns += [MEDIA_PATTERN]
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Production media fallback: when no S3 bucket is configured MEDIA_URL stays on
# the local origin, so serve the (ephemeral) filesystem media directly — except
# protected KYC folders, which go through the authenticated view only.
# When AWS_STORAGE_BUCKET_NAME is set, MEDIA_URL points at S3 and this is a no-op.
elif settings.MEDIA_URL.startswith('/'):
    urlpatterns += [MEDIA_PATTERN]
