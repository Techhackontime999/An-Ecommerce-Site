from django.urls import path
from . import views

app_name = 'seller'

urlpatterns = [
    path('seller_dashboard/', views.seller_dashboard, name='seller_dashboard'),
]
