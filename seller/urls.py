from django.urls import path
from . import views

app_name = 'seller'

urlpatterns = [
    path('search/', views.sellers_profile_search, name='sellers_profile_search'),

    path('seller_dashboard/', views.seller_dashboard, name='seller_dashboard'),
    path('verification/', views.seller_verification, name='verification'),
        path('product/add/', views.add_product, name='add_product'),
    path('product/edit/<int:pk>/', views.edit_product, name='edit_product'),
    path('product/delete/<int:pk>/', views.delete_product, name='delete_product'),
    path('product/image/delete/<int:pk>/<int:image_id>/', views.delete_product_image, name='delete_product_image'),
    path('product/image/main/<int:pk>/<int:image_id>/', views.set_product_main_image, name='set_product_main_image'),
    path('product/variant-image/delete/<int:pk>/<int:image_id>/', views.delete_variant_image, name='delete_variant_image'),
    path('orders/', views.seller_orders, name='orders'),
    path('orders/update/<int:order_id>/', views.update_order_status, name='update_order_status'),
    path('payouts/', views.seller_payouts, name='payouts'),
    path('payouts/request/', views.request_payout, name='request_payout'),
    path('profile/', views.private_profile, name='private_profile'),
    path('edit_profile/', views.edit_profile, name='edit_profile'),
    path('profile/<slug:slug>/', views.profile_details, name='profile_details'),
    path('best-sellers/', views.best_sellers, name='best_sellers'),






]


