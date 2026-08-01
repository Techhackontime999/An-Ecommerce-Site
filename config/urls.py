from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from django.urls import path, include
from django.views.generic import TemplateView

from blogs.urls import sitemaps as blog_sitemaps

urlpatterns = [
    path('robots.txt', TemplateView.as_view(template_name='robots.txt', content_type='text/plain'), name='robots'),
    path('sitemap.xml', sitemap, {'sitemaps': blog_sitemaps}, name='sitemap'),
    path('search/', include('search.urls', namespace='search')),
    path('', include('reviews.urls', namespace='reviews')),
    path('accounts/', include('accounts.urls', namespace='accounts')),
    path('admin/', include('core.admin_urls')),
    path('todays-deals/', include('deals.urls', namespace='deals')),
    path('cart/', include('cart.urls', namespace='cart')),
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
    path('i18n/', include('django.conf.urls.i18n')),
    path('preferences/', include('preferences.urls', namespace='preferences')),
    path('notifications/', include('notifications.urls', namespace='notifications')),
    path('news/', include('news.urls', namespace='news')),
    path('legal/', include('legal.urls', namespace='legal')),
    path('', include('shop.urls', namespace='shop')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
