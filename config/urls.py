# """config URL Configuration"""
# from django.conf import settings
# from django.conf.urls.static import static
# from django.contrib import admin
# from django.urls import path, include
# # from django.contrib.auth import views as auth_views
# urlpatterns = [
#     path('admin/', admin.site.urls),
#     path('cart/', include('cart.urls', namespace='cart')),
#     path('order/', include('order.urls', namespace='order')),
#     path('about/', include('about.urls' ,namespace='about')),
#     path('contact/', include('contact.urls', namespace='contact')),
#     path('coupons/', include('coupons.urls', namespace='coupons')),
#     path('', include('shop.urls', namespace='shop')),
#      path('accounts/', include('accounts.urls' ,namespace='auth')),  # NEW
#     path('accounts/', include('django.contrib.auth.urls')),
#     path('services/', include('services.urls',namespace='services')),

# ]
# # path('accounts/login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
# urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)




from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('search/', include('search.urls', namespace='search')),

    path('accounts/', include('accounts.urls', namespace='accounts')),
    path('admin/', admin.site.urls),
    path('todays-deals/', include('deals.urls', namespace='deals')),

    path('cart/', include('cart.urls', namespace='cart')),
    path('order/', include('order.urls', namespace='order')),
    path('services/', include('services.urls', namespace='services')),  # keep above shop
   path('documentation/', include('documentation.urls',namespace='doc')),
    path('faq/', include('faq.urls',namespace='faq')),  # Include the FAQ app's URLs

    path('about/', include('about.urls', namespace='about')),
    path('contact/', include('contact.urls', namespace='contact')),
    path('coupons/', include('coupons.urls', namespace='coupons')),
    path('seller/', include('seller.urls', namespace='seller')),


    path('', include('shop.urls', namespace='shop')),  # always LAST

]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
