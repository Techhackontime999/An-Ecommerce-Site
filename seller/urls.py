from django.urls import path
from . import views

app_name = 'seller'

urlpatterns = [
    path('seller_dashboard/', views.seller_dashboard, name='seller_dashboard'),
        path('product/add/', views.add_product, name='add_product'),
    path('product/edit/<int:pk>/', views.edit_product, name='edit_product'),
    path('product/delete/<int:pk>/', views.delete_product, name='delete_product'),
    path('orders/', views.seller_orders, name='orders'),
    path('orders/update/<int:order_id>/', views.update_order_status, name='update_order_status'),
    path('profile/', views.private_profile, name='private_profile'),
    path('edit_profile/', views.edit_profile, name='edit_profile'),
    path('<slug:slug>/', views.public_profile, name='public_profile'),





]


