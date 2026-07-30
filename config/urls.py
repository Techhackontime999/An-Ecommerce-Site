from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('search/', include('search.urls', namespace='search')),
    path('', include('reviews.urls', namespace='reviews')),
    path('accounts/', include('accounts.urls', namespace='accounts')),
    path('admin/', admin.site.urls),
    path('todays-deals/', include('deals.urls', namespace='deals')),
    path('cart/', include('cart.urls', namespace='cart')),
    path('order/', include('order.urls', namespace='order')),
    path('services/', include('services.urls', namespace='services')),
    path('documentation/', include('documentation.urls', namespace='doc')),
    path('faq/', include('faq.urls', namespace='faq')),
    path('about/', include('about.urls', namespace='about')),
    path('contact/', include('contact.urls', namespace='contact')),
    path('coupons/', include('coupons.urls', namespace='coupons')),
    path('seller/', include('seller.urls', namespace='seller')),
    path('payments/', include('payments.urls', namespace='payments')),
    path('', include('shop.urls', namespace='shop')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
