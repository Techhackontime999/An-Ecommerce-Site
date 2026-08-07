from django.urls import path
from . import views

app_name = 'wishlist'

urlpatterns = [
    path('', views.wishlist_detail, name='wishlist_detail'),
    path('toggle/<int:product_id>/', views.toggle_wishlist, name='toggle'),
    path('remove/<int:product_id>/', views.remove_wishlist, name='remove'),
]
